
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.db.transactions import run_in_transaction
from app.modules.identity.constants import BusinessAccountType
from app.modules.platform_money.commission import as_decimal, compute_split, money
from app.modules.platform_money.constants import (
    PAYOUT_STATUS_TRANSITIONS,
    CommissionBase,
    CommissionStatus,
    FundsState,
    PayableStatus,
    PayoutStatus,
    PlatformLedgerStatus,
    PlatformTransactionType,
    assert_platform_transition,
)
from app.modules.settings.constants import SINGLETON_KEY
from app.modules.settings.numbering import allocate_seeded_number
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import is_valid_object_id, parse_object_id


def _story_stages(
    *,
    kind: str,
    state: str,
    buyer_paid: Decimal,
    commission: Decimal,
    earnings: Decimal,
    released: bool,
    paid: Decimal,
) -> list[dict[str, Any]]:
    if kind == PlatformTransactionType.SUPPLIER_PAYOUT:
        return [
            {"key": "payout", "label": "Supplier payout", "done": True, "current": True, "amount": format(paid or buyer_paid, "f")},
        ]
    if kind == PlatformTransactionType.REFUND:
        return [
            {"key": "refund", "label": "Refund", "done": True, "current": True, "amount": format(buyer_paid, "f")},
        ]
    steps = [
        ("buyer_paid", "Buyer paid", True, format(buyer_paid, "f")),
        ("commission", "Commission recognized", commission > 0 or True, format(commission, "f")),
        ("earnings", "Supplier earnings", True, format(earnings, "f")),
        ("held", "Funds held", True, format(earnings, "f")),
        ("released", "Funds released", released, format(earnings, "f") if released else None),
        ("payout", "Supplier payout", paid > 0 and state == "paid", format(paid, "f") if paid > 0 else None),
    ]
    current = "payout" if state == "paid" else "released" if state == "ready" else "held"
    out = []
    for key, label, done, amount in steps:
        out.append({"key": key, "label": label, "done": bool(done) and (key != "released" or released) and (key != "payout" or state == "paid"), "current": key == current, "amount": amount})
    return out

def _money_out(value: Any) -> str | None:
    if value is None:
        return None
    return format(money(value), "f")

async def _next_number(
    prefix: str,
    collection: str,
    field: str,
    *,
    session: MongoSession = None,
) -> str:
    return await allocate_seeded_number(prefix, collection, field, session=session)

async def _post_platform_tx(
    *,
    type_: str,
    amount: Decimal,
    currency: str,
    funds_state: str,
    reference_type: str,
    reference_id: ObjectId,
    idempotency_key: str,
    order_id: ObjectId | None = None,
    payment_id: ObjectId | None = None,
    supplier_business_id: ObjectId | None = None,
    provider: str | None = None,
    provider_transaction_id: str | None = None,
    provider_event_id: str | None = None,
    description: str | None = None,
    session: MongoSession = None,
) -> dict[str, Any]:
    if amount <= 0:
        raise BadRequestError("Platform transaction amount must be positive")
    existing = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
        {"idempotency_key": idempotency_key}, session=session
    )
    if existing:
        return existing

    now = utc_now()
    row = {
        "_id": ObjectId(),
        "transaction_number": await _next_number(
            "PTX", CollectionName.PLATFORM_TRANSACTIONS, "transaction_number", session=session
        ),
        "type": type_,
        "amount": to_decimal128(money(amount)),
        "currency": currency,
        "funds_state": funds_state,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "order_id": order_id,
        "payment_id": payment_id,
        "supplier_business_id": supplier_business_id,
        "status": PlatformLedgerStatus.POSTED,
        "idempotency_key": idempotency_key,
        "provider": provider,
        "description": description,
        "reverses_transaction_id": None,
        "posted_at": now,
        "created_at": now,
    }
    if provider_transaction_id:
        row["provider_transaction_id"] = provider_transaction_id
    if provider_event_id:
        row["provider_event_id"] = provider_event_id
    try:
        await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).insert_one(
            row, session=session
        )
    except DuplicateKeyError:
        existing = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
            {"idempotency_key": idempotency_key}, session=session
        )
        if existing:
            return existing
        raise
    return row

async def create_commission_and_payable_for_order(*, order: dict[str, Any]) -> dict[str, Any] | None:

    async def _work(session: MongoSession) -> dict[str, Any]:
        return await create_commission_in_session(order=order, session=session)

    return await run_in_transaction(_work)

class CommissionNotConfiguredError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "Platform commission isn't configured. Ask a TradeBay admin to set it in Settings."
        )

async def load_commission_policy(*, session: MongoSession = None) -> dict[str, Any]:
    settings = await mongo_manager.collection(CollectionName.PLATFORM_SETTINGS).find_one(
        {"key": SINGLETON_KEY}, session=session
    )
    if not settings or settings.get("commission_rate") is None:
        raise CommissionNotConfiguredError()
    return {
        "rate": as_decimal(settings["commission_rate"]),
        "base": settings.get("commission_base") or CommissionBase.ORDER_TOTAL,
        "type": settings.get("commission_type") or "percentage",
    }

async def create_commission_in_session(
    *, order: dict[str, Any], session: MongoSession
) -> dict[str, Any]:
    order_id = order["_id"]
    existing = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
        {"order_id": order_id}, session=session
    )
    if existing:
        return existing

    policy = await load_commission_policy(session=session)
    base_key = policy["base"]
    base_amount = (
        order.get("subtotal") if base_key == CommissionBase.ORDER_SUBTOTAL else order.get("total")
    )
    split = compute_split(
        order_total=order.get("total"),
        base_amount=base_amount,
        rate=policy["rate"],
        commission_type=policy["type"],
    )
    now = utc_now()
    commission = {
        "_id": ObjectId(),
        "order_id": order_id,
        "checkout_id": order.get("checkout_id"),
        "supplier_business_id": order["supplier_business_id"],
        "payment_id": None,
        "base_amount": to_decimal128(split["base_amount"]),
        "rate": to_decimal128(split["rate"]),
        "commission_type": policy["type"],
        "commission_base": base_key,
        "gross_amount": to_decimal128(split["gross"]),
        "commission_amount": to_decimal128(split["commission_amount"]),
        "net_amount": to_decimal128(split["net_payable"]),
        "currency": order.get("currency") or "USD",
        "status": CommissionStatus.PENDING,
        "recognized_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).insert_one(
        commission, session=session
    )
    payable_number = await _next_number(
        "AP", CollectionName.SUPPLIER_PAYABLES, "payable_number", session=session
    )
    await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).insert_one(
        {
            "_id": ObjectId(),
            "payable_number": payable_number,
            "supplier_business_id": order["supplier_business_id"],
            "order_id": order_id,
            "checkout_id": order.get("checkout_id"),
            "commission_record_id": commission["_id"],
            "gross_amount": to_decimal128(split["gross"]),
            "commission_amount": to_decimal128(split["commission_amount"]),
            "adjustment_amount": to_decimal128(Decimal("0")),
            "net_payable_amount": to_decimal128(split["net_payable"]),
            "currency": order.get("currency") or "USD",
            "status": PayableStatus.OPEN,
            "created_at": now,
            "updated_at": now,
        },
        session=session,
    )
    return commission

async def record_checkout_payment_in_session(
    *,
    payment: dict[str, Any],
    invoices: dict[ObjectId, dict[str, Any]],
    provider_event_id: str | None,
    session: MongoSession,
) -> None:
    from app.modules.platform_money.supplier_ledger import post_sale_entries

    payment_id = payment["_id"]
    currency = payment.get("currency") or "USD"
    provider = payment.get("provider") or "manual"
    now = utc_now()
    for alloc in payment.get("allocations") or []:
        invoice = invoices[alloc["invoice_id"]]
        order_id = invoice["order_id"]
        allocated = money(alloc.get("allocated_amount"))
        key = f"pay:{payment_id}:inv:{invoice['_id']}"
        await _post_platform_tx(
            type_=PlatformTransactionType.BUYER_PAYMENT,
            amount=allocated,
            currency=currency,
            funds_state=FundsState.HELD,
            reference_type="payment",
            reference_id=payment_id,
            idempotency_key=f"{key}:{PlatformTransactionType.BUYER_PAYMENT}",
            order_id=order_id,
            payment_id=payment_id,
            supplier_business_id=invoice.get("supplier_business_id"),
            provider=provider,
            provider_transaction_id=payment.get("provider_payment_id"),
            provider_event_id=provider_event_id,
            description=f"Buyer payment {payment.get('payment_reference')} held for {invoice.get('invoice_number')}",
            session=session,
        )
        commission = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
            {"order_id": order_id}, session=session
        )
        if commission is None:
            raise BadRequestError("Commission snapshot missing for this order")
        fee = money(commission.get("commission_amount"))
        if fee > 0:
            await _post_platform_tx(
                type_=PlatformTransactionType.PLATFORM_FEE,
                amount=fee,
                currency=commission.get("currency") or currency,
                funds_state=FundsState.HELD,
                reference_type="commission_record",
                reference_id=commission["_id"],
                idempotency_key=f"{key}:{PlatformTransactionType.PLATFORM_FEE}",
                order_id=order_id,
                payment_id=payment_id,
                supplier_business_id=commission.get("supplier_business_id"),
                provider=provider,
                provider_event_id=provider_event_id,
                description=f"Platform fee for {invoice.get('invoice_number')}",
                session=session,
            )
        await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).update_one(
            {"_id": commission["_id"], "status": CommissionStatus.PENDING},
            {
                "$set": {
                    "status": CommissionStatus.RECOGNIZED,
                    "payment_id": payment_id,
                    "recognized_at": now,
                    "updated_at": now,
                }
            },
            session=session,
        )
        await post_sale_entries(
            supplier_business_id=commission["supplier_business_id"],
            order_id=order_id,
            invoice=invoice,
            payment=payment,
            commission=commission,
            session=session,
        )

async def cancel_commission_in_session(*, order_id: ObjectId, session: MongoSession) -> None:
    now = utc_now()
    await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).update_one(
        {"order_id": order_id, "status": CommissionStatus.PENDING},
        {"$set": {"status": CommissionStatus.REVERSED, "updated_at": now}},
        session=session,
    )
    await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).update_many(
        {"order_id": order_id, "status": PayableStatus.OPEN},
        {"$set": {"status": PayableStatus.CANCELLED, "updated_at": now}},
        session=session,
    )

class PlatformMoneyService:

    def _require_business(self, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        return business

                                                                            

    async def on_buyer_payment_completed(
        self,
        *,
        payment: dict[str, Any],
        invoice: dict[str, Any],
        provider: str | None = None,
        provider_transaction_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> dict[str, Any]:
        payment_id = payment["_id"]
        order_id = invoice.get("order_id")
        amount = money(payment.get("amount"))
        currency = payment.get("currency") or invoice.get("currency") or "USD"
        event = provider_event_id or f"payment:{payment_id}"

        async def _work(session: MongoSession) -> dict[str, Any]:
            pay_tx = await _post_platform_tx(
                type_=PlatformTransactionType.BUYER_PAYMENT,
                amount=amount,
                currency=currency,
                funds_state=FundsState.HELD,
                reference_type="payment",
                reference_id=payment_id,
                idempotency_key=f"manual:{event}:{PlatformTransactionType.BUYER_PAYMENT}",
                order_id=order_id,
                payment_id=payment_id,
                provider=provider or payment.get("provider") or "manual",
                provider_transaction_id=provider_transaction_id,
                provider_event_id=provider_event_id,
                description=f"Buyer payment {payment.get('payment_reference')} held",
                session=session,
            )

            commission = None
            if order_id:
                commission = await mongo_manager.collection(
                    CollectionName.COMMISSION_RECORDS
                ).find_one({"order_id": order_id}, session=session)
            if commission:
                fee_amt = money(commission.get("commission_amount"))
                if fee_amt > 0:
                    await _post_platform_tx(
                        type_=PlatformTransactionType.PLATFORM_FEE,
                        amount=fee_amt,
                        currency=commission.get("currency") or currency,
                        funds_state=FundsState.HELD,
                        reference_type="commission_record",
                        reference_id=commission["_id"],
                        idempotency_key=f"manual:{event}:{PlatformTransactionType.PLATFORM_FEE}",
                        order_id=order_id,
                        payment_id=payment_id,
                        supplier_business_id=commission.get("supplier_business_id"),
                        provider=provider or "manual",
                        provider_event_id=provider_event_id,
                        description="Platform fee reserved from buyer payment",
                        session=session,
                    )
                now = utc_now()
                await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).update_one(
                    {"_id": commission["_id"], "status": CommissionStatus.PENDING},
                    {
                        "$set": {
                            "status": CommissionStatus.RECOGNIZED,
                            "payment_id": payment_id,
                            "recognized_at": now,
                            "updated_at": now,
                        }
                    },
                    session=session,
                )
            return {"buyer_payment": pay_tx, "commission_id": str(commission["_id"]) if commission else None}

        return await run_in_transaction(_work)

                                                                            

    async def _find_order(self, order_ref: str) -> dict[str, Any]:
        raw = (order_ref or "").strip()
        if not raw:
            raise BadRequestError("Order is required")
        orders = mongo_manager.collection(CollectionName.ORDERS)
        if is_valid_object_id(raw):
            order = await orders.find_one({"_id": ObjectId(raw)})
            if order is not None:
                return order
        order = await orders.find_one({"order_number": raw})
        if order is None:
            raise NotFoundError("Order not found")
        return order

    async def release_funds_for_order(
        self, *, order_id: str, user_id: str | None = None
    ) -> dict[str, Any]:
        order = await self._find_order(order_id)
        oid = order["_id"]
        payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"order_id": oid}
        )
        if payable is None:
            raise BadRequestError("No supplier payable for this order")
        if payable.get("status") == PayableStatus.SETTLED:
            return {"status": "already_settled", "payable_id": str(payable["_id"])}

                                                     
        held = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
            {
                "order_id": oid,
                "type": PlatformTransactionType.BUYER_PAYMENT,
                "funds_state": FundsState.HELD,
                "status": PlatformLedgerStatus.POSTED,
            }
        )
        released_already = await mongo_manager.collection(
            CollectionName.PLATFORM_TRANSACTIONS
        ).find_one(
            {
                "order_id": oid,
                "type": PlatformTransactionType.FUNDS_RELEASED,
                "status": PlatformLedgerStatus.POSTED,
            }
        )
        if released_already and not held:
                                               
            payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
                {"supplier_payable_id": payable["_id"]}
            )
            return {
                "status": "already_released",
                "payout_id": str(payout["_id"]) if payout else None,
            }
        if not held and not released_already:
            raise BadRequestError("Cannot release funds before a completed buyer payment is held")

        net = money(payable.get("net_payable_amount"))
        if net <= 0:
            raise BadRequestError("Nothing to release for supplier")

        async def _work(session: MongoSession) -> dict[str, Any]:
            event = f"release:{order_id}"
            release_tx = await _post_platform_tx(
                type_=PlatformTransactionType.FUNDS_RELEASED,
                amount=net,
                currency=payable.get("currency") or "USD",
                funds_state=FundsState.RELEASED,
                reference_type="supplier_payable",
                reference_id=payable["_id"],
                idempotency_key=f"manual:{event}:{PlatformTransactionType.FUNDS_RELEASED}",
                order_id=oid,
                supplier_business_id=payable["supplier_business_id"],
                description=f"Funds released for order {order.get('order_number')}",
                session=session,
            )
                                                                                                    
                                                        
            from app.modules.platform_money.supplier_ledger import post_release_entries

            await post_release_entries(payable=payable, order=order, session=session)

            existing_payout = await mongo_manager.collection(
                CollectionName.SUPPLIER_PAYOUTS
            ).find_one({"supplier_payable_id": payable["_id"]}, session=session)
            if existing_payout:
                return {
                    "status": "released",
                    "release_transaction_id": str(release_tx["_id"]),
                    "payout_id": str(existing_payout["_id"]),
                    "payout_status": existing_payout.get("status"),
                }

            now = utc_now()
            payout_number = await _next_number(
                "POUT", CollectionName.SUPPLIER_PAYOUTS, "payout_number", session=session
            )
            payout = {
                "_id": ObjectId(),
                "payout_number": payout_number,
                "settlement_batch_id": None,
                "supplier_business_id": payable["supplier_business_id"],
                "supplier_payable_id": payable["_id"],
                "gross_amount": payable.get("gross_amount"),
                "platform_fee_amount": payable.get("commission_amount"),
                "adjustment_amount": payable.get("adjustment_amount")
                or to_decimal128(Decimal("0")),
                "net_amount": to_decimal128(net),
                "currency": payable.get("currency") or "USD",
                "status": PayoutStatus.PENDING,
                "provider": "manual",
                "idempotency_key": f"payout:payable:{payable['_id']}",
                "failure_reason": None,
                "processing_at": None,
                "completed_at": None,
                "failed_at": None,
                "created_at": now,
                "updated_at": now,
            }
            try:
                await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).insert_one(
                    payout, session=session
                )
            except DuplicateKeyError:
                existing_payout = await mongo_manager.collection(
                    CollectionName.SUPPLIER_PAYOUTS
                ).find_one({"idempotency_key": payout["idempotency_key"]}, session=session)
                if existing_payout:
                    payout = existing_payout
                else:
                    raise
            return {
                "status": "released",
                "release_transaction_id": str(release_tx["_id"]),
                "payout_id": str(payout["_id"]),
                "payout_status": payout.get("status"),
                "released_by": user_id,
            }

        return await run_in_transaction(_work)

    async def process_payout(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payout_id: str,
        provider: str | None = None,
        provider_transaction_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Only platform can process supplier payouts")
        payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
            {"_id": parse_object_id(payout_id)}
        )
        if payout is None:
            raise NotFoundError("Payout not found")
        if payout.get("status") == PayoutStatus.COMPLETED:
            return self._serialize_payout(payout)

        current = str(payout.get("status"))
        if current == PayoutStatus.PENDING:
            assert_platform_transition(
                PAYOUT_STATUS_TRANSITIONS, current, PayoutStatus.PROCESSING, label="payout"
            )
            now = utc_now()
            await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).update_one(
                {"_id": payout["_id"]},
                {
                    "$set": {
                        "status": PayoutStatus.PROCESSING,
                        "processing_at": now,
                        "updated_at": now,
                    }
                },
            )
            current = PayoutStatus.PROCESSING

        assert_platform_transition(
            PAYOUT_STATUS_TRANSITIONS, current, PayoutStatus.COMPLETED, label="payout"
        )

        payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"_id": payout["supplier_payable_id"]}
        )
        if payable is None:
            raise NotFoundError("Payable not found")
        net = money(payout.get("net_amount"))
                                              
        if net > money(payable.get("net_payable_amount")) + Decimal("0.001"):
            raise BadRequestError("Payout exceeds payable amount")

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            event = provider_event_id or f"payout:{payout_id}"
            await _post_platform_tx(
                type_=PlatformTransactionType.SUPPLIER_PAYOUT,
                amount=net,
                currency=payout.get("currency") or "USD",
                funds_state=FundsState.RELEASED,
                reference_type="supplier_payout",
                reference_id=payout["_id"],
                idempotency_key=f"manual:{event}:{PlatformTransactionType.SUPPLIER_PAYOUT}",
                order_id=payable.get("order_id"),
                supplier_business_id=payout["supplier_business_id"],
                provider=provider or payout.get("provider") or "manual",
                provider_transaction_id=provider_transaction_id,
                provider_event_id=provider_event_id,
                description=f"Payout {payout.get('payout_number')} completed",
                session=session,
            )
            updates: dict[str, Any] = {
                "status": PayoutStatus.COMPLETED,
                "completed_at": now,
                "updated_at": now,
                "provider": provider or payout.get("provider") or "manual",
            }
            if provider_transaction_id:
                updates["provider_transaction_id"] = provider_transaction_id
            if provider_event_id:
                updates["provider_event_id"] = provider_event_id
            await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).update_one(
                {"_id": payout["_id"]}, {"$set": updates}, session=session
            )
            await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).update_one(
                {"_id": payable["_id"]},
                {"$set": {"status": PayableStatus.SETTLED, "updated_at": now}},
                session=session,
            )
            from app.modules.platform_money.supplier_ledger import post_payout_entry

            await post_payout_entry(payout=payout, session=session)
            refreshed = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
                {"_id": payout["_id"]}, session=session
            )
            assert refreshed is not None
            return self._serialize_payout(refreshed)

        return await run_in_transaction(_work)

    async def fail_payout(
        self,
        *,
        business: dict[str, Any] | None,
        payout_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Only platform can fail payouts")
        payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
            {"_id": parse_object_id(payout_id)}
        )
        if payout is None:
            raise NotFoundError("Payout not found")
        assert_platform_transition(
            PAYOUT_STATUS_TRANSITIONS,
            str(payout.get("status")),
            PayoutStatus.FAILED,
            label="payout",
        )
        now = utc_now()
        await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).update_one(
            {"_id": payout["_id"]},
            {
                "$set": {
                    "status": PayoutStatus.FAILED,
                    "failure_reason": (reason or "Payout failed").strip(),
                    "failed_at": now,
                    "updated_at": now,
                }
            },
        )
        refreshed = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
            {"_id": payout["_id"]}
        )
        assert refreshed is not None
        return self._serialize_payout(refreshed)

    async def settle_payable(
        self, *, user_id: str, business: dict[str, Any] | None, payable_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Only platform can settle supplier payables")
        payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"_id": parse_object_id(payable_id)}
        )
        if payable is None:
            raise NotFoundError("Payable not found")
        if payable.get("status") == PayableStatus.SETTLED:
            payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
                {"supplier_payable_id": payable["_id"], "status": PayoutStatus.COMPLETED}
            )
            return {
                "payable": self._serialize_payable(payable),
                "payout": self._serialize_payout(payout) if payout else None,
            }

        await self.release_funds_for_order(
            order_id=str(payable["order_id"]), user_id=user_id
        )
        payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
            {"supplier_payable_id": payable["_id"]}
        )
        if payout is None:
            raise BadRequestError("Payout was not created after release")
        if payout.get("status") != PayoutStatus.COMPLETED:
            await self.process_payout(
                user_id=user_id, business=business, payout_id=str(payout["_id"])
            )
            payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
                {"_id": payout["_id"]}
            )
        refreshed = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"_id": payable["_id"]}
        )
        assert refreshed is not None and payout is not None
        return {
            "payable": self._serialize_payable(refreshed),
            "payout": self._serialize_payout(payout),
        }

    async def on_customer_refund(
        self,
        *,
        refund: dict[str, Any],
        payment: dict[str, Any],
        invoice: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if refund.get("status") != "processed":
            return None
        refund_id = refund["_id"]
        amount = money(refund.get("amount"))
        order_id = refund.get("order_id") or (invoice.get("order_id") if invoice else None)
        currency = refund.get("currency") or "USD"
        event = f"refund:{refund_id}"

        async def _work(session: MongoSession) -> dict[str, Any]:
            supplier_id = None
            if order_id:
                payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
                    {"order_id": order_id}, session=session
                )
                if payable:
                    supplier_id = payable.get("supplier_business_id")
            else:
                payable = None

            tx = await _post_platform_tx(
                type_=PlatformTransactionType.REFUND,
                amount=amount,
                currency=currency,
                funds_state=FundsState.REFUNDED,
                reference_type="refund",
                reference_id=refund_id,
                idempotency_key=f"manual:{event}:{PlatformTransactionType.REFUND}",
                order_id=order_id,
                payment_id=payment.get("_id"),
                supplier_business_id=supplier_id,
                description=f"Refund {refund.get('refund_number')}",
                session=session,
            )
            if payable and payable.get("status") != PayableStatus.SETTLED:
                adj = money(payable.get("adjustment_amount") or 0) + amount
                new_net = money(
                    money(payable.get("gross_amount"))
                    - money(payable.get("commission_amount"))
                    - adj
                )
                if new_net < 0:
                    new_net = Decimal("0.00")
                await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).update_one(
                    {"_id": payable["_id"]},
                    {
                        "$set": {
                            "adjustment_amount": to_decimal128(adj),
                            "net_payable_amount": to_decimal128(new_net),
                            "updated_at": utc_now(),
                        }
                    },
                    session=session,
                )
                from app.modules.platform_money.constants import (
                    SupplierBalanceBucket,
                    SupplierLedgerDirection,
                    SupplierLedgerEntryType,
                )
                from app.modules.platform_money.supplier_ledger import post_entry

                released = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
                    {"order_id": order_id, "type": PlatformTransactionType.FUNDS_RELEASED},
                    session=session,
                )
                reduction = money(money(payable.get("net_payable_amount")) - new_net)
                if reduction > 0:
                    await post_entry(
                        supplier_business_id=payable["supplier_business_id"],
                        entry_type=SupplierLedgerEntryType.ADJUSTMENT,
                        direction=SupplierLedgerDirection.DEBIT,
                        bucket=SupplierBalanceBucket.AVAILABLE if released else SupplierBalanceBucket.PENDING,
                        amount=reduction,
                        currency=currency,
                        order_id=order_id,
                        payment_id=payment.get("_id"),
                        idempotency_key=f"refund:{refund_id}:adjustment",
                        description=f"Refund {refund.get('refund_number')} to buyer",
                        session=session,
                    )
            return {"platform_transaction_id": str(tx["_id"])}

        return await run_in_transaction(_work)

    async def ingest_provider_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        amount: str,
        currency: str = "USD",
        reference_type: str,
        reference_id: str,
        order_id: str | None = None,
        payment_id: str | None = None,
        supplier_business_id: str | None = None,
        provider_transaction_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        if not event_id.strip():
            raise BadRequestError("provider event_id required")
        type_map = {
            "payment.succeeded": PlatformTransactionType.BUYER_PAYMENT,
            "buyer_payment": PlatformTransactionType.BUYER_PAYMENT,
            "payout.paid": PlatformTransactionType.SUPPLIER_PAYOUT,
            "supplier_payout": PlatformTransactionType.SUPPLIER_PAYOUT,
            "charge.refunded": PlatformTransactionType.REFUND,
            "refund": PlatformTransactionType.REFUND,
            "platform_fee": PlatformTransactionType.PLATFORM_FEE,
        }
        tx_type = type_map.get(event_type)
        if not tx_type:
            raise BadRequestError(f"Unsupported provider event type: {event_type}")
        funds = FundsState.HELD
        if tx_type == PlatformTransactionType.SUPPLIER_PAYOUT:
            funds = FundsState.RELEASED
        elif tx_type == PlatformTransactionType.REFUND:
            funds = FundsState.REFUNDED

        amt = money(amount)
        key = f"{provider}:{event_id}:{tx_type}"
        row = await _post_platform_tx(
            type_=tx_type,
            amount=amt,
            currency=currency,
            funds_state=funds,
            reference_type=reference_type,
            reference_id=parse_object_id(reference_id),
            idempotency_key=key,
            order_id=parse_object_id(order_id) if order_id else None,
            payment_id=parse_object_id(payment_id) if payment_id else None,
            supplier_business_id=parse_object_id(supplier_business_id)
            if supplier_business_id
            else None,
            provider=provider,
            provider_transaction_id=provider_transaction_id,
            provider_event_id=event_id,
            description=description or f"{provider} {event_type}",
        )
        return self._serialize_tx(row)

    def _serialize_tx(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "transaction_number": doc.get("transaction_number"),
            "type": doc.get("type"),
            "amount": _money_out(doc.get("amount")),
            "currency": doc.get("currency") or "USD",
            "funds_state": doc.get("funds_state"),
            "reference_type": doc.get("reference_type"),
            "reference_id": str(doc["reference_id"]) if doc.get("reference_id") else None,
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "payment_id": str(doc["payment_id"]) if doc.get("payment_id") else None,
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "status": doc.get("status"),
            "idempotency_key": doc.get("idempotency_key"),
            "provider": doc.get("provider"),
            "provider_transaction_id": doc.get("provider_transaction_id"),
            "provider_event_id": doc.get("provider_event_id"),
            "description": doc.get("description"),
            "posted_at": doc.get("posted_at").isoformat() if doc.get("posted_at") else None,
        }

    def _serialize_fee(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "base_amount": _money_out(doc.get("base_amount")),
            "rate": _money_out(doc.get("rate")),
            "commission_amount": _money_out(doc.get("commission_amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
            "recognized_at": doc.get("recognized_at").isoformat()
            if doc.get("recognized_at")
            else None,
        }

    def _serialize_payable(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "payable_number": doc.get("payable_number"),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "gross_amount": _money_out(doc.get("gross_amount")),
            "commission_amount": _money_out(doc.get("commission_amount")),
            "adjustment_amount": _money_out(doc.get("adjustment_amount")),
            "net_payable_amount": _money_out(doc.get("net_payable_amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
        }

    def _serialize_payout(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "payout_number": doc.get("payout_number"),
            "supplier_business_id": str(doc["supplier_business_id"])
            if doc.get("supplier_business_id")
            else None,
            "supplier_payable_id": str(doc["supplier_payable_id"])
            if doc.get("supplier_payable_id")
            else None,
            "gross_amount": _money_out(doc.get("gross_amount")),
            "platform_fee_amount": _money_out(doc.get("platform_fee_amount")),
            "net_amount": _money_out(doc.get("net_amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
            "provider": doc.get("provider"),
            "provider_transaction_id": doc.get("provider_transaction_id"),
            "failure_reason": doc.get("failure_reason"),
            "completed_at": doc.get("completed_at").isoformat()
            if doc.get("completed_at")
            else None,
        }

                                                                            

    async def admin_overview(
        self, *, business: dict[str, Any] | None
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform money overview is admin-only")

        tx_col = mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS)
        payout_col = mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS)
        payable_col = mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES)
        fee_col = mongo_manager.collection(CollectionName.COMMISSION_RECORDS)

        by_type: dict[str, Decimal] = {}
        async for row in tx_col.aggregate(
            [
                {"$match": {"status": PlatformLedgerStatus.POSTED}},
                {
                    "$group": {
                        "_id": "$type",
                        "total": {"$sum": "$amount"},
                    }
                },
            ]
        ):
            by_type[str(row["_id"])] = money(row.get("total"))

        buyer_payments = by_type.get(PlatformTransactionType.BUYER_PAYMENT, Decimal("0"))
        released = by_type.get(PlatformTransactionType.FUNDS_RELEASED, Decimal("0"))
        fees_ledger = by_type.get(PlatformTransactionType.PLATFORM_FEE, Decimal("0"))
        payouts_ledger = by_type.get(PlatformTransactionType.SUPPLIER_PAYOUT, Decimal("0"))
        refunds = by_type.get(PlatformTransactionType.REFUND, Decimal("0"))
                                                                           
        held = money(buyer_payments - released - refunds)
        if held < 0:
            held = Decimal("0.00")

        pending_payout_q = {
            "status": {"$in": [PayoutStatus.PENDING, PayoutStatus.PROCESSING]}
        }
        pending_only_q = {"status": PayoutStatus.PENDING}
        processing_q = {"status": PayoutStatus.PROCESSING}
        pending_payouts = await payout_col.count_documents(pending_payout_q)
        pending_only_count = await payout_col.count_documents(pending_only_q)
        processing_count = await payout_col.count_documents(processing_q)
        pending_payout_net = Decimal("0.00")
        pending_only_net = Decimal("0.00")
        processing_net = Decimal("0.00")
        async for row in payout_col.aggregate(
            [
                {"$match": pending_payout_q},
                {"$group": {"_id": "$status", "total": {"$sum": "$net_amount"}, "count": {"$sum": 1}}},
            ]
        ):
            amount = money(row.get("total"))
            pending_payout_net = money(pending_payout_net + amount)
            if row.get("_id") == PayoutStatus.PENDING:
                pending_only_net = amount
            elif row.get("_id") == PayoutStatus.PROCESSING:
                processing_net = amount

        open_payables = await payable_col.count_documents(
            {"status": {"$in": [PayableStatus.OPEN, PayableStatus.PARTIALLY_SETTLED]}}
        )
        recognized_fees = await fee_col.count_documents(
            {"status": CommissionStatus.RECOGNIZED}
        )
        fee_recognized_total = Decimal("0.00")
        async for row in fee_col.aggregate(
            [
                {"$match": {"status": CommissionStatus.RECOGNIZED}},
                {"$group": {"_id": None, "total": {"$sum": "$commission_amount"}}},
            ]
        ):
            fee_recognized_total = money(row.get("total"))

        posted = {"status": PlatformLedgerStatus.POSTED}

        async def _order_ids(extra: dict[str, Any]) -> set[Any]:
            found = await tx_col.distinct("order_id", {**posted, **extra, "order_id": {"$ne": None}})
            return {item for item in found if item}

        paid_orders = await _order_ids({"type": PlatformTransactionType.BUYER_PAYMENT})
        released_orders = await _order_ids({"type": PlatformTransactionType.FUNDS_RELEASED})
        refunded_orders = await _order_ids({"type": PlatformTransactionType.REFUND})
        held_orders = paid_orders - released_orders - refunded_orders

        buyer_payments_count = await tx_col.count_documents(
            {**posted, "type": PlatformTransactionType.BUYER_PAYMENT}
        )
        completed_payouts_count = await payout_col.count_documents({"status": PayoutStatus.COMPLETED})
        month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        paid_this_month = Decimal("0.00")
        async for row in payout_col.aggregate(
            [
                {"$match": {"status": PayoutStatus.COMPLETED, "completed_at": {"$gte": month_start}}},
                {"$group": {"_id": None, "total": {"$sum": "$net_amount"}}},
            ]
        ):
            paid_this_month = money(row.get("total"))

        ready_suppliers = await payout_col.distinct("supplier_business_id", pending_payout_q)

        outstanding = Decimal("0.00")
        outstanding_suppliers = 0
        ledger = mongo_manager.collection(CollectionName.SUPPLIER_LEDGER_ENTRIES)
        async for row in ledger.aggregate(
            [
                {
                    "$group": {
                        "_id": "$supplier_business_id",
                        "credits": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$direction", "credit"]},
                                    "$amount",
                                    0,
                                ]
                            }
                        },
                        "debits": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": ["$direction", "debit"]},
                                    "$amount",
                                    0,
                                ]
                            }
                        },
                    }
                }
            ]
        ):
            remaining = money(money(row.get("credits")) - money(row.get("debits")))
            if remaining > 0:
                outstanding = money(outstanding + remaining)
                outstanding_suppliers += 1

        rate_rows = (
            await fee_col.find(
                {"status": CommissionStatus.RECOGNIZED},
                {"rate": 1},
            )
            .limit(40)
            .to_list(length=40)
        )
        rates = {_money_out(row.get("rate")) for row in rate_rows if row.get("rate") is not None}
        rates.discard(None)
        commission_rate = next(iter(rates)) if len(rates) == 1 else None

        recent_tx = (
            await tx_col.find(posted)
            .sort("posted_at", -1)
            .limit(12)
            .to_list(length=12)
        )
        pending_payout_rows = (
            await payout_col.find(pending_payout_q)
            .sort("created_at", -1)
            .limit(8)
            .to_list(length=8)
        )
        activity = await self._activity_feed(recent_tx)

        return {
            "currency": "USD",
            "held_amount": format(held, "f"),
            "released_amount": format(released, "f"),
            "fees_ledger_amount": format(fees_ledger, "f"),
            "fees_recognized_amount": format(fee_recognized_total, "f"),
            "payouts_completed_amount": format(payouts_ledger, "f"),
            "refunds_amount": format(refunds, "f"),
            "buyer_payments_amount": format(buyer_payments, "f"),
            "buyer_payments_count": buyer_payments_count,
            "held_orders_count": len(held_orders),
            "released_orders_count": len(released_orders),
            "completed_payouts_count": completed_payouts_count,
            "paid_this_month_amount": format(paid_this_month, "f"),
            "ready_suppliers_count": len([item for item in ready_suppliers if item]),
            "outstanding_amount": format(outstanding, "f"),
            "outstanding_suppliers_count": outstanding_suppliers,
            "commission_rate": commission_rate,
            "pending_payouts_count": pending_payouts,
            "pending_payouts_net": format(pending_payout_net, "f"),
            "ready_payouts_count": pending_only_count,
            "ready_payouts_net": format(pending_only_net, "f"),
            "processing_payouts_count": processing_count,
            "processing_payouts_net": format(processing_net, "f"),
            "open_payables_count": open_payables,
            "recognized_fees_count": recognized_fees,
            "refunds_count": await tx_col.count_documents({**posted, "type": PlatformTransactionType.REFUND}),
            "recent_transactions": [self._serialize_tx(r) for r in recent_tx],
            "pending_payouts": [self._serialize_payout(r) for r in pending_payout_rows],
            "activity": activity,
        }

    async def _activity_feed(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        order_ids = [row["order_id"] for row in rows if row.get("order_id")]
        supplier_ids = [row["supplier_business_id"] for row in rows if row.get("supplier_business_id")]
        orders = {
            doc["_id"]: doc.get("order_number")
            async for doc in mongo_manager.collection(CollectionName.ORDERS).find(
                {"_id": {"$in": order_ids}}, {"order_number": 1}
            )
        } if order_ids else {}
        suppliers = {
            doc["_id"]: doc.get("name")
            async for doc in mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find(
                {"_id": {"$in": supplier_ids}}, {"name": 1}
            )
        } if supplier_ids else {}
        feed: list[dict[str, Any]] = []
        for row in rows:
            amount = _money_out(row.get("amount")) or "0.00"
            currency = row.get("currency") or "USD"
            order_no = orders.get(row.get("order_id"))
            order_bit = f" for order {order_no}" if order_no else ""
            supplier = suppliers.get(row.get("supplier_business_id")) or "the supplier"
            kind = str(row.get("type") or "")
            if kind == PlatformTransactionType.BUYER_PAYMENT:
                message = f"Payment of {currency} {amount} received{order_bit}"
            elif kind == PlatformTransactionType.FUNDS_RELEASED:
                if order_no:
                    message = f"{currency} {amount} released after order {order_no} was fulfilled"
                else:
                    message = f"{currency} {amount} released after an order was fulfilled"
            elif kind == PlatformTransactionType.SUPPLIER_PAYOUT:
                message = f"{currency} {amount} supplier payout recorded for {supplier}"
            elif kind == PlatformTransactionType.PLATFORM_FEE:
                message = f"{currency} {amount} TradeBay commission recognized{order_bit}"
            elif kind == PlatformTransactionType.REFUND:
                message = f"{currency} {amount} refund issued{order_bit}"
            else:
                message = row.get("description") or "Finance update recorded"
            feed.append(
                {
                    "id": str(row["_id"]),
                    "message": message,
                    "posted_at": row.get("posted_at").isoformat() if row.get("posted_at") else None,
                    "order_id": str(row["order_id"]) if row.get("order_id") else None,
                    "order_number": order_no,
                    "kind": kind,
                }
            )
        return feed

    async def financial_activity(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform money overview is admin-only")
        tx_col = mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS)
        posted = {"status": PlatformLedgerStatus.POSTED}
        kinds = [
            PlatformTransactionType.BUYER_PAYMENT,
            PlatformTransactionType.FUNDS_RELEASED,
            PlatformTransactionType.SUPPLIER_PAYOUT,
            PlatformTransactionType.PLATFORM_FEE,
            PlatformTransactionType.REFUND,
        ]
        rows = (
            await tx_col.find({**posted, "type": {"$in": kinds}})
            .sort("posted_at", -1)
            .limit(400)
            .to_list(length=400)
        )
        order_ids = list({row["order_id"] for row in rows if row.get("order_id")})
        orders = {
            doc["_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.ORDERS).find({"_id": {"$in": order_ids}})
        } if order_ids else {}
        fees = {
            doc["order_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find(
                {"order_id": {"$in": order_ids}}
            )
        } if order_ids else {}
        payables = {
            doc["order_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find(
                {"order_id": {"$in": order_ids}}
            )
        } if order_ids else {}
        payable_ids = [doc["_id"] for doc in payables.values()]
        payouts = (
            await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS)
            .find({"supplier_payable_id": {"$in": payable_ids}})
            .to_list(length=400)
        ) if payable_ids else []
        payout_by_payable: dict[Any, dict[str, Any]] = {}
        for payout in payouts:
            payout_by_payable.setdefault(payout.get("supplier_payable_id"), payout)
        payment_ids = [row["payment_id"] for row in rows if row.get("payment_id")]
        payments = {
            doc["_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.PAYMENTS).find({"_id": {"$in": payment_ids}})
        } if payment_ids else {}
        party_ids = []
        for order in orders.values():
            if order.get("buyer_business_id"):
                party_ids.append(order["buyer_business_id"])
            if order.get("supplier_business_id"):
                party_ids.append(order["supplier_business_id"])
        for row in rows:
            if row.get("supplier_business_id"):
                party_ids.append(row["supplier_business_id"])
        names = {
            doc["_id"]: doc.get("name")
            async for doc in mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find(
                {"_id": {"$in": party_ids}}, {"name": 1}
            )
        } if party_ids else {}
        released = {
            row.get("order_id")
            for row in rows
            if row.get("type") == PlatformTransactionType.FUNDS_RELEASED and row.get("order_id")
        }
        refunded = {
            row.get("order_id")
            for row in rows
            if row.get("type") == PlatformTransactionType.REFUND and row.get("order_id")
        }

        stories: list[dict[str, Any]] = []
        for row in rows:
            kind = str(row.get("type") or "")
            if kind == PlatformTransactionType.PLATFORM_FEE:
                continue
            if kind == PlatformTransactionType.FUNDS_RELEASED:
                continue
            order = orders.get(row.get("order_id")) or {}
            fee = fees.get(row.get("order_id")) or {}
            payable = payables.get(row.get("order_id")) or {}
            payout = payout_by_payable.get(payable.get("_id")) or {}
            payment = payments.get(row.get("payment_id")) or {}
            buyer_paid = money(row.get("amount")) if kind == PlatformTransactionType.BUYER_PAYMENT else money(fee.get("gross_amount") or order.get("total"))
            commission = money(fee.get("commission_amount")) if fee else Decimal("0.00")
            earnings = money(payable.get("net_payable_amount")) if payable else money(buyer_paid - commission)
            if earnings < 0:
                earnings = Decimal("0.00")
            paid = money(payout.get("net_amount")) if payout.get("status") == PayoutStatus.COMPLETED else Decimal("0.00")
            if paid > earnings:
                paid = earnings
            remaining = money(earnings - paid)
            is_released = row.get("order_id") in released or bool(payout)
            is_refunded = row.get("order_id") in refunded
            pay_status = str(payment.get("status") or "")
            if kind == PlatformTransactionType.REFUND or is_refunded and kind != PlatformTransactionType.SUPPLIER_PAYOUT:
                state = "refunded"
            elif pay_status == "failed":
                state = "failed"
            elif pay_status == "pending":
                state = "pending"
            elif kind == PlatformTransactionType.SUPPLIER_PAYOUT or (paid > 0 and remaining <= 0):
                state = "paid"
            elif is_released and remaining > 0:
                state = "ready"
            else:
                state = "held"
            order_status = str(order.get("status") or "")
            if state == "held" and order_status == "completed":
                reason = "The order is fulfilled and the supplier amount has not been released yet."
                nxt = "Release the funds before they can be paid to the supplier."
            elif state == "held":
                reason = "The order has not yet reached the fulfillment release condition."
                nxt = "The order must be fulfilled before the supplier amount can be paid out."
            elif state == "ready":
                reason = "Funds are released and waiting for the supplier payout to be recorded."
                nxt = "Record the supplier payout to settle this amount."
            else:
                reason = None
                nxt = None
            supplier_id = order.get("supplier_business_id") or row.get("supplier_business_id")
            headline = buyer_paid
            if kind == PlatformTransactionType.SUPPLIER_PAYOUT:
                headline = money(row.get("amount"))
            elif kind == PlatformTransactionType.REFUND:
                headline = money(row.get("amount"))
            stories.append(
                {
                    "id": str(row["_id"]),
                    "kind": (
                        "payout"
                        if kind == PlatformTransactionType.SUPPLIER_PAYOUT
                        else "refund"
                        if kind == PlatformTransactionType.REFUND
                        else "buyer_payment"
                    ),
                    "posted_at": row.get("posted_at").isoformat() if row.get("posted_at") else None,
                    "amount": format(headline, "f"),
                    "currency": row.get("currency") or "USD",
                    "order_id": str(row["order_id"]) if row.get("order_id") else None,
                    "order_number": order.get("order_number"),
                    "order_status": order_status or None,
                    "buyer_name": names.get(order.get("buyer_business_id")),
                    "supplier_id": str(supplier_id) if supplier_id else None,
                    "supplier_name": names.get(supplier_id),
                    "payment_method": payment.get("payment_method"),
                    "payment_reference": payment.get("payment_reference"),
                    "payout_id": str(payout["_id"]) if payout.get("_id") else (
                        str(row["reference_id"]) if kind == PlatformTransactionType.SUPPLIER_PAYOUT and row.get("reference_id") else None
                    ),
                    "payout_number": payout.get("payout_number"),
                    "payout_status": payout.get("status") if kind == PlatformTransactionType.SUPPLIER_PAYOUT or payout else None,
                    "state": state if kind != PlatformTransactionType.SUPPLIER_PAYOUT else (
                        "paid" if payout.get("status") == PayoutStatus.COMPLETED or kind == PlatformTransactionType.SUPPLIER_PAYOUT else "ready"
                    ),
                    "buyer_paid": format(buyer_paid, "f"),
                    "commission": format(commission, "f"),
                    "supplier_earnings": format(earnings, "f"),
                    "supplier_paid": format(paid, "f"),
                    "remaining": format(remaining, "f"),
                    "held_amount": format(earnings if state == "held" and kind == PlatformTransactionType.BUYER_PAYMENT else Decimal("0.00"), "f"),
                    "reason": reason if kind == PlatformTransactionType.BUYER_PAYMENT else None,
                    "next_step": nxt if kind == PlatformTransactionType.BUYER_PAYMENT else None,
                    "transaction_number": row.get("transaction_number"),
                    "payable_number": payable.get("payable_number"),
                    "stages": _story_stages(
                        kind=kind,
                        state=state,
                        buyer_paid=buyer_paid,
                        commission=commission,
                        earnings=earnings,
                        released=is_released or state in {"ready", "paid"},
                        paid=paid,
                    ),
                }
            )

        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = {"buyer_payments": Decimal("0.00"), "payouts": Decimal("0.00"), "commission": Decimal("0.00")}
        async for row in tx_col.aggregate(
            [
                {"$match": {**posted, "posted_at": {"$gte": start}, "type": {"$in": [
                    PlatformTransactionType.BUYER_PAYMENT,
                    PlatformTransactionType.SUPPLIER_PAYOUT,
                    PlatformTransactionType.PLATFORM_FEE,
                ]}}},
                {"$group": {"_id": "$type", "total": {"$sum": "$amount"}}},
            ]
        ):
            total = money(row.get("total"))
            if row["_id"] == PlatformTransactionType.BUYER_PAYMENT:
                today["buyer_payments"] = total
            elif row["_id"] == PlatformTransactionType.SUPPLIER_PAYOUT:
                today["payouts"] = total
            elif row["_id"] == PlatformTransactionType.PLATFORM_FEE:
                today["commission"] = total
        return {
            "currency": "USD",
            "today": {key: format(value, "f") for key, value in today.items()},
            "stories": stories,
        }

    async def movement(self, *, business: dict[str, Any] | None, range_key: str) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform money overview is admin-only")
        spans = {"7d": 7, "30d": 30, "90d": 90, "year": 365}
        days = spans.get(range_key)
        if days is None:
            raise BadRequestError("Choose 7 days, 30 days, 90 days, or this year")
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        weekly = days > 30
        date_format = "%G-W%V" if weekly else "%Y-%m-%d"
        grouped: dict[str, dict[str, Decimal]] = {}
        async for row in mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).aggregate(
            [
                {
                    "$match": {
                        "status": PlatformLedgerStatus.POSTED,
                        "posted_at": {"$gte": start},
                        "type": {
                            "$in": [
                                PlatformTransactionType.BUYER_PAYMENT,
                                PlatformTransactionType.FUNDS_RELEASED,
                                PlatformTransactionType.SUPPLIER_PAYOUT,
                                PlatformTransactionType.PLATFORM_FEE,
                            ]
                        },
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "bucket": {"$dateToString": {"format": date_format, "date": "$posted_at"}},
                            "type": "$type",
                        },
                        "total": {"$sum": "$amount"},
                    }
                },
            ]
        ):
            bucket = str(row["_id"]["bucket"])
            grouped.setdefault(bucket, {})[str(row["_id"]["type"])] = money(row.get("total"))

        if weekly:
            labels = sorted(grouped)
        else:
            labels = [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]

        def _slot(label: str, key: str) -> str:
            return format(grouped.get(label, {}).get(key, Decimal("0.00")), "f")

        buckets = [
            {
                "label": label,
                "buyer_payments": _slot(label, PlatformTransactionType.BUYER_PAYMENT),
                "released": _slot(label, PlatformTransactionType.FUNDS_RELEASED),
                "payouts": _slot(label, PlatformTransactionType.SUPPLIER_PAYOUT),
                "commission": _slot(label, PlatformTransactionType.PLATFORM_FEE),
            }
            for label in labels
        ]
        return {"range": range_key, "bucket": "week" if weekly else "day", "buckets": buckets}

    async def list_buyer_payments(
        self,
        *,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform transactions are admin-only")
        col = mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS)
        query = {"status": PlatformLedgerStatus.POSTED, "type": PlatformTransactionType.BUYER_PAYMENT}
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("posted_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        order_ids = [row["order_id"] for row in rows if row.get("order_id")]
        payment_ids = [row["payment_id"] for row in rows if row.get("payment_id")]
        orders = {
            doc["_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.ORDERS).find({"_id": {"$in": order_ids}})
        } if order_ids else {}
        payments = {
            doc["_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.PAYMENTS).find({"_id": {"$in": payment_ids}})
        } if payment_ids else {}
        fees = {
            doc["order_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find(
                {"order_id": {"$in": order_ids}}
            )
        } if order_ids else {}
        payables = {
            doc["order_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find(
                {"order_id": {"$in": order_ids}}
            )
        } if order_ids else {}
        released = set(
            await col.distinct(
                "order_id",
                {
                    "status": PlatformLedgerStatus.POSTED,
                    "type": PlatformTransactionType.FUNDS_RELEASED,
                    "order_id": {"$in": order_ids},
                },
            )
        ) if order_ids else set()
        refunded = set(
            await col.distinct(
                "order_id",
                {
                    "status": PlatformLedgerStatus.POSTED,
                    "type": PlatformTransactionType.REFUND,
                    "order_id": {"$in": order_ids},
                },
            )
        ) if order_ids else set()
        buyer_ids = [doc.get("buyer_business_id") for doc in orders.values() if doc.get("buyer_business_id")]
        buyers = {
            doc["_id"]: doc.get("name")
            async for doc in mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find(
                {"_id": {"$in": buyer_ids}}, {"name": 1}
            )
        } if buyer_ids else {}
        items = []
        for row in rows:
            order = orders.get(row.get("order_id")) or {}
            payment = payments.get(row.get("payment_id")) or {}
            fee = fees.get(row.get("order_id"))
            payable = payables.get(row.get("order_id"))
            if row.get("order_id") in refunded:
                funds_label = "Refunded"
            elif row.get("order_id") in released:
                funds_label = "Released"
            else:
                funds_label = "Held"
            pay_status = str(payment.get("status") or "paid")
            if pay_status == "pending":
                status_label = "Pending"
            elif pay_status == "failed":
                status_label = "Failed"
            elif funds_label == "Refunded":
                status_label = "Refunded"
            else:
                status_label = "Paid"
            items.append(
                {
                    "id": str(row["_id"]),
                    "payment_id": str(row["payment_id"]) if row.get("payment_id") else None,
                    "payment_reference": payment.get("payment_reference") or row.get("transaction_number"),
                    "order_id": str(row["order_id"]) if row.get("order_id") else None,
                    "order_number": order.get("order_number"),
                    "buyer_name": buyers.get(order.get("buyer_business_id")) if order else None,
                    "amount": _money_out(row.get("amount")),
                    "currency": row.get("currency") or "USD",
                    "payment_method": payment.get("payment_method"),
                    "status_label": status_label,
                    "funds_label": funds_label,
                    "paid_at": row.get("posted_at").isoformat() if row.get("posted_at") else None,
                    "commission_amount": _money_out(fee.get("commission_amount")) if fee else None,
                    "supplier_amount": _money_out(payable.get("net_payable_amount")) if payable else None,
                }
            )
        return items, total

    async def list_transactions(
        self,
        *,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform transactions are admin-only")
        col = mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS)
        total = await col.count_documents({})
        rows = (
            await col.find({})
            .sort("posted_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_tx(r) for r in rows], total

    async def get_transaction(
        self, *, business: dict[str, Any] | None, transaction_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != "platform":
            raise ForbiddenError("Platform transactions are admin-only")
        row = await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS).find_one(
            {"_id": parse_object_id(transaction_id)}
        )
        if row is None:
            raise NotFoundError("Platform transaction not found")
        return self._serialize_tx(row)

    async def list_fees(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == "platform":
            query: dict[str, Any] = {}
        elif str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            query = {"supplier_business_id": bid}
        else:
            raise ForbiddenError("Commission fees not available for this business")
        col = mongo_manager.collection(CollectionName.COMMISSION_RECORDS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_fee(r) for r in rows], total

    async def list_payouts(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == "platform":
            query: dict[str, Any] = {}
        elif str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            query = {"supplier_business_id": bid}
        else:
            raise ForbiddenError("Payouts not available for this business")
        col = mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_payout(r) for r in rows], total

    async def get_payout(
        self, *, business: dict[str, Any] | None, payout_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        row = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
            {"_id": parse_object_id(payout_id)}
        )
        if row is None:
            raise NotFoundError("Payout not found")
        if str(biz.get("type")) == BusinessAccountType.SUPPLIER and str(
            row.get("supplier_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("You don’t have access to this payout")
        if str(biz.get("type")) not in {"platform", BusinessAccountType.SUPPLIER}:
            raise ForbiddenError("You don't have access to supplier payouts")
        return self._serialize_payout(row)

    async def order_money_summary(
        self, *, business: dict[str, Any] | None, order_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        order = await self._find_order(order_id)
        oid = order["_id"]
        if str(biz.get("type")) == BusinessAccountType.SUPPLIER and str(
            order.get("supplier_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("You don't have access to this order's payment summary")
        if str(biz.get("type")) == BusinessAccountType.BUYER and str(
            order.get("buyer_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("You don't have access to this order's payment summary")

        fee = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
            {"order_id": oid}
        )
        payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"order_id": oid}
        )
        payout = None
        if payable:
            payout = await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find_one(
                {"supplier_payable_id": payable["_id"]}
            )
        txs = (
            await mongo_manager.collection(CollectionName.PLATFORM_TRANSACTIONS)
            .find({"order_id": oid})
            .sort("posted_at", 1)
            .to_list(length=100)
        )
        buyer_paid = Decimal("0.00")
        refunded_amt = Decimal("0.00")
        released_amt = Decimal("0.00")
        payment_method = None
        payment_status = None
        for tx in txs:
            if tx.get("status") != PlatformLedgerStatus.POSTED:
                continue
            if tx.get("type") == PlatformTransactionType.BUYER_PAYMENT:
                buyer_paid = money(buyer_paid + money(tx.get("amount")))
            elif tx.get("type") == PlatformTransactionType.FUNDS_RELEASED:
                released_amt = money(released_amt + money(tx.get("amount")))
            elif tx.get("type") == PlatformTransactionType.REFUND:
                refunded_amt = money(refunded_amt + money(tx.get("amount")))
        payment_id = next((tx.get("payment_id") for tx in txs if tx.get("payment_id")), None)
        if payment_id:
            payment = await mongo_manager.collection(CollectionName.PAYMENTS).find_one({"_id": payment_id})
            if payment:
                payment_method = payment.get("payment_method")
                payment_status = payment.get("status")
        paid_to_supplier = Decimal("0.00")
        if payable:
            async for row in mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).aggregate(
                [
                    {
                        "$match": {
                            "supplier_payable_id": payable["_id"],
                            "status": PayoutStatus.COMPLETED,
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$net_amount"}}},
                ]
            ):
                paid_to_supplier = money(row.get("total"))
        supplier_payable = money(payable.get("net_payable_amount")) if payable else Decimal("0.00")
        supplier_gross = money(payable.get("gross_amount")) if payable else buyer_paid
        commission_amt = money(fee.get("commission_amount")) if fee else Decimal("0.00")
        held_now = money(buyer_paid - released_amt - refunded_amt)
        if held_now < 0:
            held_now = Decimal("0.00")
        remaining = money(supplier_payable - paid_to_supplier)
        if remaining < 0:
            remaining = Decimal("0.00")
        if refunded_amt > 0 and released_amt == 0 and held_now == 0:
            hold_reason = "Refunded to the buyer"
        elif released_amt > 0:
            hold_reason = None
        elif buyer_paid > 0:
            hold_reason = "Order awaiting fulfillment"
        else:
            hold_reason = None
        pay_label = "Paid"
        if payment_status == "pending":
            pay_label = "Pending"
        elif payment_status == "failed":
            pay_label = "Failed"
        elif refunded_amt > 0 and held_now == 0 and released_amt == 0:
            pay_label = "Refunded"

        return {
            "order_id": order_id,
            "order_number": order.get("order_number"),
            "fee": self._serialize_fee(fee) if fee else None,
            "payable": self._serialize_payable(payable) if payable else None,
            "payout": self._serialize_payout(payout) if payout else None,
            "transactions": [self._serialize_tx(t) for t in txs],
            "story": {
                "currency": (payable or fee or {}).get("currency") or "USD",
                "buyer_paid": format(buyer_paid, "f"),
                "payment_method": payment_method,
                "payment_status": pay_label,
                "held_amount": format(held_now, "f"),
                "hold_reason": hold_reason,
                "released_amount": format(released_amt, "f"),
                "supplier_gross": format(supplier_gross, "f"),
                "commission_amount": format(commission_amt, "f"),
                "supplier_payable": format(supplier_payable, "f"),
                "paid_to_supplier": format(paid_to_supplier, "f"),
                "remaining": format(remaining, "f"),
                "refunded_amount": format(refunded_amt, "f"),
            },
        }
