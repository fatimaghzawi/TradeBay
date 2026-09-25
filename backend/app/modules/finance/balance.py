
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bson import Decimal128

MONEY_QUANT = Decimal("0.01")

def as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))

def money(value: Any) -> Decimal:
    return as_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

def invoice_position(
    *,
    total: Any,
    amount_paid: Any,
    amount_credited: Any,
) -> dict[str, Decimal]:
    inv_total = money(total)
    paid = money(amount_paid)
    credited = money(amount_credited)
    amount_due = money(inv_total - credited)
    outstanding = money(max(Decimal("0"), amount_due - paid))
    customer_credit = money(max(Decimal("0"), paid + credited - inv_total))
    return {
        "total": inv_total,
        "amount_paid": paid,
        "amount_credited": credited,
        "amount_due": amount_due,
        "outstanding": outstanding,
        "customer_credit": customer_credit,
    }

def ledger_outstanding(*, debits: Any, credits: Any) -> Decimal:
    return money(as_decimal(debits) - as_decimal(credits))
