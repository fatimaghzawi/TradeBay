"""Platform Money — routing ledger, commission, held/released, supplier payouts.

Customer Finance answers what the buyer owes. This module answers where cash goes:

    BUYER_PAYMENT (held)
         ↓
    PLATFORM_FEE + supplier payable
         ↓
    FUNDS_RELEASED (after fulfilment)
         ↓
    SUPPLIER_PAYOUT (completed)

Positions are derived from `platform_transactions` — no mutable platform_balance field.
"""

from __future__ import annotations

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
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import is_valid_object_id, parse_object_id


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
    year = utc_now().year
    head = f"{prefix}-{year}-"
    count = await mongo_manager.collection(collection).count_documents(
        {field: {"$regex": f"^{head}"}},
        session=session,
    )
    return f"{head}{count + 1:04d}"


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
    """Append-only ledger row. Duplicate idempotency_key returns the existing row."""
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
    """Idempotent PlatformFee (commission_records) + open supplier payable at PO confirm."""

    async def _work(session: MongoSession) -> dict[str, Any]:
        order_id = order["_id"]
        existing = await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).find_one(
            {"order_id": order_id}, session=session
        )
        if existing:
            return existing

        settings = await mongo_manager.collection(CollectionName.PLATFORM_SETTINGS).find_one(
            {"key": SINGLETON_KEY}, session=session
        )
        rate = as_decimal((settings or {}).get("commission_rate") or "0.05")
        base_key = (settings or {}).get("commission_base") or CommissionBase.ORDER_TOTAL
        base_amount = (
            order.get("subtotal")
            if base_key == CommissionBase.ORDER_SUBTOTAL
            else order.get("total")
        )
        split = compute_split(
            order_total=order.get("total"), base_amount=base_amount, rate=rate
        )
        now = utc_now()
        commission = {
            "_id": ObjectId(),
            "order_id": order_id,
            "supplier_business_id": order["supplier_business_id"],
            "payment_id": None,
            "base_amount": to_decimal128(split["base_amount"]),
            "rate": to_decimal128(split["rate"]),
            "commission_base": base_key,
            "commission_amount": to_decimal128(split["commission_amount"]),
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

    return await run_in_transaction(_work)


class PlatformMoneyService:
    """Platform routing operations — separate from Customer Finance AR."""

    def _require_business(self, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        return business

    # —— Payment routing / hold ————————————————————————————————————————————

    async def on_buyer_payment_completed(
        self,
        *,
        payment: dict[str, Any],
        invoice: dict[str, Any],
        provider: str | None = None,
        provider_transaction_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> dict[str, Any]:
        """Route a completed Customer Finance payment into the platform ledger (HELD)."""
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

    # —— Release / payouts —————————————————————————————————————————————————

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
        """Fulfilment gate: held → released + create PENDING supplier payout."""
        order = await self._find_order(order_id)
        oid = order["_id"]
        payable = await mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find_one(
            {"order_id": oid}
        )
        if payable is None:
            raise BadRequestError("No supplier payable for this order")
        if payable.get("status") == PayableStatus.SETTLED:
            return {"status": "already_settled", "payable_id": str(payable["_id"])}

        # Must have held buyer payment before release
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
            # Idempotent re-entry after release
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
            # Mark held buyer payment rows as released (lifecycle) via companion FUNDS_RELEASED row.
            # We do not rewrite held rows — append-only.

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
        """PENDING → PROCESSING → COMPLETED. Posts SUPPLIER_PAYOUT ledger; settles payable."""
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
        # Cannot pay out more than payable net
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
        """Admin convenience: release (if needed) then complete payout for a payable."""
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
        """Mirror Customer Finance refund into platform routing + payable adjustment."""
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
        """Idempotent webhook ingestion — duplicate event_id+type does not double-post."""
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

    # —— Admin / reporting —————————————————————————————————————————————————

    async def admin_overview(
        self, *, business: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Command-center finance strip — positions derived from the routing ledger."""
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
        # Append-only: held cash ≈ payments received − released − refunded.
        held = money(buyer_payments - released - refunds)
        if held < 0:
            held = Decimal("0.00")

        pending_payout_q = {
            "status": {"$in": [PayoutStatus.PENDING, PayoutStatus.PROCESSING]}
        }
        pending_payouts = await payout_col.count_documents(pending_payout_q)
        pending_payout_net = Decimal("0.00")
        async for row in payout_col.aggregate(
            [
                {"$match": pending_payout_q},
                {"$group": {"_id": None, "total": {"$sum": "$net_amount"}}},
            ]
        ):
            pending_payout_net = money(row.get("total"))

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

        recent_tx = (
            await tx_col.find({})
            .sort("posted_at", -1)
            .limit(8)
            .to_list(length=8)
        )
        pending_payout_rows = (
            await payout_col.find(pending_payout_q)
            .sort("created_at", -1)
            .limit(8)
            .to_list(length=8)
        )

        return {
            "currency": "USD",
            "held_amount": format(held, "f"),
            "released_amount": format(released, "f"),
            "fees_ledger_amount": format(fees_ledger, "f"),
            "fees_recognized_amount": format(fee_recognized_total, "f"),
            "payouts_completed_amount": format(payouts_ledger, "f"),
            "refunds_amount": format(refunds, "f"),
            "buyer_payments_amount": format(buyer_payments, "f"),
            "pending_payouts_count": pending_payouts,
            "pending_payouts_net": format(pending_payout_net, "f"),
            "open_payables_count": open_payables,
            "recognized_fees_count": recognized_fees,
            "recent_transactions": [self._serialize_tx(r) for r in recent_tx],
            "pending_payouts": [self._serialize_payout(r) for r in pending_payout_rows],
        }

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
        """Traceability view: payment → fee → payable → payout for one PO."""
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
        return {
            "order_id": order_id,
            "order_number": order.get("order_number"),
            "fee": self._serialize_fee(fee) if fee else None,
            "payable": self._serialize_payable(payable) if payable else None,
            "payout": self._serialize_payout(payout) if payout else None,
            "transactions": [self._serialize_tx(t) for t in txs],
        }
