"""Catalog API placeholders."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.catalog.dependencies import get_product_service
from app.modules.catalog.service import ProductService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated

router = APIRouter(tags=["Catalog"])


@router.get("/products", summary="List products")
async def list_products(
    _: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[ProductService, Depends(get_product_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    pagination = PaginationParams(page=page, page_size=page_size)
    items, total = await service.list_products(pagination)
    serialized = [
        {
            "id": str(item["_id"]),
            "name": item.get("name"),
            "sku": item.get("sku"),
            "status": item.get("status"),
        }
        for item in items
    ]
    return paginated(serialized, page=page, page_size=page_size, total=total)


@router.get("/categories", summary="List categories (scaffolded)")
async def list_categories(
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/inventory", summary="Inventory listing (scaffolded)")
async def list_inventory(
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return paginated([], total=0)
