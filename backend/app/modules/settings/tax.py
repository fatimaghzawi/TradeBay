"""Tax helpers — resolve active VAT and compute tax with Decimal only."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bson import Decimal128

MONEY_QUANT = Decimal("0.01")
MAX_TAX_RATE = Decimal("1")  # 100% absolute ceiling for sanity


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


def compute_tax(
    *,
    subtotal: Any,
    discount: Any = "0",
    rate: Any,
) -> dict[str, Decimal]:
    """taxable = subtotal − discount; tax = taxable × rate; total = taxable + tax."""
    sub = money(subtotal)
    disc = money(discount)
    if disc > sub:
        disc = sub
    taxable = money(sub - disc)
    tax_rate = as_decimal(rate)
    if tax_rate < 0 or tax_rate > MAX_TAX_RATE:
        raise ValueError("Tax rate out of range")
    tax_amount = money(taxable * tax_rate)
    total = money(taxable + tax_amount)
    return {
        "subtotal": sub,
        "discount": disc,
        "taxable_amount": taxable,
        "tax_rate": tax_rate.quantize(Decimal("0.0001")),
        "tax_amount": tax_amount,
        "total": total,
    }


def tax_is_effective(doc: dict[str, Any], *, at: datetime) -> bool:
    if not doc.get("is_active"):
        return False
    start = doc.get("effective_from")
    end = doc.get("effective_until")
    if start and at < start:
        return False
    if end and at > end:
        return False
    return True
