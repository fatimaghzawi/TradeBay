"""Server-side commercial totals for quotations and orders. Decimal only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0")


def money(value: Decimal | int | str | None) -> Decimal:
    """Parse a required commercial amount. ``None`` → 0; blank/invalid → ValueError."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("Money must be Decimal, int or str — not bool")
    if isinstance(value, float):
        raise ValueError("Money must be Decimal, int or str — not float")
    text = str(value).strip()
    if not text:
        raise ValueError("Money amount is required")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money amount: {text!r}") from exc


def optional_money(value: Decimal | int | str | None) -> Decimal | None:
    """Parse an optional amount. Blank/None → None; invalid → ValueError."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return money(value)


def quantize(value: Decimal) -> Decimal:
    return money(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineTotals:
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax: Decimal
    shipping: Decimal
    subtotal: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class DocumentTotals:
    subtotal: Decimal
    discount_total: Decimal
    charge_total: Decimal
    tax_total: Decimal
    total: Decimal
    lines: list[LineTotals]


def compute_line(
    *,
    quantity: Decimal | int | str,
    unit_price: Decimal | int | str,
    discount: Decimal | int | str = ZERO,
    tax: Decimal | int | str = ZERO,
    shipping: Decimal | int | str = ZERO,
) -> LineTotals:
    qty = money(quantity)
    price = money(unit_price)
    disc = money(discount)
    tax_amt = money(tax)
    ship = money(shipping)
    if qty < ZERO or price < ZERO or disc < ZERO or tax_amt < ZERO or ship < ZERO:
        raise ValueError("Commercial amounts cannot be negative")
    subtotal = quantize(qty * price)
    line_total = quantize(subtotal - disc + tax_amt + ship)
    if line_total < ZERO:
        raise ValueError("Line total cannot be negative")
    return LineTotals(
        quantity=qty,
        unit_price=quantize(price),
        discount=quantize(disc),
        tax=quantize(tax_amt),
        shipping=quantize(ship),
        subtotal=subtotal,
        line_total=line_total,
    )


def compute_document_totals(
    lines: list[LineTotals],
    *,
    document_discount: Decimal | int | str = ZERO,
    document_shipping: Decimal | int | str = ZERO,
    document_tax: Decimal | int | str = ZERO,
) -> DocumentTotals:
    subtotal = quantize(sum((ln.subtotal for ln in lines), ZERO))
    line_discount = quantize(sum((ln.discount for ln in lines), ZERO))
    line_tax = quantize(sum((ln.tax for ln in lines), ZERO))
    line_ship = quantize(sum((ln.shipping for ln in lines), ZERO))
    doc_disc = money(document_discount)
    doc_ship = money(document_shipping)
    doc_tax = money(document_tax)
    discount_total = quantize(line_discount + doc_disc)
    charge_total = quantize(line_ship + doc_ship)
    tax_total = quantize(line_tax + doc_tax)
    total = quantize(subtotal - discount_total + charge_total + tax_total)
    if total < ZERO:
        raise ValueError("Document total cannot be negative")
    return DocumentTotals(
        subtotal=subtotal,
        discount_total=discount_total,
        charge_total=charge_total,
        tax_total=tax_total,
        total=total,
        lines=lines,
    )
