"""Deterministic platform commission math (Decimal only)."""

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


def compute_split(
    *,
    order_total: Any,
    base_amount: Any,
    rate: Any,
) -> dict[str, Decimal]:
    """Frozen fee split: commission = base × rate; supplier net = total − commission."""
    total = money(order_total)
    base = money(base_amount)
    fee_rate = money(rate)
    if fee_rate < 0:
        raise ValueError("Commission rate must be >= 0")
    commission = money(base * fee_rate)
    if commission > total:
        commission = total
    net = money(total - commission)
    if net < 0:
        net = Decimal("0.00")
    return {
        "gross": total,
        "base_amount": base,
        "rate": fee_rate,
        "commission_amount": commission,
        "net_payable": net,
    }
