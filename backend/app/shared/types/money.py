"""Money type.

Money is persisted as BSON ``Decimal128`` (ERD requirement) and handled as
``Decimal`` in Python. ``float`` is rejected on the way in — binary floats
cannot represent currency exactly and the error compounds across ledger sums.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from bson import Decimal128
from pydantic import BeforeValidator


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, (bool, float)):
        raise TypeError("Money must be Decimal, Decimal128, int or str — not float")
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"Cannot read money from {type(value).__name__}")


def _to_optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return _to_decimal(value)


Money = Annotated[Decimal, BeforeValidator(_to_decimal)]
"""A monetary amount or rate. Stored as Decimal128."""

OptionalMoney = Annotated[Decimal | None, BeforeValidator(_to_optional_decimal)]
"""A nullable monetary amount or rate."""


def to_decimal128(value: Decimal) -> Decimal128:
    return Decimal128(value)
