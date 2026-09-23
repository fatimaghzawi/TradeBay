"""Customer Finance integration — invoice → payment → credit → refund → ledger balance."""

from __future__ import annotations

from decimal import Decimal

import pytest
from bson import ObjectId
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.finance.service import FinanceService, issue_invoice_for_confirmed_order
from app.modules.identity.constants import BusinessAccountType
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now


def _buyer_biz(oid: ObjectId) -> dict:
    return {"_id": oid, "type": BusinessAccountType.BUYER}


def _supplier_biz(oid: ObjectId) -> dict:
    return {"_id": oid, "type": BusinessAccountType.SUPPLIER}


@pytest.mark.asyncio
async def test_finance_lifecycle_invoice_payment_credit_refund(app: object) -> None:
    buyer_id = ObjectId()
    supplier_id = ObjectId()
    order_id = ObjectId()
    user_id = str(ObjectId())
    now = utc_now()

    await mongo_manager.collection(CollectionName.ORDERS).insert_one(
        {
            "_id": order_id,
            "order_number": f"PO-TEST-{order_id}",
            "buyer_business_id": buyer_id,
            "supplier_business_id": supplier_id,
            "currency": "USD",
            "subtotal": to_decimal128(Decimal("2000.00")),
            "discount_total": to_decimal128(Decimal("0")),
            "charge_total": to_decimal128(Decimal("0")),
            "tax_total": to_decimal128(Decimal("0")),
            "total": to_decimal128(Decimal("2000.00")),
            "status": "confirmed",
            "created_at": now,
            "updated_at": now,
        }
    )
    items = [
        {
            "_id": ObjectId(),
            "product_id": ObjectId(),
            "product_name_snapshot": "Olive oil",
            "quantity": to_decimal128(Decimal("100")),
            "unit": "L",
            "unit_price": to_decimal128(Decimal("20.00")),
            "discount_snapshot": to_decimal128(Decimal("0")),
            "tax_snapshot": to_decimal128(Decimal("0")),
            "line_total": to_decimal128(Decimal("2000.00")),
        }
    ]

    invoice = await issue_invoice_for_confirmed_order(
        order={
            "_id": order_id,
            "order_number": f"PO-TEST-{order_id}",
            "buyer_business_id": buyer_id,
            "currency": "USD",
            "subtotal": to_decimal128(Decimal("2000.00")),
            "discount_total": to_decimal128(Decimal("0")),
            "charge_total": to_decimal128(Decimal("0")),
            "tax_total": to_decimal128(Decimal("0")),
            "total": to_decimal128(Decimal("2000.00")),
        },
        order_items=items,
        user_id=user_id,
    )
    assert invoice is not None
    invoice_id = str(invoice["_id"])
    # Historical unit price preserved on lines
    assert Decimal(str(invoice["lines"][0]["unit_price"].to_decimal())) == Decimal("20.00")

    svc = FinanceService()
    buyer = _buyer_biz(buyer_id)
    supplier = _supplier_biz(supplier_id)

    # Pending payment does not reduce outstanding
    pending = await svc.record_payment(
        user_id=user_id,
        business=buyer,
        invoice_id=invoice_id,
        amount="500.00",
        complete=False,
    )
    assert pending["status"] == "pending"
    inv_view = await svc.get_invoice(business=buyer, invoice_id=invoice_id)
    assert inv_view["outstanding"] == "2000.00"

    await svc.complete_payment(user_id=user_id, business=buyer, payment_id=pending["payment_id"])
    inv_view = await svc.get_invoice(business=buyer, invoice_id=invoice_id)
    assert inv_view["outstanding"] == "1500.00"
    assert inv_view["status"] == "partially_paid"

    # Second payment settles remaining before credit
    pay2 = await svc.record_payment(
        user_id=user_id,
        business=buyer,
        invoice_id=invoice_id,
        amount="1500.00",
        complete=True,
    )
    assert pay2["status"] == "completed"
    inv_view = await svc.get_invoice(business=buyer, invoice_id=invoice_id)
    assert inv_view["outstanding"] == "0.00"
    assert inv_view["status"] == "paid"
    assert inv_view["total"] == "2000.00"  # immutable total

    # Credit note reduces obligation / creates customer credit — total unchanged
    cn = await svc.create_credit_note(
        user_id=user_id,
        business=supplier,
        invoice_id=invoice_id,
        amount="300.00",
        reason="Damaged goods return",
        apply=True,
    )
    assert cn["amount"] == "300.00"
    inv_view = await svc.get_invoice(business=buyer, invoice_id=invoice_id)
    assert inv_view["total"] == "2000.00"
    assert inv_view["amount_credited"] == "300.00"
    assert inv_view["customer_credit"] == "300.00"

    # Over-credit rejected
    with pytest.raises(Exception):
        await svc.create_credit_note(
            user_id=user_id,
            business=supplier,
            invoice_id=invoice_id,
            amount="2000.00",
            reason="Too much",
            apply=True,
        )

    # Refund against payment (cash returned)
    refund = await svc.create_refund(
        user_id=user_id,
        business=supplier,
        payment_id=pay2["payment_id"],
        amount="300.00",
        reason="Return cash for credit",
        credit_note_id=cn["id"],
        process=True,
    )
    assert refund["status"] == "processed"

    # Over-refund prevented
    with pytest.raises(Exception):
        await svc.create_refund(
            user_id=user_id,
            business=supplier,
            payment_id=pay2["payment_id"],
            amount="1500.00",
            process=True,
        )

    bal = await svc.ar_balance(business=buyer)
    # Invoice 2000 − payments 2000 − credit 300 + refund 300 = 0
    assert bal["outstanding"] == "0.00"

    txs, total = await svc.list_transactions(business=buyer, page_size=20)
    assert total >= 4
    types = {t["transaction_type"] for t in txs}
    assert "invoice_issued" in types
    assert "payment_received" in types
    assert "credit_applied" in types
    assert "refund_processed" in types

    # Buyer isolation
    other = _buyer_biz(ObjectId())
    with pytest.raises(Exception):
        await svc.get_invoice(business=other, invoice_id=invoice_id)
