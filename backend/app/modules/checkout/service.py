
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.db.transactions import run_in_transaction
from app.modules.checkout.constants import (
    CHECKOUT_PREFIX,
    ORDER_PREFIX,
    PAYMENT_PREFIX,
    CheckoutStatus,
)
from app.modules.checkout.gateway import PaymentGatewayError, get_payment_gateway, to_minor_units
from app.modules.checkout.payments import (
    _audit,
    _notify,
    cancel_checkout_in_session,
    cancel_order_in_session,
    remove_allocation_in_session,
    sync_card_payment,
)
from app.modules.checkout.pricing import (
    CheckoutQuote,
    CheckoutValidationError,
    build_checkout_quote,
    serialize_quote,
)
from app.modules.finance.constants import InvoiceStatus, PaymentMethod, PaymentProvider, PaymentStatus
from app.modules.identity.constants import BusinessAccountType
from app.modules.platform_money.commission import as_decimal, money
from app.modules.procurement.constants import OrderStatus
from app.modules.settings.numbering import allocate_document_number, allocate_seeded_number
from app.shared.events.bus import ORDER_CREATED, DomainEvent, event_bus
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import is_valid_object_id, parse_object_id

logger = get_logger(__name__)

IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")

def _col(name: CollectionName) -> Any:
    return mongo_manager.collection(name)

def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None

def _money_str(value: Any) -> str | None:
    return None if value is None else format(money(value), "f")

def _split_notice(count: int) -> str | None:
    if count < 2:
        return None
    return (
        f"Your cart includes products from {count} suppliers. "
        "Each supplier will have a separate order and invoice."
    )

class CheckoutService:
                                                                               

    def _require_buyer(self, business: dict[str, Any] | None) -> str:
        if not business or str(business.get("type")) != BusinessAccountType.BUYER:
            raise ForbiddenError("Switch to a buyer company to check out")
        return str(business["_id"])

    async def _get_checkout(self, checkout_id: str, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        if not is_valid_object_id(checkout_id):
            raise NotFoundError("Checkout not found")
        doc = await _col(CollectionName.CHECKOUTS).find_one({"_id": ObjectId(checkout_id)})
        if doc is None:
            raise NotFoundError("Checkout not found")
        btype = str(business.get("type"))
        if btype == BusinessAccountType.PLATFORM:
            return doc
        if btype == BusinessAccountType.BUYER and str(doc["buyer_business_id"]) == str(business["_id"]):
            return doc
                                                                                    
        raise NotFoundError("Checkout not found")

    async def _cart_rows(self, buyer_id: str) -> list[dict[str, Any]]:
        return (
            await _col(CollectionName.CART_ITEMS)
            .find({"buyer_business_id": parse_object_id(buyer_id)})
            .sort("created_at", 1)
            .to_list(length=500)
        )

    def payment_options(self) -> dict[str, Any]:
        gateway = get_payment_gateway()
        card_ready = gateway.is_configured()
        return {
            "methods": [
                {
                    "id": PaymentMethod.CASH,
                    "label": "Cash on delivery",
                    "available": True,
                    "description": "Pay in cash when your goods arrive. TradeBay confirms receipt.",
                },
                {
                    "id": PaymentMethod.CARD,
                    "label": "Visa / card",
                    "available": card_ready,
                    "description": "Pay securely by card now."
                    if card_ready
                    else "Card payments aren't switched on for this workspace yet.",
                },
            ],
            "card_publishable_key": gateway.publishable_key() if card_ready else None,
        }

                                                                              

    async def preview(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        quote = await build_checkout_quote(buyer_business_id=buyer_id, cart_rows=await self._cart_rows(buyer_id))
        payload = serialize_quote(quote)
        payload["split_notice"] = _split_notice(len(quote.groups))
        payload.update(self.payment_options())
        return payload

                                                                              

    async def place(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payment_method: str,
        idempotency_key: str | None,
        expected_total: str | None = None,
        notes: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        buyer_id = self._require_buyer(business)
        key = (idempotency_key or "").strip()
        if not IDEMPOTENCY_KEY_RE.match(key):
            raise BadRequestError("A valid Idempotency-Key header is required to place an order")
        if payment_method not in {PaymentMethod.CASH, PaymentMethod.CARD}:
            raise BadRequestError("Choose cash on delivery or card")

        existing = await _col(CollectionName.CHECKOUTS).find_one(
            {"buyer_business_id": parse_object_id(buyer_id), "idempotency_key": key}
        )
        if existing is not None:
            return await self._placed_response(existing, business=business, replay=True)

        gateway = get_payment_gateway()
        if payment_method == PaymentMethod.CARD and not gateway.is_configured():
            raise BadRequestError("Card payments aren't available yet. Choose cash on delivery.")

        quote = await build_checkout_quote(buyer_business_id=buyer_id, cart_rows=await self._cart_rows(buyer_id))
        if expected_total is not None:
            try:
                expected = money(Decimal(str(expected_total)))
            except Exception as exc:
                raise BadRequestError("Invalid expected total") from exc
            if expected != quote.total:
                raise ConflictError(
                    "Prices or availability changed since you opened checkout. Review the new total.",
                    code="CHECKOUT_TOTAL_CHANGED",
                    details={"total": format(quote.total, "f")},
                )

        clean_notes = (notes or "").strip()[:1000] or None
        try:
            checkout = await run_in_transaction(
                lambda session: self._place_tx(
                    session,
                    user_id=user_id,
                    buyer_id=buyer_id,
                    key=key,
                    quote=quote,
                    payment_method=payment_method,
                    notes=clean_notes,
                )
            )
        except (DuplicateKeyError, ConflictError):
                                                                                                
                                                                                           
            winner = await _col(CollectionName.CHECKOUTS).find_one(
                {"buyer_business_id": parse_object_id(buyer_id), "idempotency_key": key}
            )
            if winner is None:
                raise
            return await self._placed_response(winner, business=business, replay=True)

        await self._after_place(checkout, user_id=user_id, ip=ip)
        client_secret = None
        if payment_method == PaymentMethod.CARD:
            client_secret = await self._ensure_intent(checkout)
        response = await self._placed_response(checkout, business=business, replay=False)
        response["client_secret"] = client_secret
        return response

    async def _place_tx(
        self,
        session: MongoSession,
        *,
        user_id: str,
        buyer_id: str,
        key: str,
        quote: CheckoutQuote,
        payment_method: str,
        notes: str | None,
    ) -> dict[str, Any]:
        from app.modules.catalog.exceptions import InsufficientStockError
        from app.modules.catalog.service import CatalogService
        from app.modules.finance.service import issue_invoice_in_session
        from app.modules.platform_money.service import create_commission_in_session

        now = utc_now()
        buyer_oid = parse_object_id(buyer_id)
        user_oid = parse_object_id(user_id)
        is_card = payment_method == PaymentMethod.CARD
        checkout_id = ObjectId()
        checkout_number = await allocate_document_number(kind="checkout", prefix=CHECKOUT_PREFIX, session=session)

                                                                                            
                                                                                 
        consumed = await _col(CollectionName.CART_ITEMS).delete_many(
            {"_id": {"$in": quote.cart_item_ids}, "buyer_business_id": buyer_oid}, session=session
        )
        if consumed.deleted_count != len(quote.cart_item_ids):
            raise ConflictError("Your cart changed while checking out. Review it and try again.")

        catalog = CatalogService()
        groups_out: list[dict[str, Any]] = []
        allocations: list[dict[str, Any]] = []
        for group in quote.groups:
            order_id = ObjectId()
            order_number = await allocate_seeded_number(ORDER_PREFIX, CollectionName.ORDERS, "order_number", session=session)
            status = OrderStatus.AWAITING_PAYMENT if is_card else OrderStatus.PENDING
            order = {
                "_id": order_id,
                "order_number": order_number,
                "buyer_business_id": buyer_oid,
                "supplier_business_id": group.supplier_business_id,
                "rfq_id": None,
                "quotation_id": None,
                "source": "checkout",
                "checkout_id": checkout_id,
                "checkout_number": checkout_number,
                "status": status,
                "currency": quote.currency,
                "subtotal": to_decimal128(group.subtotal),
                "discount_total": to_decimal128(group.discount_total),
                "charge_total": to_decimal128(group.charge_total),
                "tax_total": to_decimal128(group.tax_total),
                "total": to_decimal128(group.total),
                "tax_rate_snapshot": to_decimal128(group.tax_rate) if group.tax_rate is not None else None,
                "tax_name_snapshot": group.tax_name,
                "shipping_address": None,
                "billing_address": None,
                "payment_terms": "Paid by card at checkout" if is_card else "Cash on delivery",
                "payment_method": payment_method,
                "delivery_terms": None,
                "payment_status": "unpaid",
                "stock_reservation_status": "reserved",
                "notes": notes,
                "created_by_user_id": user_oid,
                "status_history": [
                    {
                        "status": status,
                        "changed_by_user_id": user_oid,
                        "note": f"Placed at checkout {checkout_number}"
                        + (" — awaiting card payment" if is_card else " — cash on delivery"),
                        "changed_at": now,
                    }
                ],
                "rejection_reason": None,
                "confirmed_at": None,
                "completed_at": None,
                "cancelled_at": None,
                "created_at": now,
                "updated_at": now,
            }
            await _col(CollectionName.ORDERS).insert_one(order, session=session)

            items = []
            for line in group.lines:
                items.append(
                    {
                        "_id": ObjectId(),
                        "order_id": order_id,
                        "quotation_item_id": None,
                        "rfq_item_id": None,
                        "product_id": line.product_id,
                        "product_name_snapshot": line.product_name,
                        "sku_snapshot": line.sku,
                        "moq_snapshot": line.moq,
                        "quantity": to_decimal128(Decimal(line.quantity)),
                        "unit": line.unit,
                        "unit_price": to_decimal128(line.unit_price),
                        "discount_snapshot": to_decimal128(Decimal("0")),
                        "tax_snapshot": to_decimal128(Decimal("0")),
                        "subtotal": to_decimal128(line.line_total),
                        "line_total": to_decimal128(line.line_total),
                        "image_url_snapshot": line.image_url,
                        "shipped_quantity": to_decimal128(Decimal("0")),
                        "received_quantity": to_decimal128(Decimal("0")),
                        "damaged_quantity": to_decimal128(Decimal("0")),
                        "missing_quantity": to_decimal128(Decimal("0")),
                        "rejected_quantity": to_decimal128(Decimal("0")),
                    }
                )
            await _col(CollectionName.ORDER_ITEMS).insert_many(items, session=session)

            for line in group.lines:
                try:
                    await catalog.reserve_stock(
                        str(line.product_id),
                        business_id=str(group.supplier_business_id),
                        user_id=user_id,
                        quantity=Decimal(line.quantity),
                        reason=f"Checkout {checkout_number} / {order_number}",
                        reference_type="order",
                        reference_id=str(order_id),
                        session=session,
                    )
                except InsufficientStockError as exc:
                    raise CheckoutValidationError(
                        f"{line.product_name} just sold out or has less stock than you asked for. "
                        "Update the quantity and try again."
                    ) from exc

            invoice, _ = await issue_invoice_in_session(
                order=order,
                order_items=items,
                user_id=user_id,
                session=session,
                status=InvoiceStatus.DRAFT if is_card else InvoiceStatus.ISSUED,
            )
                                                                                                     
            if money(invoice["total"]) != group.total or money(invoice.get("tax_total")) != group.tax_total:
                await _col(CollectionName.CUSTOMER_INVOICES).update_one(
                    {"_id": invoice["_id"]},
                    {
                        "$set": {
                            "subtotal": to_decimal128(group.subtotal),
                            "discount_total": to_decimal128(group.discount_total),
                            "charge_total": to_decimal128(group.charge_total),
                            "tax_total": to_decimal128(group.tax_total),
                            "total": to_decimal128(group.total),
                            "tax_rate": to_decimal128(group.tax_rate) if group.tax_rate is not None else None,
                            "tax_name_snapshot": group.tax_name,
                            "updated_at": now,
                        }
                    },
                    session=session,
                )
                invoice["tax_total"] = to_decimal128(group.tax_total)
                invoice["total"] = to_decimal128(group.total)
            await create_commission_in_session(order=order, session=session)

            allocations.append(
                {
                    "invoice_id": invoice["_id"],
                    "order_id": order_id,
                    "supplier_business_id": group.supplier_business_id,
                    "allocated_amount": to_decimal128(group.total),
                    "allocated_at": now,
                }
            )
            groups_out.append(
                {
                    "supplier_business_id": group.supplier_business_id,
                    "supplier_name": group.supplier_name,
                    "order_id": order_id,
                    "order_number": order_number,
                    "invoice_id": invoice["_id"],
                    "invoice_number": invoice["invoice_number"],
                    "subtotal": to_decimal128(group.subtotal),
                    "tax_total": to_decimal128(group.tax_total),
                    "total": to_decimal128(group.total),
                    "line_count": len(group.lines),
                }
            )

        amount = money(sum((as_decimal(a["allocated_amount"]) for a in allocations), Decimal("0")))
        if amount != quote.total:
            raise ConflictError("Checkout total doesn't match the supplier orders")
        payment_id = ObjectId()
        payment_reference = await allocate_seeded_number(
            PAYMENT_PREFIX, CollectionName.PAYMENTS, "payment_reference", session=session
        )
        await _col(CollectionName.PAYMENTS).insert_one(
            {
                "_id": payment_id,
                "payment_reference": payment_reference,
                "idempotency_key": f"checkout:{checkout_id}",
                "checkout_id": checkout_id,
                "payer_business_id": buyer_oid,
                "amount": to_decimal128(amount),
                "currency": quote.currency,
                "payment_method": payment_method,
                "provider": PaymentProvider.STRIPE if is_card else PaymentProvider.CASH,
                "provider_payment_id": None,
                "status": PaymentStatus.PENDING,
                "allocations": allocations,
                "failure_code": None,
                "failure_message": None,
                "metadata": {"checkout_number": checkout_number},
                "receipt_document_url": None,
                "receipt_issued_at": None,
                "paid_at": None,
                "created_by_user_id": user_oid,
                "created_at": now,
                "updated_at": now,
            },
            session=session,
        )
        checkout = {
            "_id": checkout_id,
            "checkout_number": checkout_number,
            "buyer_business_id": buyer_oid,
            "created_by_user_id": user_oid,
            "idempotency_key": key,
            "status": CheckoutStatus.AWAITING_PAYMENT,
            "payment_method": payment_method,
            "currency": quote.currency,
            "subtotal": to_decimal128(quote.subtotal),
            "tax_total": to_decimal128(quote.tax_total),
            "total": to_decimal128(quote.total),
            "supplier_count": len(groups_out),
            "groups": groups_out,
            "payment_id": payment_id,
            "payment_reference": payment_reference,
            "notes": notes,
            "status_history": [
                {"status": CheckoutStatus.AWAITING_PAYMENT, "note": "Checkout placed", "changed_at": now}
            ],
            "paid_at": None,
            "cancelled_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await _col(CollectionName.CHECKOUTS).insert_one(checkout, session=session)
        return checkout

    async def _after_place(self, checkout: dict[str, Any], *, user_id: str, ip: str | None) -> None:
        await _audit(
            "CHECKOUT_PLACED",
            resource_type="checkout",
            resource_id=checkout["_id"],
            business_id=checkout["buyer_business_id"],
            user_id=user_id,
            metadata={
                "checkout_number": checkout["checkout_number"],
                "payment_method": checkout["payment_method"],
                "total": _money_str(checkout["total"]),
                "currency": checkout["currency"],
                "orders": [g["order_number"] for g in checkout["groups"]],
                "ip": ip,
            },
        )
        for group in checkout["groups"]:
            await event_bus.publish(DomainEvent(name=ORDER_CREATED, payload={"order_id": str(group["order_id"])}))
        if checkout["payment_method"] == PaymentMethod.CASH:
            for group in checkout["groups"]:
                await _notify(
                    recipient_business_id=group["supplier_business_id"],
                    type="ORDER_CREATED",
                    title=f"New order {group['order_number']} — cash on delivery",
                    message="A buyer placed an order. Confirm it in TradeBay to start fulfilment. Cash is collected on delivery.",
                    reference_type="order",
                    reference_id=group["order_id"],
                )

    async def _ensure_intent(self, checkout: dict[str, Any]) -> str | None:
        pay = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout["payment_id"]})
        if pay is None or pay["status"] not in {PaymentStatus.PENDING, PaymentStatus.FAILED}:
            return None
        gateway = get_payment_gateway()
        try:
            if pay.get("provider_payment_id"):
                intent = await gateway.retrieve_intent(pay["provider_payment_id"])
                if intent.status != "canceled":
                    return intent.client_secret
            intent = await gateway.create_intent(
                amount_minor=to_minor_units(money(pay["amount"])),
                currency=pay.get("currency") or "USD",
                idempotency_key=f"tradebay-payment-{pay['_id']}",
                metadata={
                    "payment_id": str(pay["_id"]),
                    "checkout_id": str(checkout["_id"]),
                    "checkout_number": checkout["checkout_number"],
                    "description": f"TradeBay {checkout['checkout_number']}",
                },
            )
        except PaymentGatewayError as exc:
            await _col(CollectionName.PAYMENTS).update_one(
                {"_id": pay["_id"]},
                {"$set": {"failure_code": "provider_unavailable", "failure_message": exc.message, "updated_at": utc_now()}},
            )
            return None
        await _col(CollectionName.PAYMENTS).update_one(
            {"_id": pay["_id"], "$or": [{"provider_payment_id": None}, {"provider_payment_id": {"$exists": False}}, {"provider_payment_id": pay.get("provider_payment_id")}]},
            {"$set": {"provider_payment_id": intent.id, "failure_code": None, "failure_message": None, "updated_at": utc_now()}},
        )
        return intent.client_secret

    async def _placed_response(self, checkout: dict[str, Any], *, business: dict[str, Any] | None, replay: bool) -> dict[str, Any]:
        payload = await self.serialize(checkout, business=business)
        payload["idempotent_replay"] = replay
        return payload

                                                                              

    async def list(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        btype = str(business.get("type"))
        query: dict[str, Any]
        if btype == BusinessAccountType.BUYER:
            query = {"buyer_business_id": parse_object_id(str(business["_id"]))}
        elif btype == BusinessAccountType.PLATFORM:
            query = {}
        else:
            raise ForbiddenError("Checkouts belong to buyers")
        if status:
            query["status"] = status
        col = _col(CollectionName.CHECKOUTS)
        total = await col.count_documents(query)
        rows = await col.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
        return [await self.serialize(r, business=business, include_lines=False) for r in rows], total

    async def get(self, *, business: dict[str, Any] | None, checkout_id: str) -> dict[str, Any]:
        return await self.serialize(await self._get_checkout(checkout_id, business), business=business)

    async def serialize(
        self, checkout: dict[str, Any], *, business: dict[str, Any] | None, include_lines: bool = True
    ) -> dict[str, Any]:
        order_ids = [g["order_id"] for g in checkout.get("groups") or []]
        orders = {o["_id"]: o async for o in _col(CollectionName.ORDERS).find({"_id": {"$in": order_ids}})}
        invoices = {
            i["order_id"]: i async for i in _col(CollectionName.CUSTOMER_INVOICES).find({"order_id": {"$in": order_ids}})
        }
        items_by_order: dict[Any, list[dict[str, Any]]] = {}
        if include_lines:
            async for item in _col(CollectionName.ORDER_ITEMS).find({"order_id": {"$in": order_ids}}):
                items_by_order.setdefault(item["order_id"], []).append(item)
        pay = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout.get("payment_id")}) if checkout.get("payment_id") else None

        groups = []
        active_total = Decimal("0")
        for g in checkout.get("groups") or []:
            order = orders.get(g["order_id"]) or {}
            invoice = invoices.get(g["order_id"]) or {}
            if order.get("status") != OrderStatus.CANCELLED:
                active_total += as_decimal(g.get("total"))
            entry: dict[str, Any] = {
                "order_id": str(g["order_id"]),
                "order_number": g.get("order_number"),
                "order_status": order.get("status"),
                "payment_status": order.get("payment_status"),
                "supplier_business_id": str(g["supplier_business_id"]),
                "supplier_name": g.get("supplier_name"),
                "subtotal": _money_str(g.get("subtotal")),
                "tax_total": _money_str(g.get("tax_total")),
                "total": _money_str(g.get("total")),
                "line_count": g.get("line_count"),
                "invoice": {
                    "id": str(invoice["_id"]),
                    "invoice_number": invoice.get("invoice_number"),
                    "status": invoice.get("status"),
                    "total": _money_str(invoice.get("total")),
                }
                if invoice
                else None,
            }
            if include_lines:
                entry["lines"] = [
                    {
                        "product_id": str(i["product_id"]) if i.get("product_id") else None,
                        "product_name": i.get("product_name_snapshot"),
                        "sku": i.get("sku_snapshot"),
                        "quantity": format(as_decimal(i.get("quantity")).normalize(), "f"),
                        "unit": i.get("unit"),
                        "unit_price": _money_str(i.get("unit_price")),
                        "line_total": _money_str(i.get("line_total")),
                        "image_url": i.get("image_url_snapshot"),
                    }
                    for i in items_by_order.get(g["order_id"], [])
                ]
            groups.append(entry)

        payment = None
        if pay:
            names = {str(g["invoice_id"]): (g.get("supplier_name"), g.get("invoice_number")) for g in checkout.get("groups") or []}
            payment = {
                "id": str(pay["_id"]),
                "payment_reference": pay.get("payment_reference"),
                "status": pay.get("status"),
                "method": pay.get("payment_method"),
                "provider": pay.get("provider"),
                "amount": _money_str(pay.get("amount")),
                "currency": pay.get("currency"),
                "failure_message": pay.get("failure_message"),
                "receipt_number": pay.get("receipt_number"),
                "paid_at": _iso(pay.get("paid_at")),
                "requires_attention": bool(pay.get("requires_attention")),
                "allocations": [
                    {
                        "invoice_id": str(a["invoice_id"]),
                        "invoice_number": names.get(str(a["invoice_id"]), (None, None))[1],
                        "supplier_name": names.get(str(a["invoice_id"]), (None, None))[0],
                        "amount": _money_str(a.get("allocated_amount")),
                    }
                    for a in pay.get("allocations") or []
                ],
            }

        is_card_pending = (
            checkout.get("payment_method") == PaymentMethod.CARD
            and checkout.get("status") == CheckoutStatus.AWAITING_PAYMENT
        )
        return {
            "id": str(checkout["_id"]),
            "checkout_number": checkout.get("checkout_number"),
            "status": checkout.get("status"),
            "payment_method": checkout.get("payment_method"),
            "currency": checkout.get("currency"),
            "subtotal": _money_str(checkout.get("subtotal")),
            "tax_total": _money_str(checkout.get("tax_total")),
            "total": _money_str(checkout.get("total")),
            "active_total": format(money(active_total), "f"),
            "supplier_count": checkout.get("supplier_count"),
            "split_notice": _split_notice(int(checkout.get("supplier_count") or 0)),
            "notes": checkout.get("notes"),
            "buyer_business_id": str(checkout["buyer_business_id"]),
            "orders": groups,
            "payment": payment,
            "card_publishable_key": get_payment_gateway().publishable_key() if is_card_pending else None,
            "status_history": [
                {"status": h.get("status"), "note": h.get("note"), "changed_at": _iso(h.get("changed_at"))}
                for h in checkout.get("status_history") or []
            ],
            "created_at": _iso(checkout.get("created_at")),
            "paid_at": _iso(checkout.get("paid_at")),
            "cancelled_at": _iso(checkout.get("cancelled_at")),
        }

                                                                               

    async def start_card_payment(self, *, business: dict[str, Any] | None, checkout_id: str) -> dict[str, Any]:
        self._require_buyer(business)
        checkout = await self._get_checkout(checkout_id, business)
        if checkout["payment_method"] != PaymentMethod.CARD:
            raise BadRequestError("This checkout is paid in cash on delivery")
        if checkout["status"] != CheckoutStatus.AWAITING_PAYMENT:
            raise ConflictError("This checkout is no longer awaiting payment")
        secret = await self._ensure_intent(checkout)
        if not secret:
            pay = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout["payment_id"]})
            raise BadRequestError((pay or {}).get("failure_message") or "Couldn't start the card payment. Try again.")
        return {
            "client_secret": secret,
            "publishable_key": get_payment_gateway().publishable_key(),
            "checkout": await self.serialize(checkout, business=business),
        }

    async def refresh_payment(self, *, business: dict[str, Any] | None, checkout_id: str) -> dict[str, Any]:
        checkout = await self._get_checkout(checkout_id, business)
        pay = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout["payment_id"]})
        if pay and pay.get("payment_method") == PaymentMethod.CARD and pay["status"] in {
            PaymentStatus.PENDING,
            PaymentStatus.FAILED,
        }:
            try:
                await sync_card_payment(pay)
            except PaymentGatewayError:
                logger.warning("stripe_sync_failed", checkout=str(checkout["_id"]))
        fresh = await _col(CollectionName.CHECKOUTS).find_one({"_id": checkout["_id"]})
        return await self.serialize(fresh or checkout, business=business)

                                                                               

    async def cancel(
        self, *, user_id: str, business: dict[str, Any] | None, checkout_id: str, reason: str | None
    ) -> dict[str, Any]:
        checkout = await self._get_checkout(checkout_id, business)
        if str((business or {}).get("type")) == BusinessAccountType.BUYER:
            self._require_buyer(business)
        pay = await _col(CollectionName.PAYMENTS).find_one({"_id": checkout["payment_id"]})
        if pay and pay.get("provider") == PaymentProvider.STRIPE and pay.get("provider_payment_id"):
                                                                                                   
            gateway = get_payment_gateway()
            intent = await gateway.retrieve_intent(pay["provider_payment_id"])
            if intent.status == "succeeded":
                await sync_card_payment(pay)
                raise ConflictError("Your card payment already went through, so this checkout can't be cancelled.")
            if intent.status != "canceled":
                await gateway.cancel_intent(pay["provider_payment_id"])
        text = (reason or "").strip()[:300] or "Cancelled by buyer"

        async def _work(session: MongoSession) -> bool:
            return await cancel_checkout_in_session(checkout, user_id=user_id, reason=text, session=session)

        changed = await run_in_transaction(_work)
        if changed:
            await _audit(
                "CHECKOUT_CANCELLED",
                resource_type="checkout",
                resource_id=checkout["_id"],
                business_id=checkout["buyer_business_id"],
                user_id=user_id,
                metadata={"checkout_number": checkout["checkout_number"], "reason": text},
            )
            if checkout["payment_method"] == PaymentMethod.CASH:
                for g in checkout["groups"]:
                    await _notify(
                        recipient_business_id=g["supplier_business_id"],
                        type="ORDER_CANCELLED",
                        title=f"Order {g['order_number']} was cancelled",
                        message="The buyer cancelled before you confirmed. Reserved stock was released.",
                        reference_type="order",
                        reference_id=g["order_id"],
                    )
        fresh = await _col(CollectionName.CHECKOUTS).find_one({"_id": checkout["_id"]})
        return await self.serialize(fresh or checkout, business=business)

    async def cancel_order(
        self, *, user_id: str, business: dict[str, Any] | None, order_id: str, reason: str | None
    ) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        if not is_valid_object_id(order_id):
            raise NotFoundError("Purchase order not found")
        order = await _col(CollectionName.ORDERS).find_one({"_id": ObjectId(order_id)})
        if order is None:
            raise NotFoundError("Purchase order not found")
        btype = str(business.get("type"))
        bid = str(business["_id"])
        if btype == BusinessAccountType.BUYER:
            if str(order["buyer_business_id"]) != bid:
                raise NotFoundError("Purchase order not found")
            if order["status"] != OrderStatus.PENDING:
                raise ConflictError("You can cancel only before the supplier confirms the order")
            default_reason = "Cancelled by buyer"
        elif btype == BusinessAccountType.SUPPLIER:
            if str(order["supplier_business_id"]) != bid or order["status"] == OrderStatus.AWAITING_PAYMENT:
                raise NotFoundError("Purchase order not found")
            if order["status"] != OrderStatus.PENDING:
                raise ConflictError("Only a new order can be declined. Open a dispute for confirmed orders.")
            default_reason = "Declined by supplier"
        elif btype == BusinessAccountType.PLATFORM:
            default_reason = "Cancelled by TradeBay"
        else:
            raise ForbiddenError()
        if order["status"] == OrderStatus.AWAITING_PAYMENT:
            raise ConflictError("This order is waiting for card payment. Cancel the whole checkout instead.")
        text = (reason or "").strip()[:300] or default_reason

        async def _work(session: MongoSession) -> None:
            fresh = await _col(CollectionName.ORDERS).find_one({"_id": order["_id"]}, session=session)
            assert fresh is not None
            await cancel_order_in_session(fresh, user_id=user_id, reason=text, session=session)
            if not fresh.get("checkout_id"):
                return
            checkout = await _col(CollectionName.CHECKOUTS).find_one({"_id": fresh["checkout_id"]}, session=session)
            pay = await _col(CollectionName.PAYMENTS).find_one({"_id": (checkout or {}).get("payment_id")}, session=session)
            invoice = await _col(CollectionName.CUSTOMER_INVOICES).find_one({"order_id": fresh["_id"]}, session=session)
            if pay and invoice:
                pay = await remove_allocation_in_session(pay, invoice_id=invoice["_id"], reason=text, session=session)
            remaining = await _col(CollectionName.ORDERS).count_documents(
                {"checkout_id": fresh["checkout_id"], "status": {"$ne": OrderStatus.CANCELLED}}, session=session
            )
            if checkout and remaining == 0 and checkout["status"] == CheckoutStatus.AWAITING_PAYMENT:
                now = utc_now()
                await _col(CollectionName.CHECKOUTS).update_one(
                    {"_id": checkout["_id"], "status": CheckoutStatus.AWAITING_PAYMENT},
                    {
                        "$set": {"status": CheckoutStatus.CANCELLED, "cancelled_at": now, "updated_at": now},
                        "$push": {"status_history": {"status": CheckoutStatus.CANCELLED, "note": "All orders cancelled", "changed_at": now}},
                    },
                    session=session,
                )

        await run_in_transaction(_work)
        await _audit(
            "ORDER_CANCELLED",
            resource_type="order",
            resource_id=order["_id"],
            business_id=business["_id"],
            user_id=user_id,
            metadata={"order_number": order.get("order_number"), "reason": text, "by": btype},
        )
        counterparty = order["supplier_business_id"] if btype != BusinessAccountType.SUPPLIER else order["buyer_business_id"]
        await _notify(
            recipient_business_id=counterparty,
            type="ORDER_CANCELLED",
            title=f"Order {order.get('order_number')} was cancelled",
            message=f"{text}. Any reserved stock was released and the invoice was voided.",
            reference_type="order",
            reference_id=order["_id"],
        )
        if btype == BusinessAccountType.PLATFORM:
            await _notify(
                recipient_business_id=order["buyer_business_id"],
                type="ORDER_CANCELLED",
                title=f"Order {order.get('order_number')} was cancelled",
                message=text,
                reference_type="order",
                reference_id=order["_id"],
            )
        return {"order_id": order_id, "status": OrderStatus.CANCELLED}
