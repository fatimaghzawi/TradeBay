"""Customer finance — invoices, payments, credit notes, refunds, AR ledger.

Balance is always derived from `financial_transactions` (and per-invoice from
payments + applied credits). There is no mutable customer.balance field.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.db.transactions import run_in_transaction
from app.modules.finance.balance import as_decimal, invoice_position, money
from app.modules.finance.constants import (
    PAYMENT_STATUS_TRANSITIONS,
    REFUND_STATUS_TRANSITIONS,
    CreditNoteStatus,
    InvoiceStatus,
    LedgerDirection,
    LedgerSourceType,
    LedgerStatus,
    LedgerTransactionType,
    PaymentStatus,
    RefundStatus,
    assert_finance_transition,
)
from app.modules.identity.constants import BusinessAccountType
from app.modules.platform_money.constants import CommissionStatus
from app.modules.settings.constants import SINGLETON_KEY
from app.modules.settings.numbering import allocate_document_number
from app.modules.settings.tax import compute_tax
from app.shared.repositories.base import MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


def _money_out(value: Any) -> str | None:
    if value is None:
        return None
    return format(money(value), "f")


async def _safe_notify(**kwargs: Any) -> None:
    try:
        from app.modules.trust.notify import notify

        await notify(**kwargs)
    except Exception:
        pass


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


async def _insert_ledger_row(
    *,
    business_account_id: ObjectId,
    amount: Decimal,
    currency: str,
    source_type: str,
    source_id: ObjectId,
    transaction_type: str,
    direction: str,
    description: str,
    invoice_id: ObjectId | None = None,
    order_id: ObjectId | None = None,
    user_id: str | None = None,
    session: MongoSession = None,
) -> dict[str, Any]:
    now = utc_now()
    tx_number = await _next_number(
        "FTX", CollectionName.FINANCIAL_TRANSACTIONS, "transaction_number", session=session
    )
    row = {
        "_id": ObjectId(),
        "transaction_number": tx_number,
        "business_account_id": business_account_id,
        "order_id": order_id,
        "invoice_id": invoice_id,
        "source_type": source_type,
        "source_id": source_id,
        "transaction_type": transaction_type,
        "direction": direction,
        "amount": to_decimal128(money(amount)),
        "currency": currency,
        "status": LedgerStatus.POSTED,
        "reverses_transaction_id": None,
        "description": description,
        "posted_at": now,
        "created_by": parse_object_id(user_id) if user_id else None,
        "created_at": now,
    }
    await mongo_manager.collection(CollectionName.FINANCIAL_TRANSACTIONS).insert_one(
        row, session=session
    )
    return row


async def issue_invoice_for_confirmed_order(
    *,
    order: dict[str, Any],
    order_items: list[dict[str, Any]],
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Idempotent: one invoice per order. Snapshots order line prices (never live catalog)."""
    order_id = order["_id"]

    async def _work(session: MongoSession) -> tuple[dict[str, Any], bool]:
        existing = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"order_id": order_id}, session=session
        )
        if existing:
            return existing, False

        letterhead = await mongo_manager.collection(CollectionName.BUSINESS_SETTINGS).find_one(
            {"key": SINGLETON_KEY}, session=session
        )
        prefix = (letterhead or {}).get("invoice_prefix") or "TB-INV"
        tax = await mongo_manager.collection(CollectionName.TAX_SETTINGS).find_one(
            {"is_active": True}, session=session
        )

        now = utc_now()
        lines = []
        for item in order_items:
            lines.append(
                {
                    "order_item_id": item.get("_id"),
                    "product_id": item.get("product_id"),
                    "description": item.get("product_name_snapshot") or "Item",
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit") or "unit",
                    "unit_price": item.get("unit_price"),
                    "discount_snapshot": item.get("discount_snapshot")
                    or to_decimal128(Decimal("0")),
                    "tax_snapshot": item.get("tax_snapshot") or to_decimal128(Decimal("0")),
                    "line_total": item.get("line_total"),
                }
            )

        tax_rate = order.get("tax_rate_snapshot") or (tax.get("rate") if tax else None)
        tax_name = order.get("tax_name_snapshot") or ((tax or {}).get("name") if tax else "VAT")
        subtotal = as_decimal(order.get("subtotal"))
        discount = as_decimal(order.get("discount_total"))
        charge = as_decimal(order.get("charge_total"))
        if tax_rate is not None:
            computed = compute_tax(subtotal=subtotal, discount=discount, rate=tax_rate)
            tax_total = computed["tax_amount"]
            total = money(computed["taxable_amount"] + tax_total + charge)
            tax_rate = computed["tax_rate"]
        else:
            tax_total = as_decimal(order.get("tax_total"))
            total = as_decimal(order.get("total"))

        invoice_number = await allocate_document_number(
            kind="invoice", prefix=prefix, session=session
        )
        invoice = {
            "_id": ObjectId(),
            "invoice_number": invoice_number,
            "order_id": order_id,
            "buyer_business_id": order["buyer_business_id"],
            "status": InvoiceStatus.ISSUED,
            "currency": order.get("currency") or "USD",
            "issued_at": now,
            "due_at": now + timedelta(days=30),
            "tax_rate": to_decimal128(tax_rate) if tax_rate is not None else None,
            "tax_name_snapshot": tax_name,
            "lines": lines,
            "subtotal": order.get("subtotal"),
            "discount_total": order.get("discount_total"),
            "charge_total": order.get("charge_total"),
            "tax_total": to_decimal128(tax_total),
            "total": to_decimal128(total),
            "created_at": now,
            "updated_at": now,
        }
        await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).insert_one(
            invoice, session=session
        )
        await _insert_ledger_row(
            business_account_id=order["buyer_business_id"],
            amount=as_decimal(total),
            currency=order.get("currency") or "USD",
            source_type=LedgerSourceType.CUSTOMER_INVOICE,
            source_id=invoice["_id"],
            transaction_type=LedgerTransactionType.INVOICE_ISSUED,
            direction=LedgerDirection.DEBIT,
            description=f"Invoice {invoice_number} for {order.get('order_number')}",
            invoice_id=invoice["_id"],
            order_id=order_id,
            user_id=user_id,
            session=session,
        )
        return invoice, True

    result, created = await run_in_transaction(_work)
    if created:
        await _safe_notify(
            recipient_business_id=order["buyer_business_id"],
            type="INVOICE_ISSUED",
            title=f"Invoice {result.get('invoice_number')} issued",
            message=f"An invoice was issued for {order.get('order_number')}. Open TradeBay to review and pay.",
            reference_type="invoice",
            reference_id=result["_id"],
        )
    return result


class FinanceService:
    """Customer AR — invoices, payments, credit notes, refunds, payables."""

    def _require_business(self, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business:
            raise ForbiddenError("Select a company to continue")
        return business

    # —— Invoices ——————————————————————————————————————————————————————————

    def _serialize_invoice(
        self,
        doc: dict[str, Any],
        *,
        paid: Decimal | None = None,
        credited: Decimal | None = None,
    ) -> dict[str, Any]:
        pos = invoice_position(
            total=doc.get("total"),
            amount_paid=paid if paid is not None else Decimal("0"),
            amount_credited=credited if credited is not None else Decimal("0"),
        )
        return {
            "id": str(doc["_id"]),
            "invoice_number": doc.get("invoice_number"),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "buyer_business_id": str(doc["buyer_business_id"])
            if doc.get("buyer_business_id")
            else None,
            "status": doc.get("status"),
            "currency": doc.get("currency") or "USD",
            "issued_at": doc.get("issued_at").isoformat() if doc.get("issued_at") else None,
            "due_at": doc.get("due_at").isoformat() if doc.get("due_at") else None,
            "subtotal": _money_out(doc.get("subtotal")),
            "discount_total": _money_out(doc.get("discount_total")),
            "charge_total": _money_out(doc.get("charge_total")),
            "tax_total": _money_out(doc.get("tax_total")),
            "total": format(pos["total"], "f"),
            "amount_paid": format(pos["amount_paid"], "f"),
            "amount_credited": format(pos["amount_credited"], "f"),
            "amount_due": format(pos["amount_due"], "f"),
            "outstanding": format(pos["outstanding"], "f"),
            "customer_credit": format(pos["customer_credit"], "f"),
            "lines": [
                {
                    "product_id": str(ln["product_id"]) if ln.get("product_id") else None,
                    "description": ln.get("description"),
                    "quantity": _money_out(ln.get("quantity")),
                    "unit": ln.get("unit"),
                    "unit_price": _money_out(ln.get("unit_price")),
                    "line_total": _money_out(ln.get("line_total")),
                }
                for ln in (doc.get("lines") or [])
            ],
        }

    async def _paid_for_invoice(
        self, invoice_id: ObjectId, *, session: MongoSession = None
    ) -> Decimal:
        cursor = mongo_manager.collection(CollectionName.PAYMENTS).find(
            {
                "status": PaymentStatus.COMPLETED,
                "allocations.invoice_id": invoice_id,
            },
            session=session,
        )
        total = Decimal("0")
        async for pay in cursor:
            for alloc in pay.get("allocations") or []:
                if alloc.get("invoice_id") == invoice_id:
                    total += as_decimal(alloc.get("allocated_amount"))
        return money(total)

    async def _credited_for_invoice(
        self, invoice_id: ObjectId, *, session: MongoSession = None
    ) -> Decimal:
        cursor = mongo_manager.collection(CollectionName.CREDIT_NOTES).find(
            {
                "invoice_id": invoice_id,
                "status": {"$in": [CreditNoteStatus.APPLIED, CreditNoteStatus.ISSUED]},
            },
            session=session,
        )
        total = Decimal("0")
        async for cn in cursor:
            # Count ISSUED + APPLIED only (draft does not reduce due / post ledger).
            if cn.get("status") in {CreditNoteStatus.APPLIED, CreditNoteStatus.ISSUED}:
                total += as_decimal(cn.get("amount"))
        return money(total)

    def _derive_invoice_status(
        self, *, total: Decimal, paid: Decimal, credited: Decimal, current: str
    ) -> str:
        if current == InvoiceStatus.VOID:
            return InvoiceStatus.VOID
        pos = invoice_position(total=total, amount_paid=paid, amount_credited=credited)
        if pos["amount_due"] <= 0 and credited > 0:
            return InvoiceStatus.CREDITED
        if pos["outstanding"] <= 0 and paid > 0:
            return InvoiceStatus.PAID
        if paid > 0:
            return InvoiceStatus.PARTIALLY_PAID
        if current == InvoiceStatus.OVERDUE:
            return InvoiceStatus.OVERDUE
        return InvoiceStatus.ISSUED

    async def _refresh_invoice_status(
        self, inv: dict[str, Any], *, session: MongoSession = None
    ) -> str:
        paid = await self._paid_for_invoice(inv["_id"], session=session)
        credited = await self._credited_for_invoice(inv["_id"], session=session)
        new_status = self._derive_invoice_status(
            total=as_decimal(inv.get("total")),
            paid=paid,
            credited=credited,
            current=str(inv.get("status")),
        )
        if new_status != inv.get("status"):
            # Allow derived refresh even if not in strict transition map (e.g. issued→paid)
            now = utc_now()
            await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).update_one(
                {"_id": inv["_id"]},
                {"$set": {"status": new_status, "updated_at": now}},
                session=session,
            )
            payment_status = (
                "paid"
                if new_status == InvoiceStatus.PAID
                else "partially_paid"
                if new_status == InvoiceStatus.PARTIALLY_PAID
                else "unpaid"
            )
            if inv.get("order_id"):
                await mongo_manager.collection(CollectionName.ORDERS).update_one(
                    {"_id": inv["order_id"]},
                    {"$set": {"payment_status": payment_status, "updated_at": now}},
                    session=session,
                )
            if new_status == InvoiceStatus.PAID and inv.get("order_id"):
                await mongo_manager.collection(CollectionName.COMMISSION_RECORDS).update_one(
                    {"order_id": inv["order_id"], "status": CommissionStatus.PENDING},
                    {
                        "$set": {
                            "status": CommissionStatus.RECOGNIZED,
                            "recognized_at": now,
                            "updated_at": now,
                        }
                    },
                    session=session,
                )
        return new_status

    async def _clear_cart_after_invoice_paid(self, invoice_id: str | ObjectId) -> None:
        """Remove cart lines for products on a fully paid order invoice."""
        try:
            inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                {"_id": parse_object_id(str(invoice_id))}
            )
            if inv is None or str(inv.get("status")) != InvoiceStatus.PAID:
                return
            buyer_id = inv.get("buyer_business_id")
            order_id = inv.get("order_id")
            if not buyer_id or not order_id:
                return
            from app.modules.cart.service import CartService

            lines = (
                await mongo_manager.collection(CollectionName.ORDER_ITEMS)
                .find({"order_id": parse_object_id(str(order_id))})
                .to_list(length=500)
            )
            product_ids = [
                str(line["product_id"]) for line in lines if line.get("product_id") is not None
            ]
            if product_ids:
                await CartService().remove_products_for_buyer(
                    buyer_business_id=str(buyer_id),
                    product_ids=product_ids,
                )
        except Exception:
            pass

    async def list_invoices(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            query: dict[str, Any] = {"buyer_business_id": bid}
        elif str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            order_ids = [
                o["_id"]
                async for o in mongo_manager.collection(CollectionName.ORDERS).find(
                    {"supplier_business_id": bid}, {"_id": 1}
                )
            ]
            query = {"order_id": {"$in": order_ids}} if order_ids else {"_id": {"$exists": False}}
        else:
            query = {}
        col = mongo_manager.collection(CollectionName.CUSTOMER_INVOICES)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        out = []
        for row in rows:
            paid = await self._paid_for_invoice(row["_id"])
            credited = await self._credited_for_invoice(row["_id"])
            out.append(self._serialize_invoice(row, paid=paid, credited=credited))
        return out, total

    async def get_invoice(self, *, business: dict[str, Any] | None, invoice_id: str) -> dict[str, Any]:
        biz = self._require_business(business)
        inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"_id": parse_object_id(invoice_id)}
        )
        if inv is None:
            raise NotFoundError("Invoice not found")
        await self._assert_invoice_access(inv, biz)
        paid = await self._paid_for_invoice(inv["_id"])
        credited = await self._credited_for_invoice(inv["_id"])
        return self._serialize_invoice(inv, paid=paid, credited=credited)

    async def _assert_invoice_access(self, inv: dict[str, Any], business: dict[str, Any]) -> None:
        bid = str(business["_id"])
        if str(business.get("type")) == "platform":
            return
        if str(inv.get("buyer_business_id")) == bid:
            return
        order = await mongo_manager.collection(CollectionName.ORDERS).find_one({"_id": inv["order_id"]})
        if order and str(order.get("supplier_business_id")) == bid:
            return
        raise ForbiddenError("Not allowed to access this invoice")

    async def _assert_buyer_scope(
        self, business: dict[str, Any], buyer_business_id: ObjectId
    ) -> None:
        if str(business.get("type")) == "platform":
            return
        if str(business.get("type")) == BusinessAccountType.BUYER and str(business["_id"]) == str(
            buyer_business_id
        ):
            return
        if str(business.get("type")) == BusinessAccountType.SUPPLIER:
            # Supplier may view AR for their own order chain only (caller must pre-check).
            return
        raise ForbiddenError("Not allowed to access this buyer's finance data")

    async def ar_balance(
        self, *, business: dict[str, Any] | None, buyer_id: str | None = None
    ) -> dict[str, Any]:
        """Buyer AR = sum of posted ledger (debit − credit). Never a stored balance field."""
        biz = self._require_business(business)
        if buyer_id:
            bid = parse_object_id(buyer_id)
            if str(biz.get("type")) == BusinessAccountType.BUYER and str(biz["_id"]) != buyer_id:
                raise ForbiddenError("Cannot view another buyer's balance")
            if str(biz.get("type")) not in {"platform", BusinessAccountType.BUYER}:
                raise ForbiddenError("AR balance lookup not allowed")
        else:
            if str(biz.get("type")) != BusinessAccountType.BUYER:
                raise ForbiddenError("AR balance is for buyer businesses")
            bid = parse_object_id(str(biz["_id"]))

        rows = await mongo_manager.collection(CollectionName.FINANCIAL_TRANSACTIONS).find(
            {"business_account_id": bid, "status": LedgerStatus.POSTED}
        ).to_list(length=5000)
        debit = Decimal("0")
        credit = Decimal("0")
        for row in rows:
            amt = as_decimal(row.get("amount"))
            if row.get("direction") == LedgerDirection.DEBIT:
                debit += amt
            else:
                credit += amt
        outstanding = money(debit - credit)
        return {
            "business_id": str(bid),
            "currency": "USD",
            "debits": format(money(debit), "f"),
            "credits": format(money(credit), "f"),
            "outstanding": format(outstanding, "f"),
        }

    async def list_transactions(
        self,
        *,
        business: dict[str, Any] | None,
        buyer_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        if buyer_id:
            if str(biz.get("type")) == BusinessAccountType.BUYER and str(biz["_id"]) != buyer_id:
                raise ForbiddenError("Cannot view another buyer's ledger")
            if str(biz.get("type")) not in {"platform", BusinessAccountType.BUYER}:
                raise ForbiddenError("Ledger history not allowed")
            bid = parse_object_id(buyer_id)
        else:
            if str(biz.get("type")) != BusinessAccountType.BUYER:
                raise ForbiddenError("Ledger history is for buyer businesses")
            bid = parse_object_id(str(biz["_id"]))

        query = {"business_account_id": bid, "status": LedgerStatus.POSTED}
        col = mongo_manager.collection(CollectionName.FINANCIAL_TRANSACTIONS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("posted_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_tx(r) for r in rows], total

    def _serialize_tx(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "transaction_number": doc.get("transaction_number"),
            "business_account_id": str(doc["business_account_id"]),
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "invoice_id": str(doc["invoice_id"]) if doc.get("invoice_id") else None,
            "source_type": doc.get("source_type"),
            "source_id": str(doc["source_id"]) if doc.get("source_id") else None,
            "transaction_type": doc.get("transaction_type"),
            "direction": doc.get("direction"),
            "amount": _money_out(doc.get("amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
            "description": doc.get("description"),
            "posted_at": doc.get("posted_at").isoformat() if doc.get("posted_at") else None,
        }

    # —— Payments ——————————————————————————————————————————————————————————

    async def record_payment(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        invoice_id: str,
        amount: str,
        payment_method: str | None = None,
        reference: str | None = None,
        complete: bool = True,
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) != BusinessAccountType.BUYER:
            raise ForbiddenError("Only the buyer can record payment on an invoice")
        inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"_id": parse_object_id(invoice_id)}
        )
        if inv is None:
            raise NotFoundError("Invoice not found")
        if str(inv.get("buyer_business_id")) != str(biz["_id"]):
            raise ForbiddenError("Invoice does not belong to this buyer")
        if inv.get("status") in {InvoiceStatus.VOID, InvoiceStatus.PAID, InvoiceStatus.CREDITED}:
            raise BadRequestError("Invoice is not open for payment")

        pay_amt = money(amount)
        if pay_amt <= 0:
            raise BadRequestError("Payment amount must be positive")
        paid = await self._paid_for_invoice(inv["_id"])
        credited = await self._credited_for_invoice(inv["_id"])
        pos = invoice_position(total=inv.get("total"), amount_paid=paid, amount_credited=credited)
        if pay_amt > pos["outstanding"] + Decimal("0.001"):
            raise BadRequestError("Payment exceeds outstanding balance")

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            payment_ref = reference or await _next_number(
                "PAY", CollectionName.PAYMENTS, "payment_reference", session=session
            )
            status = PaymentStatus.COMPLETED if complete else PaymentStatus.PENDING
            payment = {
                "_id": ObjectId(),
                "payment_reference": payment_ref,
                "idempotency_key": f"inv:{invoice_id}:{payment_ref}",
                "payer_business_id": inv["buyer_business_id"],
                "amount": to_decimal128(pay_amt),
                "currency": inv.get("currency") or "USD",
                "payment_method": payment_method or "manual",
                "status": status,
                "provider": "manual",
                "allocations": [
                    {
                        "invoice_id": inv["_id"],
                        "allocated_amount": to_decimal128(pay_amt),
                        "allocated_at": now,
                    }
                ],
                "receipt_document_url": None,
                "receipt_issued_at": now if complete else None,
                "paid_at": now if complete else None,
                "created_at": now,
                "updated_at": now,
            }
            if complete:
                payment["receipt_number"] = await _next_number(
                    "RCP", CollectionName.PAYMENTS, "receipt_number", session=session
                )
            await mongo_manager.collection(CollectionName.PAYMENTS).insert_one(
                payment, session=session
            )

            if complete:
                await _insert_ledger_row(
                    business_account_id=inv["buyer_business_id"],
                    amount=pay_amt,
                    currency=inv.get("currency") or "USD",
                    source_type=LedgerSourceType.PAYMENT,
                    source_id=payment["_id"],
                    transaction_type=LedgerTransactionType.PAYMENT_RECEIVED,
                    direction=LedgerDirection.CREDIT,
                    description=f"Payment {payment_ref} on {inv.get('invoice_number')}",
                    invoice_id=inv["_id"],
                    order_id=inv.get("order_id"),
                    user_id=user_id,
                    session=session,
                )
                await self._refresh_invoice_status(inv, session=session)

            return {
                "payment_id": str(payment["_id"]),
                "payment_reference": payment_ref,
                "amount": format(pay_amt, "f"),
                "status": status,
            }

        result = await run_in_transaction(_work)
        result["invoice"] = await self.get_invoice(business=business, invoice_id=invoice_id)
        if result.get("status") == PaymentStatus.COMPLETED:
            await self._try_platform_on_payment(payment_id=result["payment_id"], invoice_id=invoice_id)
            await self._clear_cart_after_invoice_paid(invoice_id)
            order = await mongo_manager.collection(CollectionName.ORDERS).find_one(
                {"_id": inv.get("order_id")}
            ) if inv.get("order_id") else None
            supplier_id = order.get("supplier_business_id") if order else None
            amount_label = f"{result.get('amount')} {inv.get('currency') or 'USD'}"
            if supplier_id:
                await _safe_notify(
                    recipient_business_id=supplier_id,
                    type="PAYMENT_RECEIVED",
                    title=f"Payment received for {inv.get('invoice_number')}",
                    message=f"{amount_label} was recorded on this invoice.",
                    reference_type="invoice",
                    reference_id=inv["_id"],
                )
            await _safe_notify(
                recipient_business_id=inv.get("buyer_business_id"),
                type="PAYMENT_RECEIVED",
                title=f"Payment recorded for {inv.get('invoice_number')}",
                message=f"{amount_label} has been applied to this invoice.",
                reference_type="invoice",
                reference_id=inv["_id"],
            )
        return result

    async def _try_platform_on_payment(self, *, payment_id: str, invoice_id: str) -> None:
        """Best-effort handoff to Platform Money (held buyer payment + fee)."""
        try:
            from app.modules.platform_money.service import PlatformMoneyService

            pay = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
                {"_id": parse_object_id(payment_id)}
            )
            inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                {"_id": parse_object_id(invoice_id)}
            )
            if pay and inv:
                await PlatformMoneyService().on_buyer_payment_completed(payment=pay, invoice=inv)
        except Exception:
            pass

    async def _try_platform_on_refund(self, *, refund_id: str) -> None:
        try:
            from app.modules.platform_money.service import PlatformMoneyService

            rf = await mongo_manager.collection(CollectionName.REFUNDS).find_one(
                {"_id": parse_object_id(refund_id)}
            )
            if not rf:
                return
            pay = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
                {"_id": rf["payment_id"]}
            )
            inv = None
            if rf.get("invoice_id"):
                inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                    {"_id": rf["invoice_id"]}
                )
            if pay:
                await PlatformMoneyService().on_customer_refund(
                    refund=rf, payment=pay, invoice=inv
                )
        except Exception:
            pass

    async def complete_payment(
        self, *, user_id: str, business: dict[str, Any] | None, payment_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        pay = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
            {"_id": parse_object_id(payment_id)}
        )
        if pay is None:
            raise NotFoundError("Payment not found")
        if str(biz.get("type")) == BusinessAccountType.BUYER and str(
            pay.get("payer_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("Payment does not belong to this buyer")
        assert_finance_transition(
            PAYMENT_STATUS_TRANSITIONS, str(pay.get("status")), PaymentStatus.COMPLETED, label="payment"
        )

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            await mongo_manager.collection(CollectionName.PAYMENTS).update_one(
                {"_id": pay["_id"]},
                {
                    "$set": {
                        "status": PaymentStatus.COMPLETED,
                        "paid_at": now,
                        "receipt_issued_at": now,
                        "updated_at": now,
                    }
                },
                session=session,
            )
            invoice_id = None
            for alloc in pay.get("allocations") or []:
                invoice_id = alloc.get("invoice_id")
                break
            inv = None
            if invoice_id:
                inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                    {"_id": invoice_id}, session=session
                )
            await _insert_ledger_row(
                business_account_id=pay["payer_business_id"],
                amount=as_decimal(pay.get("amount")),
                currency=pay.get("currency") or "USD",
                source_type=LedgerSourceType.PAYMENT,
                source_id=pay["_id"],
                transaction_type=LedgerTransactionType.PAYMENT_RECEIVED,
                direction=LedgerDirection.CREDIT,
                description=f"Payment {pay.get('payment_reference')} completed",
                invoice_id=invoice_id,
                order_id=inv.get("order_id") if inv else None,
                user_id=user_id,
                session=session,
            )
            if inv:
                await self._refresh_invoice_status(inv, session=session)
            refreshed = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
                {"_id": pay["_id"]}, session=session
            )
            assert refreshed is not None
            return self._serialize_payment(refreshed)

        result = await run_in_transaction(_work)
        inv_id = None
        for alloc in pay.get("allocations") or []:
            inv_id = str(alloc.get("invoice_id"))
            break
        if inv_id:
            await self._try_platform_on_payment(payment_id=payment_id, invoice_id=inv_id)
            await self._clear_cart_after_invoice_paid(inv_id)
        return result

    def _serialize_payment(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "payment_reference": doc.get("payment_reference"),
            "receipt_number": doc.get("receipt_number"),
            "receipt_issued_at": doc.get("receipt_issued_at").isoformat()
            if doc.get("receipt_issued_at")
            else None,
            "payer_business_id": str(doc["payer_business_id"])
            if doc.get("payer_business_id")
            else None,
            "amount": _money_out(doc.get("amount")),
            "currency": doc.get("currency") or "USD",
            "payment_method": doc.get("payment_method"),
            "status": doc.get("status"),
            "paid_at": doc.get("paid_at").isoformat() if doc.get("paid_at") else None,
            "allocations": [
                {
                    "invoice_id": str(a["invoice_id"]),
                    "allocated_amount": _money_out(a.get("allocated_amount")),
                }
                for a in (doc.get("allocations") or [])
            ],
        }

    async def list_payments(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            query: dict[str, Any] = {"payer_business_id": bid}
        elif str(biz.get("type")) == "platform":
            query = {}
        else:
            # Supplier: payments on invoices for their orders
            order_ids = [
                o["_id"]
                async for o in mongo_manager.collection(CollectionName.ORDERS).find(
                    {"supplier_business_id": bid}, {"_id": 1}
                )
            ]
            inv_ids = [
                i["_id"]
                async for i in mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find(
                    {"order_id": {"$in": order_ids}}, {"_id": 1}
                )
            ]
            query = (
                {"allocations.invoice_id": {"$in": inv_ids}}
                if inv_ids
                else {"_id": {"$exists": False}}
            )
        col = mongo_manager.collection(CollectionName.PAYMENTS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_payment(r) for r in rows], total

    async def get_payment(self, *, business: dict[str, Any] | None, payment_id: str) -> dict[str, Any]:
        biz = self._require_business(business)
        pay = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
            {"_id": parse_object_id(payment_id)}
        )
        if pay is None:
            raise NotFoundError("Payment not found")
        if str(biz.get("type")) == BusinessAccountType.BUYER and str(
            pay.get("payer_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("You don't have access to this payment")
        if str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            # Must be tied to supplier's invoice
            allowed = False
            for alloc in pay.get("allocations") or []:
                inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                    {"_id": alloc.get("invoice_id")}
                )
                if inv:
                    try:
                        await self._assert_invoice_access(inv, biz)
                        allowed = True
                        break
                    except ForbiddenError:
                        continue
            if not allowed:
                raise ForbiddenError("You don't have access to this payment")
        return self._serialize_payment(pay)

    # —— Credit notes ——————————————————————————————————————————————————————

    async def create_credit_note(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        invoice_id: str,
        amount: str,
        reason: str,
        apply: bool = True,
        lines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        reason_clean = (reason or "").strip()
        if not reason_clean:
            raise BadRequestError("Credit note requires a reason")
        inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"_id": parse_object_id(invoice_id)}
        )
        if inv is None:
            raise NotFoundError("Invoice not found")
        await self._assert_invoice_access(inv, biz)
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            raise ForbiddenError("Buyers cannot issue credit notes")
        if inv.get("status") == InvoiceStatus.VOID:
            raise BadRequestError("Cannot credit a void invoice")

        cn_amt = money(amount)
        if cn_amt <= 0:
            raise BadRequestError("Credit note amount must be positive")
        credited = await self._credited_for_invoice(inv["_id"])
        # Max credit = remaining invoice obligation before this note (total - already credited)
        max_credit = money(as_decimal(inv.get("total")) - credited)
        if cn_amt > max_credit + Decimal("0.001"):
            raise BadRequestError("Credit note exceeds allowable amount for this invoice")

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            number = await _next_number(
                "CN", CollectionName.CREDIT_NOTES, "credit_note_number", session=session
            )
            status = CreditNoteStatus.APPLIED if apply else CreditNoteStatus.ISSUED
            cn_lines = []
            for ln in lines or []:
                cn_lines.append(
                    {
                        "description": ln.get("description") or "Credit",
                        "quantity": to_decimal128(money(ln["quantity"]))
                        if ln.get("quantity") is not None
                        else None,
                        "unit_price": to_decimal128(money(ln["unit_price"]))
                        if ln.get("unit_price") is not None
                        else None,
                        "line_total": to_decimal128(money(ln.get("line_total") or cn_amt)),
                    }
                )
            if not cn_lines:
                cn_lines = [
                    {
                        "description": reason_clean,
                        "quantity": None,
                        "unit_price": None,
                        "line_total": to_decimal128(cn_amt),
                    }
                ]
            doc = {
                "_id": ObjectId(),
                "credit_note_number": number,
                "invoice_id": inv["_id"],
                "buyer_business_id": inv["buyer_business_id"],
                "order_id": inv.get("order_id"),
                "reason": reason_clean,
                "amount": to_decimal128(cn_amt),
                "currency": inv.get("currency") or "USD",
                "status": status,
                "lines": cn_lines,
                "issued_at": now,
                "applied_at": now if apply else None,
                "created_by": parse_object_id(user_id),
                "created_at": now,
                "updated_at": now,
            }
            await mongo_manager.collection(CollectionName.CREDIT_NOTES).insert_one(
                doc, session=session
            )
            # Ledger posts when issued/applied (obligation reduced). Draft would not post.
            await _insert_ledger_row(
                business_account_id=inv["buyer_business_id"],
                amount=cn_amt,
                currency=inv.get("currency") or "USD",
                source_type=LedgerSourceType.CREDIT_NOTE,
                source_id=doc["_id"],
                transaction_type=LedgerTransactionType.CREDIT_APPLIED,
                direction=LedgerDirection.CREDIT,
                description=f"Credit note {number} on {inv.get('invoice_number')}: {reason_clean}",
                invoice_id=inv["_id"],
                order_id=inv.get("order_id"),
                user_id=user_id,
                session=session,
            )
            await self._refresh_invoice_status(inv, session=session)
            return self._serialize_credit_note(doc)

        result = await run_in_transaction(_work)
        await _safe_notify(
            recipient_business_id=result.get("buyer_business_id"),
            type="CREDIT_NOTE_ISSUED",
            title=f"Credit note {result.get('credit_note_number')} issued",
            message=(
                f"{result.get('amount')} {result.get('currency') or 'USD'} was credited"
                f" on this invoice. {result.get('reason') or ''}"
            ).strip(),
            reference_type="invoice",
            reference_id=result.get("invoice_id"),
        )
        return result

    def _serialize_credit_note(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "credit_note_number": doc.get("credit_note_number"),
            "invoice_id": str(doc["invoice_id"]) if doc.get("invoice_id") else None,
            "buyer_business_id": str(doc["buyer_business_id"])
            if doc.get("buyer_business_id")
            else None,
            "order_id": str(doc["order_id"]) if doc.get("order_id") else None,
            "reason": doc.get("reason"),
            "amount": _money_out(doc.get("amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
            "issued_at": doc.get("issued_at").isoformat() if doc.get("issued_at") else None,
            "applied_at": doc.get("applied_at").isoformat() if doc.get("applied_at") else None,
            "lines": [
                {
                    "description": ln.get("description"),
                    "quantity": _money_out(ln.get("quantity")),
                    "unit_price": _money_out(ln.get("unit_price")),
                    "line_total": _money_out(ln.get("line_total")),
                }
                for ln in (doc.get("lines") or [])
            ],
        }

    async def list_credit_notes(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            query: dict[str, Any] = {"buyer_business_id": bid}
        elif str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            order_ids = [
                o["_id"]
                async for o in mongo_manager.collection(CollectionName.ORDERS).find(
                    {"supplier_business_id": bid}, {"_id": 1}
                )
            ]
            inv_ids = [
                i["_id"]
                async for i in mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find(
                    {"order_id": {"$in": order_ids}}, {"_id": 1}
                )
            ]
            query = {"invoice_id": {"$in": inv_ids}} if inv_ids else {"_id": {"$exists": False}}
        else:
            query = {}
        col = mongo_manager.collection(CollectionName.CREDIT_NOTES)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_credit_note(r) for r in rows], total

    async def get_credit_note(
        self, *, business: dict[str, Any] | None, credit_note_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        cn = await mongo_manager.collection(CollectionName.CREDIT_NOTES).find_one(
            {"_id": parse_object_id(credit_note_id)}
        )
        if cn is None:
            raise NotFoundError("Credit note not found")
        inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
            {"_id": cn["invoice_id"]}
        )
        if inv is None:
            raise NotFoundError("Invoice not found")
        await self._assert_invoice_access(inv, biz)
        return self._serialize_credit_note(cn)

    # —— Refunds ———————————————————————————————————————————————————————————

    async def create_refund(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payment_id: str,
        amount: str,
        reason: str | None = None,
        credit_note_id: str | None = None,
        process: bool = True,
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        pay = await mongo_manager.collection(CollectionName.PAYMENTS).find_one(
            {"_id": parse_object_id(payment_id)}
        )
        if pay is None:
            raise NotFoundError("Payment not found")
        if pay.get("status") != PaymentStatus.COMPLETED:
            raise BadRequestError("Only completed payments can be refunded")
        if str(biz.get("type")) == BusinessAccountType.BUYER and str(
            pay.get("payer_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("Payment does not belong to this buyer")

        refund_amt = money(amount)
        if refund_amt <= 0:
            raise BadRequestError("Refund amount must be positive")

        already = Decimal("0")
        async for rf in mongo_manager.collection(CollectionName.REFUNDS).find(
            {
                "payment_id": pay["_id"],
                "status": {"$in": [RefundStatus.PROCESSED, RefundStatus.APPROVED, RefundStatus.REQUESTED]},
            }
        ):
            already += as_decimal(rf.get("amount"))
        refundable = money(as_decimal(pay.get("amount")) - already)
        if refund_amt > refundable + Decimal("0.001"):
            raise BadRequestError("Refund exceeds refundable amount on this payment")

        cn = None
        if credit_note_id:
            cn = await mongo_manager.collection(CollectionName.CREDIT_NOTES).find_one(
                {"_id": parse_object_id(credit_note_id)}
            )
            if cn is None:
                raise NotFoundError("Credit note not found")
            if str(cn.get("buyer_business_id")) != str(pay.get("payer_business_id")):
                raise BadRequestError("Credit note does not belong to this payer")

        invoice_id = None
        for alloc in pay.get("allocations") or []:
            invoice_id = alloc.get("invoice_id")
            break
        inv = None
        if invoice_id:
            inv = await mongo_manager.collection(CollectionName.CUSTOMER_INVOICES).find_one(
                {"_id": invoice_id}
            )
            if inv and str(biz.get("type")) == BusinessAccountType.SUPPLIER:
                await self._assert_invoice_access(inv, biz)

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            number = await _next_number(
                "RFN", CollectionName.REFUNDS, "refund_number", session=session
            )
            status = RefundStatus.PROCESSED if process else RefundStatus.REQUESTED
            doc = {
                "_id": ObjectId(),
                "refund_number": number,
                "payment_id": pay["_id"],
                "credit_note_id": cn["_id"] if cn else None,
                "invoice_id": invoice_id,
                "buyer_business_id": pay["payer_business_id"],
                "order_id": inv.get("order_id") if inv else None,
                "amount": to_decimal128(refund_amt),
                "currency": pay.get("currency") or "USD",
                "reason": (reason or "").strip() or None,
                "status": status,
                "refund_reference": number,
                "processed_at": now if process else None,
                "created_by": parse_object_id(user_id),
                "created_at": now,
                "updated_at": now,
            }
            await mongo_manager.collection(CollectionName.REFUNDS).insert_one(doc, session=session)
            if process:
                await _insert_ledger_row(
                    business_account_id=pay["payer_business_id"],
                    amount=refund_amt,
                    currency=pay.get("currency") or "USD",
                    source_type=LedgerSourceType.REFUND,
                    source_id=doc["_id"],
                    transaction_type=LedgerTransactionType.REFUND_PROCESSED,
                    direction=LedgerDirection.DEBIT,
                    description=f"Refund {number} of payment {pay.get('payment_reference')}",
                    invoice_id=invoice_id,
                    order_id=inv.get("order_id") if inv else None,
                    user_id=user_id,
                    session=session,
                )
            return self._serialize_refund(doc)

        result = await run_in_transaction(_work)
        if result.get("status") == RefundStatus.PROCESSED:
            await self._try_platform_on_refund(refund_id=result["id"])
            await _safe_notify(
                recipient_business_id=result.get("buyer_business_id"),
                type="REFUND_PROCESSED",
                title=f"Refund {result.get('refund_number')} processed",
                message=(
                    f"{result.get('amount')} {result.get('currency') or 'USD'} was refunded."
                    + (f" {result.get('reason')}" if result.get("reason") else "")
                ),
                reference_type="invoice",
                reference_id=result.get("invoice_id"),
            )
        return result

    async def process_refund(
        self, *, user_id: str, business: dict[str, Any] | None, refund_id: str
    ) -> dict[str, Any]:
        biz = self._require_business(business)
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            raise ForbiddenError("Buyers cannot process refunds")
        rf = await mongo_manager.collection(CollectionName.REFUNDS).find_one(
            {"_id": parse_object_id(refund_id)}
        )
        if rf is None:
            raise NotFoundError("Refund not found")
        current = str(rf.get("status"))
        if current == RefundStatus.REQUESTED:
            assert_finance_transition(
                REFUND_STATUS_TRANSITIONS, current, RefundStatus.APPROVED, label="refund"
            )
            current = RefundStatus.APPROVED
            await mongo_manager.collection(CollectionName.REFUNDS).update_one(
                {"_id": rf["_id"]},
                {"$set": {"status": RefundStatus.APPROVED, "updated_at": utc_now()}},
            )
        assert_finance_transition(
            REFUND_STATUS_TRANSITIONS, current, RefundStatus.PROCESSED, label="refund"
        )

        async def _work(session: MongoSession) -> dict[str, Any]:
            now = utc_now()
            await mongo_manager.collection(CollectionName.REFUNDS).update_one(
                {"_id": rf["_id"]},
                {
                    "$set": {
                        "status": RefundStatus.PROCESSED,
                        "processed_at": now,
                        "updated_at": now,
                    }
                },
                session=session,
            )
            await _insert_ledger_row(
                business_account_id=rf["buyer_business_id"],
                amount=as_decimal(rf.get("amount")),
                currency=rf.get("currency") or "USD",
                source_type=LedgerSourceType.REFUND,
                source_id=rf["_id"],
                transaction_type=LedgerTransactionType.REFUND_PROCESSED,
                direction=LedgerDirection.DEBIT,
                description=f"Refund {rf.get('refund_number')} processed",
                invoice_id=rf.get("invoice_id"),
                order_id=rf.get("order_id"),
                user_id=user_id,
                session=session,
            )
            refreshed = await mongo_manager.collection(CollectionName.REFUNDS).find_one(
                {"_id": rf["_id"]}, session=session
            )
            assert refreshed is not None
            return self._serialize_refund(refreshed)

        result = await run_in_transaction(_work)
        await self._try_platform_on_refund(refund_id=refund_id)
        await _safe_notify(
            recipient_business_id=result.get("buyer_business_id"),
            type="REFUND_PROCESSED",
            title=f"Refund {result.get('refund_number')} processed",
            message=(
                f"{result.get('amount')} {result.get('currency') or 'USD'} was refunded."
                + (f" {result.get('reason')}" if result.get("reason") else "")
            ),
            reference_type="invoice",
            reference_id=result.get("invoice_id"),
        )
        return result

    def _serialize_refund(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "refund_number": doc.get("refund_number"),
            "payment_id": str(doc["payment_id"]) if doc.get("payment_id") else None,
            "credit_note_id": str(doc["credit_note_id"]) if doc.get("credit_note_id") else None,
            "invoice_id": str(doc["invoice_id"]) if doc.get("invoice_id") else None,
            "buyer_business_id": str(doc["buyer_business_id"])
            if doc.get("buyer_business_id")
            else None,
            "amount": _money_out(doc.get("amount")),
            "currency": doc.get("currency") or "USD",
            "reason": doc.get("reason"),
            "status": doc.get("status"),
            "refund_reference": doc.get("refund_reference"),
            "processed_at": doc.get("processed_at").isoformat()
            if doc.get("processed_at")
            else None,
        }

    async def list_refunds(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == BusinessAccountType.BUYER:
            query: dict[str, Any] = {"buyer_business_id": bid}
        elif str(biz.get("type")) == "platform":
            query = {}
        else:
            order_ids = [
                o["_id"]
                async for o in mongo_manager.collection(CollectionName.ORDERS).find(
                    {"supplier_business_id": bid}, {"_id": 1}
                )
            ]
            query = {"order_id": {"$in": order_ids}} if order_ids else {"_id": {"$exists": False}}
        col = mongo_manager.collection(CollectionName.REFUNDS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_refund(r) for r in rows], total

    async def get_refund(self, *, business: dict[str, Any] | None, refund_id: str) -> dict[str, Any]:
        biz = self._require_business(business)
        rf = await mongo_manager.collection(CollectionName.REFUNDS).find_one(
            {"_id": parse_object_id(refund_id)}
        )
        if rf is None:
            raise NotFoundError("Refund not found")
        if str(biz.get("type")) == BusinessAccountType.BUYER and str(
            rf.get("buyer_business_id")
        ) != str(biz["_id"]):
            raise ForbiddenError("You don't have access to this refund")
        return self._serialize_refund(rf)

    # —— Supplier payables —————————————————————————————————————————————————

    async def list_payables(
        self, *, business: dict[str, Any] | None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        biz = self._require_business(business)
        bid = parse_object_id(str(biz["_id"]))
        if str(biz.get("type")) == BusinessAccountType.SUPPLIER:
            query: dict[str, Any] = {"supplier_business_id": bid}
        elif str(biz.get("type")) == "platform":
            query = {}
        else:
            order_ids = [
                o["_id"]
                async for o in mongo_manager.collection(CollectionName.ORDERS).find(
                    {"buyer_business_id": bid}, {"_id": 1}
                )
            ]
            query = {"order_id": {"$in": order_ids}} if order_ids else {"_id": {"$exists": False}}
        col = mongo_manager.collection(CollectionName.SUPPLIER_PAYABLES)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_payable(r) for r in rows], total

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
            "net_payable_amount": _money_out(doc.get("net_payable_amount")),
            "currency": doc.get("currency") or "USD",
            "status": doc.get("status"),
        }

    async def settle_payable(
        self, *, user_id: str, business: dict[str, Any] | None, payable_id: str
    ) -> dict[str, Any]:
        """Delegate to Platform Money: release held funds then complete payout."""
        from app.modules.platform_money.service import PlatformMoneyService

        result = await PlatformMoneyService().settle_payable(
            user_id=user_id, business=business, payable_id=payable_id
        )
        return result.get("payable") or result
