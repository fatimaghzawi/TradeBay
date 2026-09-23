"""Buyer shopping cart HTTP routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.modules.cart.schemas import (
    AddCartItemRequest,
    CheckoutCartRequest,
    PlaceCartOrderRequest,
    UpdateCartItemRequest,
)
from app.modules.cart.service import CartService
from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.identity.http import client_ip
from app.shared.schemas.response import success

router = APIRouter(prefix="/cart", tags=["Cart"])


def get_cart_service() -> CartService:
    return CartService()


@router.get("", summary="Get the active buyer cart")
async def get_cart(
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(await service.get_cart(business=auth.business))


@router.get("/summary", summary="Cart item count for badges")
async def cart_summary(
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    cart = await service.get_cart(business=auth.business)
    return success(
        {
            "item_count": cart["item_count"],
            "quantity_total": cart["quantity_total"],
        }
    )


@router.post("/items", summary="Add a product to the cart")
async def add_cart_item(
    body: AddCartItemRequest,
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(
        await service.add_item(
            business=auth.business,
            product_id=body.product_id,
            quantity=body.quantity,
            suggested_unit_price=body.suggested_unit_price,
        )
    )


@router.patch("/items/{item_id}", summary="Update cart line quantity or suggested price")
async def update_cart_item(
    item_id: str,
    body: UpdateCartItemRequest,
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    fields = body.model_fields_set
    return success(
        await service.update_item(
            business=auth.business,
            item_id=item_id,
            quantity=body.quantity if "quantity" in fields else None,
            suggested_unit_price=(
                body.suggested_unit_price if "suggested_unit_price" in fields else None
            ),
            update_suggested_price="suggested_unit_price" in fields,
        )
    )


@router.delete("/items/{item_id}", summary="Remove a cart line")
async def remove_cart_item(
    item_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(await service.remove_item(business=auth.business, item_id=item_id))


@router.delete("", summary="Clear the cart")
async def clear_cart(
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(await service.clear_cart(business=auth.business))


@router.post("/checkout", summary="Turn the cart into an RFQ")
async def checkout_cart(
    body: CheckoutCartRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(
        await service.checkout(
            user_id=auth.user_id,
            business=auth.business,
            title=body.title,
            notes=body.notes,
            publish=body.publish,
            ip=client_ip(request),
        )
    )


@router.post("/order", summary="Place direct purchase orders from the cart")
async def place_cart_orders(
    body: PlaceCartOrderRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[CartService, Depends(get_cart_service)],
) -> dict[str, Any]:
    return success(
        await service.place_orders(
            user_id=auth.user_id,
            business=auth.business,
            notes=body.notes,
            ip=client_ip(request),
        )
    )
