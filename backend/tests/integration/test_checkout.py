
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.core.config import reset_settings_cache
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.checkout.gateway import IntentResult, set_payment_gateway, sign_stripe_payload
from app.modules.checkout.payments import confirm_offline_payment
from app.modules.checkout.pricing import CheckoutValidationError
from app.modules.checkout.schemas import PlaceCheckoutRequest
from app.modules.checkout.service import CheckoutService
from app.modules.finance.service import FinanceService
from app.modules.platform_money.service import PlatformMoneyService
from app.modules.platform_money.supplier_ledger import SupplierLedgerService
from app.modules.procurement.service import ProcurementService
from app.modules.settings.constants import SINGLETON_KEY
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from bson import Decimal128, ObjectId
from httpx import AsyncClient
from pydantic import ValidationError

WEBHOOK_SECRET = "whsec_test_checkout_suite"
PLATFORM = {"_id": ObjectId(), "type": "platform"}

def _col(name: CollectionName) -> Any:
    return mongo_manager.collection(name)

def D(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))

def _uid() -> str:
    return str(ObjectId())

def _key() -> str:
    return f"test-{os.urandom(8).hex()}"

                                                                              

class FakeGateway:
    provider = "stripe"

    def __init__(self) -> None:
        self.intents: dict[str, IntentResult] = {}
        self.by_key: dict[str, str] = {}

    def is_configured(self) -> bool:
        return True

    def publishable_key(self) -> str | None:
        return "pk_test_fake"

    async def create_intent(
        self, *, amount_minor: int, currency: str, idempotency_key: str, metadata: dict[str, str]
    ) -> IntentResult:
        if idempotency_key in self.by_key:
            return self.intents[self.by_key[idempotency_key]]
        intent_id = f"pi_{os.urandom(6).hex()}"
        intent = IntentResult(
            id=intent_id,
            status="requires_payment_method",
            amount_minor=amount_minor,
            currency=currency.upper(),
            client_secret=f"{intent_id}_secret_x",
            metadata=dict(metadata),
        )
        self.intents[intent_id] = intent
        self.by_key[idempotency_key] = intent_id
        return intent

    async def retrieve_intent(self, intent_id: str) -> IntentResult:
        return self.intents[intent_id]

    async def cancel_intent(self, intent_id: str) -> IntentResult:
        old = self.intents[intent_id]
        self.intents[intent_id] = IntentResult(
            id=old.id, status="canceled", amount_minor=old.amount_minor, currency=old.currency, metadata=old.metadata
        )
        return self.intents[intent_id]

    def event(self, intent_id: str, type_: str, *, amount_received: int | None = None, event_id: str | None = None) -> bytes:
        intent = self.intents[intent_id]
        status = {
            "payment_intent.succeeded": "succeeded",
            "payment_intent.payment_failed": "requires_payment_method",
            "payment_intent.canceled": "canceled",
        }[type_]
        obj: dict[str, Any] = {
            "id": intent.id,
            "object": "payment_intent",
            "status": status,
            "amount": intent.amount_minor,
            "currency": intent.currency.lower(),
            "metadata": intent.metadata,
        }
        if type_ == "payment_intent.succeeded":
            obj["amount_received"] = intent.amount_minor if amount_received is None else amount_received
        if type_ == "payment_intent.payment_failed":
            obj["last_payment_error"] = {"code": "card_declined", "decline_code": "insufficient_funds", "message": "Your card has insufficient funds."}
        self.intents[intent_id] = IntentResult(
            id=intent.id,
            status=status,
            amount_minor=intent.amount_minor,
            currency=intent.currency,
            metadata=intent.metadata,
            failure_code="card_declined" if type_ == "payment_intent.payment_failed" else None,
            failure_message="Your card has insufficient funds." if type_ == "payment_intent.payment_failed" else None,
        )
        return json.dumps(
            {"id": event_id or f"evt_{os.urandom(6).hex()}", "type": type_, "data": {"object": obj}}
        ).encode()

@pytest.fixture
def gateway() -> Any:
    fake = FakeGateway()
    set_payment_gateway(fake)
    os.environ["STRIPE_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    reset_settings_cache()
    yield fake
    set_payment_gateway(None)
    os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
    reset_settings_cache()

@pytest.fixture
async def no_tax(app: object) -> AsyncIterator[None]:
    rows = await _col(CollectionName.TAX_SETTINGS).find({}).to_list(100)
    past = utc_now() - timedelta(days=1)
    await _col(CollectionName.TAX_SETTINGS).update_many({}, {"$set": {"effective_until": past, "effective_from": past - timedelta(days=1)}})
    try:
        yield
    finally:
        for row in rows:
            await _col(CollectionName.TAX_SETTINGS).replace_one({"_id": row["_id"]}, row)

async def _post_webhook(client: AsyncClient, payload: bytes, *, secret: str = WEBHOOK_SECRET) -> Any:
    return await client.post(
        "/api/v1/payments/stripe/webhook",
        content=payload,
        headers={"Stripe-Signature": sign_stripe_payload(payload=payload, secret=secret), "Content-Type": "application/json"},
    )

                                                                               

async def _buyer(name: str = "Buyer Co") -> dict[str, Any]:
    oid = ObjectId()
    now = utc_now()
    await _col(CollectionName.BUSINESS_ACCOUNTS).insert_one(
        {"_id": oid, "name": f"{name} {oid}", "type": "buyer", "status": "verified", "created_at": now, "updated_at": now}
    )
    return {"_id": oid, "type": "buyer"}

async def _supplier(name: str) -> dict[str, Any]:
    oid = ObjectId()
    now = utc_now()
    await _col(CollectionName.BUSINESS_ACCOUNTS).insert_one(
        {"_id": oid, "name": name, "type": "supplier", "status": "verified", "created_at": now, "updated_at": now}
    )
    await _col(CollectionName.SUPPLIER_PROFILES).insert_one(
        {"_id": ObjectId(), "business_account_id": oid, "verification_status": "verified", "created_at": now, "updated_at": now}
    )
    return {"_id": oid, "type": "supplier"}

async def _product(supplier: dict[str, Any], name: str, price: str, *, stock: int = 1000, moq: int = 1) -> ObjectId:
    pid = ObjectId()
    now = utc_now()
    await _col(CollectionName.PRODUCTS).insert_one(
        {
            "_id": pid,
            "business_account_id": supplier["_id"],
            "name": name,
            "sku": f"SKU-{str(pid)[-6:]}",
            "unit": "unit",
            "moq": moq,
            "status": "active",
            "deleted_at": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    await _col(CollectionName.PRODUCT_PRICES).insert_one(
        {
            "_id": ObjectId(),
            "product_id": pid,
            "min_quantity": 1,
            "max_quantity": None,
            "unit_price": to_decimal128(Decimal(price)),
            "currency": "USD",
            "is_active": True,
            "deleted_at": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    await _col(CollectionName.INVENTORIES).insert_one(
        {
            "_id": ObjectId(),
            "product_id": pid,
            "business_account_id": supplier["_id"],
            "available_quantity": to_decimal128(Decimal(stock)),
            "reserved_quantity": to_decimal128(Decimal(0)),
            "created_at": now,
            "updated_at": now,
        }
    )
    return pid

async def _cart(buyer: dict[str, Any], supplier: dict[str, Any], product_id: ObjectId, qty: int, *, tampered_price: str | None = None) -> None:
    now = utc_now()
    doc: dict[str, Any] = {
        "_id": ObjectId(),
        "buyer_business_id": buyer["_id"],
        "supplier_business_id": supplier["_id"],
        "product_id": product_id,
        "product_name": "Cart snapshot",
        "quantity": qty,
        "created_at": now,
        "updated_at": now,
    }
    if tampered_price is not None:
        doc["unit_price"] = to_decimal128(Decimal(tampered_price))
        doc["suggested_unit_price"] = to_decimal128(Decimal(tampered_price))
    await _col(CollectionName.CART_ITEMS).insert_one(doc)

async def _stock(product_id: ObjectId) -> tuple[Decimal, Decimal]:
    inv = await _col(CollectionName.INVENTORIES).find_one({"product_id": product_id})
    return D(inv["available_quantity"]), D(inv["reserved_quantity"])

async def _orders(checkout_id: str) -> list[dict[str, Any]]:
    return await _col(CollectionName.ORDERS).find({"checkout_id": ObjectId(checkout_id)}).to_list(50)

async def _assert_invariants(checkout_id: str) -> None:
    checkout = await _col(CollectionName.CHECKOUTS).find_one({"_id": ObjectId(checkout_id)})
    orders = await _orders(checkout_id)
                                           
    assert D(checkout["total"]) == sum((D(o["total"]) for o in orders), Decimal("0"))
                                         
    assert len({o["supplier_business_id"] for o in orders}) == len(orders)
    for order in orders:
        items = await _col(CollectionName.ORDER_ITEMS).find({"order_id": order["_id"]}).to_list(100)
        invoice = await _col(CollectionName.CUSTOMER_INVOICES).find_one({"order_id": order["_id"]})
                                                               
        lines_total = sum((D(ln["line_total"]) for ln in invoice["lines"]), Decimal("0"))
        assert D(invoice["subtotal"]) == lines_total
        assert D(invoice["total"]) == lines_total + D(invoice["tax_total"])
        assert D(invoice["total"]) == D(order["total"])
        assert invoice["supplier_business_id"] == order["supplier_business_id"]
        assert {ln["order_item_id"] for ln in invoice["lines"]} == {i["_id"] for i in items}
                                     
        commission = await _col(CollectionName.COMMISSION_RECORDS).find_one({"order_id": order["_id"]})
        assert D(commission["gross_amount"]) == D(commission["commission_amount"]) + D(commission["net_amount"])
        assert D(commission["gross_amount"]) == D(order["total"])
                                 
        for item in items:
            avail, reserved = await _stock(item["product_id"])
            assert avail >= 0 and reserved >= 0
                                
    payment = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout["payment_id"]})
    assert D(payment["amount"]) == sum((D(a["allocated_amount"]) for a in payment["allocations"]), Decimal("0"))
                                                                                  
    for order in orders:
        bal = await SupplierLedgerService().balance(business={"_id": order["supplier_business_id"], "type": "supplier"})
        assert D(bal["balance"]) == D(bal["total_credits"]) - D(bal["total_debits"])
        assert D(bal["balance"]) == D(bal["pending_balance"]) + D(bal["available_balance"])

                                                                              

@pytest.mark.asyncio
async def test_multi_supplier_card_checkout_matches_worked_example(
    app: object, client: AsyncClient, gateway: FakeGateway, no_tax: None
) -> None:
    buyer = await _buyer()
    sup_a = await _supplier("Supplier A")
    sup_b = await _supplier("Supplier B")
    a1 = await _product(sup_a, "A one", "100.00")
    a2 = await _product(sup_a, "A two", "200.00")
    b1 = await _product(sup_b, "B one", "150.00")
    b2 = await _product(sup_b, "B two", "50.00")
    for sup, pid in ((sup_a, a1), (sup_a, a2), (sup_b, b1), (sup_b, b2)):
        await _cart(buyer, sup, pid, 1)

    svc = CheckoutService()
    preview = await svc.preview(business=buyer)
    assert preview["total"] == "500.00"
    assert preview["supplier_count"] == 2
    assert preview["split_notice"]
    assert "commission" not in json.dumps(preview).lower()

    placed = await svc.place(
        user_id=_uid(), business=buyer, payment_method="card", idempotency_key=_key(), expected_total="500.00"
    )
    assert placed["total"] == "500.00"
    assert placed["client_secret"]
    assert "commission" not in json.dumps(placed).lower()
    by_supplier = {o["supplier_business_id"]: o for o in placed["orders"]}
    assert by_supplier[str(sup_a["_id"])]["total"] == "300.00"
    assert by_supplier[str(sup_b["_id"])]["total"] == "200.00"
    assert {o["order_status"] for o in placed["orders"]} == {"awaiting_payment"}
    assert all(o["order_number"].startswith("PO-") for o in placed["orders"])
    assert placed["checkout_number"].startswith("CHK-")
    assert placed["payment"]["payment_reference"].startswith("PAY-")
    assert sorted(a["amount"] for a in placed["payment"]["allocations"]) == ["200.00", "300.00"]
    assert placed["payment"]["amount"] == "500.00"

                                                                                         
    orders = await _orders(placed["id"])
    fees = {
        o["supplier_business_id"]: await _col(CollectionName.COMMISSION_RECORDS).find_one({"order_id": o["_id"]})
        for o in orders
    }
    assert D(fees[sup_a["_id"]]["commission_amount"]) == Decimal("15.00")
    assert D(fees[sup_b["_id"]]["commission_amount"]) == Decimal("10.00")
    assert D(fees[sup_a["_id"]]["rate"]) == Decimal("0.05")

                                                                            
    proc = ProcurementService()
    rows, _ = await proc.list_orders(business=sup_a)
    assert all(r["checkout_id"] != placed["id"] for r in rows)
    with pytest.raises(NotFoundError):
        await proc.get_order(user_id=_uid(), business=sup_a, order_id=str(orders[0]["_id"]))
    bal_a = await SupplierLedgerService().balance(business=sup_a)
    assert D(bal_a["balance"]) == 0

                                                                                     
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": ObjectId(placed["payment"]["id"])})
    intent_id = pay["provider_payment_id"]
    assert gateway.intents[intent_id].amount_minor == 50000
    resp = await _post_webhook(client, gateway.event(intent_id, "payment_intent.succeeded"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "completed"

    done = await svc.get(business=buyer, checkout_id=placed["id"])
    assert done["status"] == "paid"
    assert done["payment"]["status"] == "completed"
    assert done["payment"]["receipt_number"].startswith("RCP-")
    assert {o["order_status"] for o in done["orders"]} == {"pending"}
    assert {o["invoice"]["status"] for o in done["orders"]} == {"paid"}
    assert len({o["invoice"]["invoice_number"] for o in done["orders"]}) == 2

    bal_a = await SupplierLedgerService().balance(business=sup_a)
    bal_b = await SupplierLedgerService().balance(business=sup_b)
    assert D(bal_a["gross_sales"]) == Decimal("300.00") and D(bal_a["platform_fees"]) == Decimal("15.00")
    assert D(bal_a["balance"]) == Decimal("285.00") and D(bal_a["pending_balance"]) == Decimal("285.00")
    assert D(bal_b["balance"]) == Decimal("190.00")

    fee_rows = await _col(CollectionName.PLATFORM_TRANSACTIONS).find(
        {"type": "platform_fee", "order_id": {"$in": [o["_id"] for o in orders]}}
    ).to_list(10)
    assert sum((D(r["amount"]) for r in fee_rows), Decimal("0")) == Decimal("25.00")

                                                                            
    a_order = next(o for o in orders if o["supplier_business_id"] == sup_a["_id"])
    sup_view = await proc.get_order(user_id=_uid(), business=sup_a, order_id=str(a_order["_id"]))
    assert sup_view["financials"]["order_amount"] == "300.00"
    assert sup_view["financials"]["platform_fee"] == "15.00"
    assert sup_view["financials"]["supplier_earnings"] == "285.00"
    buyer_view = await proc.get_order(user_id=_uid(), business=buyer, order_id=str(a_order["_id"]))
    assert buyer_view["financials"] is None
    assert buyer_view["payment_status"] == "paid"
    assert [s["key"] for s in buyer_view["timeline"]][:3] == ["placed", "paid", "shipped"]
    assert buyer_view["timeline"][1]["state"] == "done"

                                                              
    visible = await FinanceService().get_payment(business=sup_a, payment_id=placed["payment"]["id"])
    assert len(visible["allocations"]) == 1

    await _assert_invariants(placed["id"])

                                                                              

@pytest.mark.asyncio
async def test_single_supplier_cash_is_not_received_until_staff_confirm(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    sup = await _supplier("Cash Supplier")
    pid = await _product(sup, "Rice", "12.50", stock=40)
    await _cart(buyer, sup, pid, 8)

    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    assert placed["total"] == "100.00"
    assert placed["supplier_count"] == 1 and placed["split_notice"] is None
    order = placed["orders"][0]
    assert order["order_status"] == "pending"
    assert order["invoice"]["status"] == "issued"
    assert placed["payment"]["status"] == "pending"
    assert placed["client_secret"] is None
    assert await _stock(pid) == (Decimal("32"), Decimal("8"))

                                          
    bal = await SupplierLedgerService().balance(business=sup)
    assert D(bal["balance"]) == 0
    view = await ProcurementService().get_order(user_id=_uid(), business=buyer, order_id=order["order_id"])
    assert view["payment_status"] == "awaiting_cash"

                                                                                 
    proc = ProcurementService()
    await proc.acknowledge_order(user_id=_uid(), business=sup, order_id=order["order_id"])
    assert await _stock(pid) == (Decimal("32"), Decimal("8"))

    confirmed = await confirm_offline_payment(payment_id=placed["payment"]["id"], user_id=_uid(), note="Collected")
    assert confirmed["status"] == "completed"
    again = await confirm_offline_payment(payment_id=placed["payment"]["id"], user_id=_uid(), note="again")
    assert again["status"] == "completed"

    bal = await SupplierLedgerService().balance(business=sup)
    assert D(bal["gross_sales"]) == Decimal("100.00")
    assert D(bal["platform_fees"]) == Decimal("5.00")
    assert D(bal["balance"]) == Decimal("95.00")
    entries, _ = await SupplierLedgerService().entries(business=sup)
    assert len(entries) == 2                                       
    await _assert_invariants(placed["id"])

                                                                               

@pytest.mark.asyncio
async def test_card_failure_keeps_orders_unpaid_and_can_retry(
    app: object, client: AsyncClient, gateway: FakeGateway, no_tax: None
) -> None:
    buyer = await _buyer()
    sup = await _supplier("Card Supplier")
    pid = await _product(sup, "Oil", "40.00")
    await _cart(buyer, sup, pid, 5)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="card", idempotency_key=_key())
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": ObjectId(placed["payment"]["id"])})
    intent_id = pay["provider_payment_id"]

    resp = await _post_webhook(client, gateway.event(intent_id, "payment_intent.payment_failed"))
    assert resp.status_code == 200 and resp.json()["outcome"] == "failed"
    after = await svc.get(business=buyer, checkout_id=placed["id"])
    assert after["payment"]["status"] == "failed"
    assert after["payment"]["failure_message"]
    assert after["status"] == "awaiting_payment"
    assert {o["order_status"] for o in after["orders"]} == {"awaiting_payment"}
    assert {o["invoice"]["status"] for o in after["orders"]} == {"draft"}
    assert D((await SupplierLedgerService().balance(business=sup))["balance"]) == 0

                                                               
    refreshed = await svc.refresh_payment(business=buyer, checkout_id=placed["id"])
    assert refreshed["status"] == "awaiting_payment"

    resp = await _post_webhook(client, gateway.event(intent_id, "payment_intent.succeeded"))
    assert resp.json()["outcome"] == "completed"
    assert (await svc.get(business=buyer, checkout_id=placed["id"]))["status"] == "paid"
    await _assert_invariants(placed["id"])

                                                                               

@pytest.mark.asyncio
async def test_webhooks_are_verified_idempotent_and_amount_checked(
    app: object, client: AsyncClient, gateway: FakeGateway, no_tax: None
) -> None:
    buyer = await _buyer()
    sup = await _supplier("Webhook Supplier")
    pid = await _product(sup, "Salt", "10.00")
    await _cart(buyer, sup, pid, 10)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="card", idempotency_key=_key())
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": ObjectId(placed["payment"]["id"])})
    intent_id = pay["provider_payment_id"]

                                                       
    forged = gateway.event(intent_id, "payment_intent.succeeded", event_id="evt_forged")
    resp = await _post_webhook(client, forged, secret="whsec_attacker")
    assert resp.status_code == 400
    resp = await client.post("/api/v1/payments/stripe/webhook", content=forged)
    assert resp.status_code == 400

                                                                    
    short = gateway.event(intent_id, "payment_intent.succeeded", amount_received=100, event_id="evt_short")
    resp = await _post_webhook(client, short)
    assert resp.status_code == 200 and resp.json()["outcome"] == "amount_mismatch"
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": pay["_id"]})
    assert pay["status"] == "pending" and pay["requires_attention"] is True

    good = gateway.event(intent_id, "payment_intent.succeeded", event_id="evt_good_1")
    first = await _post_webhook(client, good)
    second = await _post_webhook(client, good)
    assert first.json()["outcome"] == "completed"
    assert second.json().get("duplicate") is True
                                                                       
    third = await _post_webhook(client, gateway.event(intent_id, "payment_intent.succeeded", event_id="evt_good_2"))
    assert third.json()["outcome"] == "already_completed"

    _, total = await SupplierLedgerService().entries(business=sup)
    assert total == 2
    order_id = ObjectId(placed["orders"][0]["order_id"])
    assert await _col(CollectionName.PLATFORM_TRANSACTIONS).count_documents({"order_id": order_id, "type": "buyer_payment"}) == 1
    assert D((await SupplierLedgerService().balance(business=sup))["balance"]) == Decimal("95.00")
    await _assert_invariants(placed["id"])

                                                                               

@pytest.mark.asyncio
async def test_concurrent_checkouts_cannot_oversell(app: object, no_tax: None) -> None:
    sup = await _supplier("Scarce Supplier")
    pid = await _product(sup, "Saffron", "30.00", stock=5)
    buyers = [await _buyer(f"Racer {i}") for i in range(2)]
    for b in buyers:
        await _cart(b, sup, pid, 4)
    svc = CheckoutService()
    results = await asyncio.gather(
        *(svc.place(user_id=_uid(), business=b, payment_method="cash", idempotency_key=_key()) for b in buyers),
        return_exceptions=True,
    )
    ok = [r for r in results if isinstance(r, dict)]
    failed = [r for r in results if isinstance(r, Exception)]
    assert len(ok) == 1, results
    assert len(failed) == 1 and isinstance(failed[0], (CheckoutValidationError, ConflictError, BadRequestError))
    assert await _stock(pid) == (Decimal("1"), Decimal("4"))
    held = await _col(CollectionName.INVENTORY_TRANSACTIONS).count_documents({"product_id": pid, "transaction_type": "reservation"})
    assert held == 1
                                                                
    loser = next(b for b, r in zip(buyers, results, strict=True) if isinstance(r, Exception))
    assert await _col(CollectionName.CART_ITEMS).count_documents({"buyer_business_id": loser["_id"]}) == 1

                                                                               

@pytest.mark.asyncio
async def test_suppliers_and_buyers_cannot_reach_each_others_records(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    other_buyer = await _buyer("Other")
    sup_a = await _supplier("Iso A")
    sup_b = await _supplier("Iso B")
    outsider = await _supplier("Outsider")
    await _cart(buyer, sup_a, await _product(sup_a, "Iso A1", "20.00"), 1)
    await _cart(buyer, sup_b, await _product(sup_b, "Iso B1", "30.00"), 1)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    by_sup = {o["supplier_business_id"]: o for o in placed["orders"]}
    a_order, b_order = by_sup[str(sup_a["_id"])], by_sup[str(sup_b["_id"])]

    proc = ProcurementService()
    with pytest.raises(ForbiddenError):
        await proc.get_order(user_id=_uid(), business=outsider, order_id=a_order["order_id"])
    with pytest.raises(ForbiddenError):
        await proc.get_order(user_id=_uid(), business=sup_b, order_id=a_order["order_id"])
    with pytest.raises(ForbiddenError):
        await proc.acknowledge_order(user_id=_uid(), business=sup_b, order_id=a_order["order_id"])
    for intruder in (sup_a, other_buyer):
        with pytest.raises(NotFoundError):
            await svc.get(business=intruder, checkout_id=placed["id"])

    fin = FinanceService()
    with pytest.raises(ForbiddenError):
        await fin.get_invoice(business=sup_b, invoice_id=a_order["invoice"]["id"])
    with pytest.raises(ForbiddenError):
        await fin.get_invoice(business=other_buyer, invoice_id=a_order["invoice"]["id"])
    own = await fin.get_invoice(business=sup_a, invoice_id=a_order["invoice"]["id"])
    assert own["total"] == "20.00"
    invoices, _ = await fin.list_invoices(business=sup_a)
    assert b_order["invoice"]["id"] not in {i["id"] for i in invoices}

                                                                                 
    pay_a = await fin.get_payment(business=sup_a, payment_id=placed["payment"]["id"])
    assert [a["invoice_id"] for a in pay_a["allocations"]] == [a_order["invoice"]["id"]]
    assert pay_a["amount"] == "20.00"

    ledger = SupplierLedgerService()
    with pytest.raises(ForbiddenError):
        await ledger.balance(business=sup_a, supplier_id=str(sup_b["_id"]))
    with pytest.raises(ForbiddenError):
        await ledger.all_balances(business=sup_a)
    with pytest.raises(ForbiddenError):
        await ledger.balance(business=buyer)

                                                                               

@pytest.mark.asyncio
async def test_client_cannot_set_prices_totals_or_commission(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    sup = await _supplier("Price Supplier")
    pid = await _product(sup, "Honey", "25.00")
    await _cart(buyer, sup, pid, 4, tampered_price="0.01")

    with pytest.raises(ValidationError):
        PlaceCheckoutRequest.model_validate({"payment_method": "cash", "total": "1.00"})
    with pytest.raises(ValidationError):
        PlaceCheckoutRequest.model_validate({"payment_method": "cash", "commission_rate": "0"})
    with pytest.raises(ValidationError):
        PlaceCheckoutRequest.model_validate({"payment_method": "cash", "expected_total": 100.0})

    svc = CheckoutService()
    preview = await svc.preview(business=buyer)
    assert preview["total"] == "100.00"
    assert preview["price_changes"] and preview["price_changes"][0]["unit_price"] == "25.00"
    with pytest.raises(ConflictError):
        await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key(), expected_total="0.04")

                                                                                   
    settings = _col(CollectionName.PLATFORM_SETTINGS)
    original = (await settings.find_one({"key": SINGLETON_KEY}))["commission_rate"]
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    assert placed["total"] == "100.00"
    try:
        await settings.update_one({"key": SINGLETON_KEY}, {"$set": {"commission_rate": to_decimal128(Decimal("0.1000"))}})
        first = await _col(CollectionName.COMMISSION_RECORDS).find_one({"order_id": ObjectId(placed["orders"][0]["order_id"])})
        assert D(first["commission_amount"]) == Decimal("5.00")

        await _cart(buyer, sup, pid, 2)
        second = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
        rec = await _col(CollectionName.COMMISSION_RECORDS).find_one({"order_id": ObjectId(second["orders"][0]["order_id"])})
        assert D(rec["rate"]) == Decimal("0.1") and D(rec["commission_amount"]) == Decimal("5.00")
        assert D(rec["net_amount"]) == Decimal("45.00")
    finally:
        await settings.update_one({"key": SINGLETON_KEY}, {"$set": {"commission_rate": original}})

                                               
    with pytest.raises(ForbiddenError):
        await FinanceService().complete_payment(user_id=_uid(), business=buyer, payment_id=placed["payment"]["id"])

                                                                               

@pytest.mark.asyncio
async def test_duplicate_submissions_create_one_checkout(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    sup = await _supplier("Dup Supplier")
    pid = await _product(sup, "Tea", "5.00", stock=100)
    await _cart(buyer, sup, pid, 10)
    svc = CheckoutService()
    key = _key()
    results = await asyncio.gather(
        *(svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=key) for _ in range(3)),
        return_exceptions=True,
    )
    assert all(isinstance(r, dict) for r in results), results
    assert len({r["id"] for r in results}) == 1
    replay = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=key)
    assert replay["idempotent_replay"] is True and replay["id"] == results[0]["id"]
    assert await _col(CollectionName.CHECKOUTS).count_documents({"buyer_business_id": buyer["_id"]}) == 1
    assert await _col(CollectionName.ORDERS).count_documents({"buyer_business_id": buyer["_id"]}) == 1
    assert await _stock(pid) == (Decimal("90"), Decimal("10"))
                                                         
    with pytest.raises(CheckoutValidationError):
        await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    with pytest.raises(BadRequestError):
        await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key="short")

                                                                               

@pytest.mark.asyncio
async def test_three_suppliers_get_three_separate_invoices(app: object) -> None:
    buyer = await _buyer()
    sups = [await _supplier(f"Tri {i}") for i in range(3)]
    for i, sup in enumerate(sups):
        await _cart(buyer, sup, await _product(sup, f"Tri {i} item", f"{(i + 1) * 10}.00"), 3)
        await _cart(buyer, sup, await _product(sup, f"Tri {i} extra", "1.00"), 1)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    assert placed["supplier_count"] == 3
    invoices = await _col(CollectionName.CUSTOMER_INVOICES).find({"checkout_id": ObjectId(placed["id"])}).to_list(10)
    assert len(invoices) == 3
    assert len({i["invoice_number"] for i in invoices}) == 3
    assert {i["supplier_business_id"] for i in invoices} == {s["_id"] for s in sups}
    for inv in invoices:
        products = [ln["product_id"] for ln in inv["lines"]]
        owners = await _col(CollectionName.PRODUCTS).distinct("business_account_id", {"_id": {"$in": products}})
        assert owners == [inv["supplier_business_id"]]
    assert D(placed["total"]) == sum((D(i["total"]) for i in invoices), Decimal("0"))
    assert D(placed["tax_total"]) > 0                                           
    await _assert_invariants(placed["id"])

                                                                               

@pytest.mark.asyncio
async def test_cancel_unpaid_checkout_releases_stock_and_voids_invoices(
    app: object, gateway: FakeGateway, no_tax: None
) -> None:
    buyer = await _buyer()
    sup = await _supplier("Cancel Supplier")
    pid = await _product(sup, "Flour", "8.00", stock=20)
    await _cart(buyer, sup, pid, 5)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="card", idempotency_key=_key())
    assert await _stock(pid) == (Decimal("15"), Decimal("5"))
    cancelled = await svc.cancel(user_id=_uid(), business=buyer, checkout_id=placed["id"], reason="Changed mind")
    assert cancelled["status"] == "cancelled"
    assert await _stock(pid) == (Decimal("20"), Decimal("0"))
    assert {o["order_status"] for o in cancelled["orders"]} == {"cancelled"}
    assert {o["invoice"]["status"] for o in cancelled["orders"]} == {"void"}
    assert cancelled["payment"]["status"] == "cancelled"
    rec = await _col(CollectionName.COMMISSION_RECORDS).find_one({"order_id": ObjectId(placed["orders"][0]["order_id"])})
    assert rec["status"] == "reversed"
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": ObjectId(placed["payment"]["id"])})
    assert gateway.intents[pay["provider_payment_id"]].status == "canceled"

@pytest.mark.asyncio
async def test_supplier_decline_cancels_only_its_order(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    sup_a = await _supplier("Decline A")
    sup_b = await _supplier("Decline B")
    pa = await _product(sup_a, "DA", "10.00", stock=10)
    pb = await _product(sup_b, "DB", "20.00", stock=10)
    await _cart(buyer, sup_a, pa, 2)
    await _cart(buyer, sup_b, pb, 2)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    a_order = next(o for o in placed["orders"] if o["supplier_business_id"] == str(sup_a["_id"]))
    await svc.cancel_order(user_id=_uid(), business=sup_a, order_id=a_order["order_id"], reason="Out of season")
    after = await svc.get(business=buyer, checkout_id=placed["id"])
    statuses = {o["supplier_business_id"]: o["order_status"] for o in after["orders"]}
    assert statuses == {str(sup_a["_id"]): "cancelled", str(sup_b["_id"]): "pending"}
    assert after["active_total"] == "40.00"
    assert after["payment"]["amount"] == "40.00"
    assert len(after["payment"]["allocations"]) == 1
    assert await _stock(pa) == (Decimal("10"), Decimal("0"))
    assert await _stock(pb) == (Decimal("8"), Decimal("2"))
    pay = await _col(CollectionName.PAYMENTS).find_one({"_id": ObjectId(placed["payment"]["id"])})
    assert D(pay["amount"]) == sum((D(a["allocated_amount"]) for a in pay["allocations"]), Decimal("0"))
    assert pay["adjustments"]                                                         

@pytest.mark.asyncio
async def test_fulfilment_consumes_reservation_and_releases_supplier_funds(app: object, no_tax: None) -> None:
    buyer = await _buyer()
    sup = await _supplier("Lifecycle Supplier")
    pid = await _product(sup, "Dates", "20.00", stock=50)
    await _cart(buyer, sup, pid, 10)
    svc = CheckoutService()
    placed = await svc.place(user_id=_uid(), business=buyer, payment_method="cash", idempotency_key=_key())
    order_id = placed["orders"][0]["order_id"]
    await confirm_offline_payment(payment_id=placed["payment"]["id"], user_id=_uid(), note=None)

    proc = ProcurementService()
    confirmed = await proc.acknowledge_order(user_id=_uid(), business=sup, order_id=order_id)
    assert confirmed["status"] == "confirmed"
    item_id = confirmed["items"][0]["id"]
    shipment = await proc.create_shipment(
        user_id=_uid(),
        business=sup,
        order_id=order_id,
        payload={"carrier_name": "Courier", "tracking_number": "T-1", "lines": [{"order_item_id": item_id, "quantity": "10"}]},
    )
    assert await _stock(pid) == (Decimal("40"), Decimal("0"))
    for status in ("in_transit", "delivered"):
        await proc.add_tracking_event(user_id=_uid(), business=sup, shipment_id=shipment["id"], payload={"status": status, "description": status})
    await proc.receive_shipment(
        user_id=_uid(),
        business=buyer,
        shipment_id=shipment["id"],
        payload={"complete_order": True, "lines": [{"order_item_id": item_id, "received_quantity": "10"}]},
    )
    final = await proc.get_order(user_id=_uid(), business=buyer, order_id=order_id)
    assert final["status"] == "completed"
    assert all(step["state"] == "done" for step in final["timeline"])

    bal = await SupplierLedgerService().balance(business=sup)
    assert D(bal["balance"]) == Decimal("190.00")
    assert D(bal["available_balance"]) == Decimal("190.00")
    assert D(bal["pending_balance"]) == Decimal("0.00")
    again = await PlatformMoneyService().release_funds_for_order(order_id=order_id, user_id=_uid())
    assert again["status"] in {"already_released", "already_settled", "released"}
    assert D((await SupplierLedgerService().balance(business=sup))["balance"]) == Decimal("190.00")
    await _assert_invariants(placed["id"])
