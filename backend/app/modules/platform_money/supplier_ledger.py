
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import BadRequestError, ForbiddenError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import BusinessAccountType
from app.modules.platform_money.commission import as_decimal, money
from app.modules.platform_money.constants import (
    PayoutStatus,
    SupplierBalanceBucket,
    SupplierLedgerDirection,
    SupplierLedgerEntryType,
)
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


def _col() -> Any:
    return mongo_manager.collection(CollectionName.SUPPLIER_LEDGER_ENTRIES)

async def post_entry(
    *,
    supplier_business_id: ObjectId,
    entry_type: str,
    direction: str,
    bucket: str,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    description: str,
    order_id: ObjectId | None = None,
    order_number: str | None = None,
    invoice_id: ObjectId | None = None,
    invoice_number: str | None = None,
    payment_id: ObjectId | None = None,
    payment_reference: str | None = None,
    commission_record_id: ObjectId | None = None,
    commission_rate: Any = None,
    payout_id: ObjectId | None = None,
    session: MongoSession = None,
) -> dict[str, Any]:
    amt = money(amount)
    if amt < 0:
        raise BadRequestError("Ledger amounts are always positive; direction carries the sign")
    existing = await _col().find_one({"idempotency_key": idempotency_key}, session=session)
    if existing:
        return existing
    row = {
        "_id": ObjectId(),
        "supplier_business_id": supplier_business_id,
        "entry_type": entry_type,
        "direction": direction,
        "bucket": bucket,
        "amount": to_decimal128(amt),
        "currency": currency,
        "order_id": order_id,
        "order_number": order_number,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "payment_id": payment_id,
        "payment_reference": payment_reference,
        "commission_record_id": commission_record_id,
        "commission_rate": to_decimal128(as_decimal(commission_rate)) if commission_rate is not None else None,
        "payout_id": payout_id,
        "description": description,
        "idempotency_key": idempotency_key,
        "created_at": utc_now(),
    }
    try:
        await _col().insert_one(row, session=session)
    except DuplicateKeyError:
        existing = await _col().find_one({"idempotency_key": idempotency_key}, session=session)
        if existing:
            return existing
        raise
    return row

async def post_sale_entries(
    *,
    supplier_business_id: ObjectId,
    order_id: ObjectId,
    invoice: dict[str, Any],
    payment: dict[str, Any],
    commission: dict[str, Any],
    session: MongoSession,
) -> None:
    gross = money(commission.get("gross_amount") or invoice.get("total"))
    fee = money(commission.get("commission_amount"))
    currency = invoice.get("currency") or "USD"
    common = {
        "supplier_business_id": supplier_business_id,
        "bucket": SupplierBalanceBucket.PENDING,
        "currency": currency,
        "order_id": order_id,
        "order_number": invoice.get("order_number"),
        "invoice_id": invoice["_id"],
        "invoice_number": invoice.get("invoice_number"),
        "payment_id": payment["_id"],
        "payment_reference": payment.get("payment_reference"),
        "commission_record_id": commission["_id"],
        "session": session,
    }
    await post_entry(
        entry_type=SupplierLedgerEntryType.SALE,
        direction=SupplierLedgerDirection.CREDIT,
        amount=gross,
        idempotency_key=f"order:{order_id}:sale",
        description=f"Sale {invoice.get('order_number') or ''} — buyer paid {invoice.get('invoice_number')}".strip(),
        **common,
    )
    if fee > 0:
        await post_entry(
            entry_type=SupplierLedgerEntryType.PLATFORM_FEE,
            direction=SupplierLedgerDirection.DEBIT,
            amount=fee,
            idempotency_key=f"order:{order_id}:platform_fee",
            description=f"TradeBay platform fee on {invoice.get('invoice_number')}",
            commission_rate=commission.get("rate"),
            **common,
        )

async def post_release_entries(
    *,
    payable: dict[str, Any],
    order: dict[str, Any],
    session: MongoSession,
) -> None:
    net = money(payable.get("net_payable_amount"))
    if net <= 0:
        return
    common = {
        "supplier_business_id": payable["supplier_business_id"],
        "entry_type": SupplierLedgerEntryType.FUNDS_RELEASED,
        "amount": net,
        "currency": payable.get("currency") or "USD",
        "order_id": order["_id"],
        "order_number": order.get("order_number"),
        "session": session,
    }
    await post_entry(
        direction=SupplierLedgerDirection.DEBIT,
        bucket=SupplierBalanceBucket.PENDING,
        idempotency_key=f"order:{order['_id']}:release:out",
        description=f"Order {order.get('order_number')} fulfilled — moved to available",
        **common,
    )
    await post_entry(
        direction=SupplierLedgerDirection.CREDIT,
        bucket=SupplierBalanceBucket.AVAILABLE,
        idempotency_key=f"order:{order['_id']}:release:in",
        description=f"Order {order.get('order_number')} earnings available for payout",
        **common,
    )

async def post_payout_entry(*, payout: dict[str, Any], session: MongoSession) -> None:
    net = money(payout.get("net_amount"))
    if net <= 0:
        return
    await post_entry(
        supplier_business_id=payout["supplier_business_id"],
        entry_type=SupplierLedgerEntryType.PAYOUT,
        direction=SupplierLedgerDirection.DEBIT,
        bucket=SupplierBalanceBucket.AVAILABLE,
        amount=net,
        currency=payout.get("currency") or "USD",
        payout_id=payout["_id"],
        idempotency_key=f"payout:{payout['_id']}",
        description=f"Payout {payout.get('payout_number')} sent",
        session=session,
    )

async def compute_supplier_balance(supplier_business_id: ObjectId) -> dict[str, Any]:
    pipeline = [
        {"$match": {"supplier_business_id": supplier_business_id}},
        {
            "$group": {
                "_id": {"bucket": "$bucket", "direction": "$direction", "type": "$entry_type"},
                "total": {"$sum": "$amount"},
            }
        },
    ]
    sums: dict[tuple[str, str, str], Decimal] = {}
    async for row in _col().aggregate(pipeline):
        key = (row["_id"]["bucket"], row["_id"]["direction"], row["_id"]["type"])
        sums[key] = as_decimal(row["total"])

    def total(*, bucket: str | None = None, direction: str | None = None, type_: str | None = None) -> Decimal:
        return money(
            sum(
                (
                    v
                    for (b, d, t), v in sums.items()
                    if (bucket is None or b == bucket)
                    and (direction is None or d == direction)
                    and (type_ is None or t == type_)
                ),
                Decimal("0"),
            )
        )

    credits = total(direction=SupplierLedgerDirection.CREDIT)
    debits = total(direction=SupplierLedgerDirection.DEBIT)
    pending = money(
        total(bucket=SupplierBalanceBucket.PENDING, direction=SupplierLedgerDirection.CREDIT)
        - total(bucket=SupplierBalanceBucket.PENDING, direction=SupplierLedgerDirection.DEBIT)
    )
    available = money(
        total(bucket=SupplierBalanceBucket.AVAILABLE, direction=SupplierLedgerDirection.CREDIT)
        - total(bucket=SupplierBalanceBucket.AVAILABLE, direction=SupplierLedgerDirection.DEBIT)
    )
    return {
        "supplier_business_id": str(supplier_business_id),
        "currency": "USD",
        "gross_sales": format(total(type_=SupplierLedgerEntryType.SALE), "f"),
        "platform_fees": format(total(type_=SupplierLedgerEntryType.PLATFORM_FEE), "f"),
        "net_earnings": format(
            money(total(type_=SupplierLedgerEntryType.SALE) - total(type_=SupplierLedgerEntryType.PLATFORM_FEE)),
            "f",
        ),
        "pending_balance": format(pending, "f"),
        "available_balance": format(available, "f"),
        "paid_out": format(total(type_=SupplierLedgerEntryType.PAYOUT), "f"),
        "total_credits": format(credits, "f"),
        "total_debits": format(debits, "f"),
        "balance": format(money(credits - debits), "f"),
    }

def serialize_entry(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "entry_type": doc.get("entry_type"),
        "direction": doc.get("direction"),
        "bucket": doc.get("bucket"),
        "amount": format(money(doc.get("amount")), "f"),
        "currency": doc.get("currency") or "USD",
        "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
        "order_number": doc.get("order_number"),
        "invoice_id": str(doc["invoice_id"]) if doc.get("invoice_id") else None,
        "invoice_number": doc.get("invoice_number"),
        "payment_reference": doc.get("payment_reference"),
        "commission_rate": format(as_decimal(doc["commission_rate"]), "f")
        if doc.get("commission_rate") is not None
        else None,
        "description": doc.get("description"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }

class SupplierLedgerService:

    def _resolve_supplier(self, business: dict[str, Any] | None, supplier_id: str | None) -> ObjectId:
        if not business:
            raise ForbiddenError("Select a company to continue")
        btype = str(business.get("type"))
        if btype == BusinessAccountType.SUPPLIER:
            if supplier_id and supplier_id != str(business["_id"]):
                raise ForbiddenError("You can only view your own balance")
            return parse_object_id(str(business["_id"]))
        if btype == BusinessAccountType.PLATFORM:
            if not supplier_id:
                raise BadRequestError("Choose a supplier")
            return parse_object_id(supplier_id)
        raise ForbiddenError("Supplier balances are available to suppliers and TradeBay staff")

    async def balance(self, *, business: dict[str, Any] | None, supplier_id: str | None = None) -> dict[str, Any]:
        return await compute_supplier_balance(self._resolve_supplier(business, supplier_id))

    async def entries(
        self,
        *,
        business: dict[str, Any] | None,
        supplier_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        sid = self._resolve_supplier(business, supplier_id)
        query = {"supplier_business_id": sid}
        chrono = (
            await _col()
            .find(query)
            .sort([("created_at", 1), ("_id", 1)])
            .limit(2000)
            .to_list(length=2000)
        )
        running: dict[Any, str] = {}
        balance = Decimal("0.00")
        for row in chrono:
            signed = money(row.get("amount"))
            if row.get("direction") == SupplierLedgerDirection.DEBIT:
                signed = -signed
            balance = money(balance + signed)
            running[row["_id"]] = format(balance, "f")
        rows = list(reversed(chrono))
        start = (page - 1) * page_size
        page_rows = rows[start : start + page_size]
        items = []
        for row in page_rows:
            item = serialize_entry(row)
            item["running_balance"] = running.get(row["_id"])
            items.append(item)
        return items, len(chrono)

    async def all_balances(self, *, business: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not business or str(business.get("type")) != BusinessAccountType.PLATFORM:
            raise ForbiddenError("Only TradeBay staff can see every supplier balance")
        supplier_ids = await _col().distinct("supplier_business_id")
        businesses = {
            b["_id"]: b
            async for b in mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find(
                {"_id": {"$in": supplier_ids}}, {"name": 1, "logo_url": 1}
            )
        }
        verification = {
            p["business_account_id"]: p.get("verification_status")
            async for p in mongo_manager.collection(CollectionName.SUPPLIER_PROFILES).find(
                {"business_account_id": {"$in": supplier_ids}},
                {"business_account_id": 1, "verification_status": 1},
            )
        }
        order_counts: dict[Any, int] = {}
        async for row in _col().aggregate(
            [
                {"$match": {"supplier_business_id": {"$in": supplier_ids}, "entry_type": "sale"}},
                {"$group": {"_id": "$supplier_business_id", "orders": {"$addToSet": "$order_id"}}},
            ]
        ):
            order_counts[row["_id"]] = len([item for item in row.get("orders") or [] if item])
        pending_payout: dict[Any, str] = {}
        async for payout in mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS).find(
            {
                "supplier_business_id": {"$in": supplier_ids},
                "status": {"$in": ["pending", "processing"]},
            }
        ).sort("created_at", 1):
            pending_payout.setdefault(payout["supplier_business_id"], str(payout["_id"]))
        out = []
        for sid in supplier_ids:
            bal = await compute_supplier_balance(sid)
            business = businesses.get(sid) or {}
            bal["supplier_name"] = business.get("name")
            bal["logo_url"] = business.get("logo_url")
            bal["verification_status"] = verification.get(sid)
            bal["orders_count"] = order_counts.get(sid, 0)
            bal["pending_payout_id"] = pending_payout.get(sid)
            remaining = Decimal(bal["balance"])
            available = Decimal(bal["available_balance"])
            paid = Decimal(bal["paid_out"])
            if remaining <= 0:
                position = "paid"
            elif available > 0 and paid > 0:
                position = "partially_paid"
            elif available > 0:
                position = "ready"
            else:
                position = "on_hold"
            bal["position"] = position
            out.append(bal)
        out.sort(key=lambda r: Decimal(r["balance"]), reverse=True)
        return out

    async def financial_overview(
        self,
        *,
        business: dict[str, Any] | None,
        supplier_id: str,
        range_key: str = "30d",
    ) -> dict[str, Any]:
        sid = self._resolve_supplier(business, supplier_id)
        spans = {"7d": 7, "30d": 30, "90d": 90, "year": 365}
        days = spans.get(range_key)
        if days is None:
            raise BadRequestError("Choose 7 days, 30 days, 90 days, or this year")
        balance = await compute_supplier_balance(sid)
        supplier = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": sid}, {"name": 1}
        )
        supplier_name = (supplier or {}).get("name") or "This supplier"
        grouped: dict[Any, dict[str, Any]] = {}
        async for row in _col().aggregate(
            [
                {"$match": {"supplier_business_id": sid, "order_id": {"$ne": None}}},
                {
                    "$group": {
                        "_id": {
                            "order_id": "$order_id",
                            "type": "$entry_type",
                            "direction": "$direction",
                            "bucket": "$bucket",
                        },
                        "total": {"$sum": "$amount"},
                        "order_number": {"$max": "$order_number"},
                        "first_at": {"$min": "$created_at"},
                    }
                },
            ]
        ):
            key = row["_id"]
            slot = grouped.setdefault(
                key["order_id"],
                {
                    "order_number": None,
                    "paid_at": None,
                    "gross": Decimal("0"),
                    "fee": Decimal("0"),
                    "released": Decimal("0"),
                    "adj_debit": Decimal("0"),
                    "adj_credit": Decimal("0"),
                },
            )
            if row.get("order_number"):
                slot["order_number"] = row["order_number"]
            amount = money(row.get("total"))
            etype = key.get("type")
            if etype == SupplierLedgerEntryType.SALE:
                slot["gross"] = money(slot["gross"] + amount)
                first = row.get("first_at")
                if first and (slot["paid_at"] is None or first < slot["paid_at"]):
                    slot["paid_at"] = first
            elif etype == SupplierLedgerEntryType.PLATFORM_FEE:
                slot["fee"] = money(slot["fee"] + amount)
            elif etype == SupplierLedgerEntryType.FUNDS_RELEASED and key.get("bucket") == SupplierBalanceBucket.AVAILABLE:
                slot["released"] = money(slot["released"] + amount)
            elif etype == SupplierLedgerEntryType.ADJUSTMENT:
                if key.get("direction") == SupplierLedgerDirection.DEBIT:
                    slot["adj_debit"] = money(slot["adj_debit"] + amount)
                else:
                    slot["adj_credit"] = money(slot["adj_credit"] + amount)

        order_ids = list(grouped)
        orders = {
            doc["_id"]: doc
            async for doc in mongo_manager.collection(CollectionName.ORDERS).find(
                {"_id": {"$in": order_ids}},
                {"order_number": 1, "status": 1, "buyer_business_id": 1},
            )
        } if order_ids else {}
        buyer_ids = [doc.get("buyer_business_id") for doc in orders.values() if doc.get("buyer_business_id")]
        buyers = {
            doc["_id"]: doc.get("name")
            async for doc in mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find(
                {"_id": {"$in": buyer_ids}}, {"name": 1}
            )
        } if buyer_ids else {}
        payables = {
            doc.get("order_id"): doc
            async for doc in mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES).find(
                {"supplier_business_id": sid}
            )
        }
        paid_by_payable: dict[Any, Decimal] = {}
        payout_rows = (
            await mongo_manager.collection(CollectionName.SUPPLIER_PAYOUTS)
            .find({"supplier_business_id": sid})
            .sort("created_at", -1)
            .to_list(length=500)
        )
        for payout in payout_rows:
            if payout.get("status") != PayoutStatus.COMPLETED:
                continue
            pid = payout.get("supplier_payable_id")
            paid_by_payable[pid] = money(paid_by_payable.get(pid, Decimal("0")) + money(payout.get("net_amount")))

        order_rows = []
        held_orders = 0
        for oid, slot in grouped.items():
            if slot["gross"] <= 0 and slot["fee"] <= 0:
                continue
            earnings = money(slot["gross"] - slot["fee"] - slot["adj_debit"] + slot["adj_credit"])
            if earnings < 0:
                earnings = Decimal("0.00")
            payable = payables.get(oid) or {}
            paid = paid_by_payable.get(payable.get("_id"), Decimal("0.00"))
            if paid > earnings:
                paid = earnings
            remaining = money(earnings - paid)
            released = slot["released"] > 0
            if not released:
                state = "held"
                held_orders += 1
            elif remaining <= 0 and paid > 0:
                state = "paid"
            elif paid > 0:
                state = "partial"
            else:
                state = "ready"
            order = orders.get(oid) or {}
            fulfilled = str(order.get("status") or "") == "completed" or released
            order_rows.append(
                {
                    "order_id": str(oid),
                    "order_number": slot["order_number"] or order.get("order_number"),
                    "buyer_name": buyers.get(order.get("buyer_business_id")),
                    "order_value": _fmt(slot["gross"]),
                    "commission": _fmt(slot["fee"]),
                    "supplier_earnings": _fmt(earnings),
                    "money_state": state,
                    "paid": _fmt(paid),
                    "remaining": _fmt(remaining),
                    "paid_at": slot["paid_at"].isoformat() if slot["paid_at"] else None,
                    "order_status": order.get("status"),
                    "lifecycle": {
                        "buyer_paid": slot["gross"] > 0,
                        "held": slot["gross"] > 0,
                        "fulfilled": fulfilled,
                        "released": released,
                        "ready": released and remaining > 0,
                        "supplier_paid": paid > 0 and remaining <= 0,
                    },
                }
            )
        order_rows.sort(key=lambda row: row["paid_at"] or "", reverse=True)

        activity = await self._activity(sid, supplier_name, {row["order_id"]: row for row in order_rows})
        payouts = []
        payable_by_id = {doc["_id"]: doc for doc in payables.values()}
        for payout in payout_rows:
            payable = payable_by_id.get(payout.get("supplier_payable_id")) or {}
            order = orders.get(payable.get("order_id")) or {}
            payouts.append(
                {
                    "id": str(payout["_id"]),
                    "payout_number": payout.get("payout_number"),
                    "status": payout.get("status"),
                    "net_amount": _fmt(money(payout.get("net_amount"))),
                    "currency": payout.get("currency") or "USD",
                    "order_id": str(payable["order_id"]) if payable.get("order_id") else None,
                    "order_number": order.get("order_number") or payable.get("order_number"),
                    "created_at": payout["created_at"].isoformat() if payout.get("created_at") else None,
                    "completed_at": payout["completed_at"].isoformat() if payout.get("completed_at") else None,
                }
            )

        last = next((row for row in order_rows if row["paid_at"]), None)
        earnings = Decimal(balance["net_earnings"])
        held = Decimal(balance["pending_balance"])
        held_share = "0.0000"
        if earnings > 0:
            held_share = format((held / earnings).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")
        ready_count = sum(1 for payout in payout_rows if payout.get("status") in {PayoutStatus.PENDING, PayoutStatus.PROCESSING})
        return {
            "supplier_name": supplier_name,
            "currency": balance["currency"],
            "gross_sales": balance["gross_sales"],
            "commission": balance["platform_fees"],
            "supplier_earnings": balance["net_earnings"],
            "paid": balance["paid_out"],
            "held": balance["pending_balance"],
            "ready": balance["available_balance"],
            "outstanding": balance["balance"],
            "paid_order_count": len(order_rows),
            "held_order_count": held_orders,
            "ready_payout_count": ready_count,
            "held_share": held_share,
            "last_payment": None
            if last is None
            else {
                "amount": last["order_value"],
                "paid_at": last["paid_at"],
                "order_number": last["order_number"],
            },
            "orders": order_rows,
            "activity": activity,
            "payouts": payouts,
            "trend": await _trend(sid, range_key, days),
        }

    async def _activity(
        self,
        sid: Any,
        supplier_name: str,
        orders: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = (
            await _col()
            .find({"supplier_business_id": sid})
            .sort([("created_at", -1), ("_id", -1)])
            .limit(400)
            .to_list(length=400)
        )
        events = []
        for row in rows:
            if (
                row.get("entry_type") == SupplierLedgerEntryType.FUNDS_RELEASED
                and row.get("bucket") == SupplierBalanceBucket.PENDING
            ):
                continue
            order_id = str(row["order_id"]) if row.get("order_id") else None
            order = orders.get(order_id or "") or {}
            number = row.get("order_number") or order.get("order_number")
            amount = _fmt(money(row.get("amount")))
            etype = row.get("entry_type")
            description = row.get("description") or ""
            if etype == SupplierLedgerEntryType.SALE:
                held_now = order.get("money_state") == "held"
                kind = "buyer_payment"
                filters = ["buyer_payments"]
                if held_now:
                    filters.append("funds_held")
                title = "Buyer payment received"
                detail = (
                    "Buyer payment received and currently held by TradeBay."
                    if held_now
                    else "Buyer payment received."
                )
                sign = "plus"
            elif etype == SupplierLedgerEntryType.PLATFORM_FEE:
                kind, filters = "commission", ["commission"]
                title = "TradeBay commission recognized"
                detail = "TradeBay commission from this order."
                sign = "plain"
            elif etype == SupplierLedgerEntryType.FUNDS_RELEASED:
                kind = "ready"
                filters = ["funds_released", "ready"]
                title = "Funds ready for payout"
                detail = "Funds released after fulfillment."
                sign = "plain"
            elif etype == SupplierLedgerEntryType.PAYOUT:
                kind, filters = "payout", ["payouts"]
                title = "Supplier payout completed"
                detail = f"Paid to {supplier_name}."
                sign = "plain"
            elif "refund" in description.lower():
                kind, filters = "refund", ["refunds"]
                title = "Refund to the buyer"
                detail = description
                sign = "minus"
            elif row.get("direction") == SupplierLedgerDirection.CREDIT:
                kind, filters = "credit", ["credits"]
                title = "Credit note"
                detail = description or "Credit applied to this supplier."
                sign = "plus"
            else:
                kind, filters = "adjustment", ["credits"]
                title = "Adjustment"
                detail = description or "Balance adjustment."
                sign = "minus" if row.get("direction") == SupplierLedgerDirection.DEBIT else "plus"
            events.append(
                {
                    "id": str(row["_id"]),
                    "kind": kind,
                    "filters": filters,
                    "title": title,
                    "detail": detail,
                    "order_id": order_id,
                    "order_number": number,
                    "amount": amount,
                    "sign": sign,
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )
        return events

def _fmt(amount: Decimal) -> str:
    return format(money(amount), "f")

async def _trend(supplier_id: Any, range_key: str, days: int) -> dict[str, Any]:
    start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    weekly = days > 30
    date_format = "%G-W%V" if weekly else "%Y-%m-%d"
    grouped: dict[str, dict[str, Decimal]] = {}
    async for row in _col().aggregate(
        [
            {
                "$match": {
                    "supplier_business_id": supplier_id,
                    "created_at": {"$gte": start},
                    "entry_type": {
                        "$in": [
                            SupplierLedgerEntryType.SALE,
                            SupplierLedgerEntryType.PLATFORM_FEE,
                            SupplierLedgerEntryType.PAYOUT,
                        ]
                    },
                }
            },
            {
                "$group": {
                    "_id": {
                        "bucket": {"$dateToString": {"format": date_format, "date": "$created_at"}},
                        "type": "$entry_type",
                    },
                    "total": {"$sum": "$amount"},
                }
            },
        ]
    ):
        bucket = str(row["_id"]["bucket"])
        grouped.setdefault(bucket, {})[str(row["_id"]["type"])] = money(row.get("total"))
    labels = sorted(grouped) if weekly else [
        (start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)
    ]

    def slot(label: str, key: str) -> Decimal:
        return grouped.get(label, {}).get(key, Decimal("0.00"))

    buckets = []
    for label in labels:
        gross = slot(label, SupplierLedgerEntryType.SALE)
        fee = slot(label, SupplierLedgerEntryType.PLATFORM_FEE)
        buckets.append(
            {
                "label": label,
                "gross_sales": _fmt(gross),
                "commission": _fmt(fee),
                "supplier_earnings": _fmt(money(gross - fee)),
                "payouts": _fmt(slot(label, SupplierLedgerEntryType.PAYOUT)),
            }
        )
    return {"range": range_key, "bucket": "week" if weekly else "day", "buckets": buckets}
