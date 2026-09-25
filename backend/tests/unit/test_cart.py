
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.modules.cart.exceptions import CartBuyerRequiredError, CartEmptyError
from app.modules.cart.service import CartService
from app.modules.identity.constants import BusinessAccountType


def _buyer() -> dict[str, Any]:
    return {"_id": "aaaaaaaaaaaaaaaaaaaaaaaa", "type": BusinessAccountType.BUYER}

@pytest.mark.asyncio
async def test_cart_requires_buyer_company() -> None:
    service = CartService()
    with pytest.raises(CartBuyerRequiredError):
        await service.get_cart(business={"_id": "x", "type": BusinessAccountType.SUPPLIER})

@pytest.mark.asyncio
async def test_checkout_rejects_empty_cart() -> None:
    service = CartService()
    service._ensure_cart = AsyncMock(return_value={"_id": "cart"})  # type: ignore[method-assign]
    service.items.list_for_buyer = AsyncMock(return_value=[])  # type: ignore[method-assign]
    with pytest.raises(CartEmptyError):
        await service.checkout(
            user_id="bbbbbbbbbbbbbbbbbbbbbbbb",
            business=_buyer(),
            publish=False,
        )

def test_money_str_formats_decimal128_like() -> None:
    from app.modules.cart.service import _money_str

    class Fake:
        def to_decimal(self) -> Decimal:
            return Decimal("12.50")

    assert _money_str(Fake()) == "12.50"
    assert _money_str(None) is None
