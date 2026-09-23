"""Catalog & inventory HTTP routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.modules.catalog.schemas import (
    CreateCategoryRequest,
    CreatePriceRequest,
    CreateProductRequest,
    StockQuantityRequest,
    UpdateCategoryRequest,
    UpdatePriceRequest,
    UpdateProductRequest,
)
from app.modules.catalog.service import CatalogService
from app.modules.identity.dependencies import (
    AuthContext,
    get_optional_user,
    require_permission,
    require_seller,
)
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

categories_router = APIRouter(prefix="/catalog/categories", tags=["Catalog"])
products_router = APIRouter(prefix="/catalog/products", tags=["Catalog"])
inventory_router = APIRouter(prefix="/inventory/products", tags=["Inventory"])


def get_catalog_service() -> CatalogService:
    return CatalogService()


# ── Categories (platform manage / everyone read) ───────────────────────────


@categories_router.post("", summary="Create category")
async def create_category(
    body: CreateCategoryRequest,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    return success(
        await service.create_category(
            name=body.name,
            slug=body.slug,
            description=body.description,
            parent_category_id=body.parent_category_id,
            display_order=body.display_order,
            is_active=body.is_active,
        )
    )


@categories_router.get("", summary="List categories")
async def list_categories(
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    parent_category_id: str | None = None,
    active_only: bool = Query(False),
) -> dict[str, Any]:
    # Guests may browse the live taxonomy (active categories only).
    if auth is None:
        active_only = True
    elif not auth.has_permission("categories", "read"):
        from app.modules.identity.exceptions import PermissionDeniedError

        raise PermissionDeniedError("categories", "read")
    items, total = await service.list_categories(
        parent_category_id=parent_category_id,
        active_only=active_only,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@categories_router.get("/{category_id}", summary="Get category")
async def get_category(
    category_id: str,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "read"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    return success(await service.get_category(category_id))


@categories_router.patch("/{category_id}", summary="Update category")
async def update_category(
    category_id: str,
    body: UpdateCategoryRequest,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    return success(
        await service.update_category(
            category_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            parent_category_id=body.parent_category_id,
            clear_parent=body.clear_parent,
            display_order=body.display_order,
            is_active=body.is_active,
        )
    )


@categories_router.delete("/{category_id}", summary="Soft-delete category (deactivate)")
async def delete_category(
    category_id: str,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    await service.delete_category(category_id)
    return success({"deleted": True, "soft_deleted": True})


@categories_router.post(
    "/{category_id}/image",
    summary="Upload category image (platform)",
)
async def upload_category_image(
    category_id: str,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    from app.modules.catalog.storage import save_category_image

    # Ensure category exists before writing to disk.
    await service.get_category(category_id)
    url = await save_category_image(category_id=category_id, upload=file)
    return success(await service.set_category_image(category_id, url=url))


@categories_router.delete(
    "/{category_id}/image",
    summary="Remove category image (platform)",
)
async def delete_category_image(
    category_id: str,
    _auth: Annotated[AuthContext, Depends(require_permission("categories", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    return success(await service.clear_category_image(category_id))


# ── Products ───────────────────────────────────────────────────────────────


@products_router.post("", summary="Create product")
async def create_product(
    body: CreateProductRequest,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.create_product(
            business_id=auth.business_id,
            category_id=body.category_id,
            sku=body.sku,
            name=body.name,
            slug=body.slug,
            description=body.description,
            unit=body.unit,
            origin=body.origin,
            moq=body.moq,
            lead_time_days=body.lead_time_days,
            status=body.status,
            is_featured=body.is_featured,
        )
    )


@products_router.get("", summary="List products")
async def list_products(
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    supplier_business_id: str | None = None,
    category_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    featured: bool | None = Query(None),
    include_details: bool = Query(False),
) -> dict[str, Any]:
    # Guests browse the public marketplace (active listings only).
    if auth is None:
        items, total = await service.list_products(
            viewer_business_id=None,
            viewer_business_type=None,
            can_manage=False,
            supplier_business_id=supplier_business_id,
            category_id=category_id,
            status="active",
            q=q,
            featured=featured,
            page=pagination.page,
            page_size=min(pagination.page_size, 100),
            include_details=include_details,
        )
        return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)

    if not auth.has_permission("products", "read"):
        from app.modules.identity.exceptions import PermissionDeniedError

        raise PermissionDeniedError("products", "read")

    items, total = await service.list_products(
        viewer_business_id=auth.business_id,
        viewer_business_type=str(auth.business.get("type")) if auth.business else None,
        can_manage=auth.has_permission("products", "manage"),
        supplier_business_id=supplier_business_id,
        category_id=category_id,
        status=status,
        q=q,
        featured=featured,
        page=pagination.page,
        page_size=pagination.page_size,
        include_details=include_details,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@products_router.get("/{product_id}", summary="Get product")
async def get_product(
    product_id: str,
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    if auth is None:
        return success(
            await service.get_product(
                product_id,
                viewer_business_id=None,
                can_manage=False,
                include_details=True,
            )
        )
    if not auth.has_permission("products", "read"):
        from app.modules.identity.exceptions import PermissionDeniedError

        raise PermissionDeniedError("products", "read")
    return success(
        await service.get_product(
            product_id,
            viewer_business_id=auth.business_id,
            can_manage=auth.has_permission("products", "manage"),
            include_details=True,
            viewer_business_type=str(auth.business.get("type")) if auth.business else None,
        )
    )


@products_router.patch("/{product_id}", summary="Update product")
async def update_product(
    product_id: str,
    body: UpdateProductRequest,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.update_product(
            product_id,
            business_id=auth.business_id,
            category_id=body.category_id,
            sku=body.sku,
            name=body.name,
            slug=body.slug,
            description=body.description,
            unit=body.unit.value if body.unit else None,
            origin=body.origin,
            moq=body.moq,
            lead_time_days=body.lead_time_days,
            status=body.status,
            is_featured=body.is_featured,
        )
    )


@products_router.delete("/{product_id}", summary="Soft-delete product (deactivate)")
async def delete_product(
    product_id: str,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    await service.delete_product(product_id, business_id=auth.business_id)
    return success({"deactivated": True, "soft_deleted": True})


@products_router.get("/{product_id}/prices", summary="List price tiers")
async def list_prices(
    product_id: str,
    _auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    quantity: int | None = Query(None, ge=1),
) -> dict[str, Any]:
    tiers = await service.list_prices(product_id)
    meta: dict[str, Any] = {}
    if quantity is not None:
        meta["matched_tier"] = service.resolve_unit_price(tiers, quantity)
    return success(tiers, meta=meta)


@products_router.post("/{product_id}/prices", summary="Create price tier")
async def create_price(
    product_id: str,
    body: CreatePriceRequest,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.create_price(
            product_id,
            business_id=auth.business_id,
            min_quantity=body.min_quantity,
            max_quantity=body.max_quantity,
            unit_price=body.unit_price,
            currency=body.currency,
            is_active=body.is_active,
        )
    )


@products_router.patch("/{product_id}/prices/{price_id}", summary="Update price tier")
async def update_price(
    product_id: str,
    price_id: str,
    body: UpdatePriceRequest,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.update_price(
            product_id,
            price_id,
            business_id=auth.business_id,
            min_quantity=body.min_quantity,
            max_quantity=body.max_quantity,
            clear_max_quantity=body.clear_max_quantity,
            unit_price=body.unit_price,
            currency=body.currency,
            is_active=body.is_active,
        )
    )


@products_router.delete("/{product_id}/prices/{price_id}", summary="Soft-delete price tier")
async def delete_price(
    product_id: str,
    price_id: str,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    await service.delete_price(product_id, price_id, business_id=auth.business_id)
    return success({"deleted": True, "soft_deleted": True})


@products_router.post("/{product_id}/images", summary="Upload product image")
async def upload_product_image(
    product_id: str,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None),
    is_primary: bool = Form(default=False),
) -> dict[str, Any]:
    assert auth.business_id is not None
    from app.modules.catalog.storage import save_product_image

    url = await save_product_image(product_id=product_id, upload=file)
    return success(
        await service.add_product_image(
            product_id,
            business_id=auth.business_id,
            url=url,
            alt_text=alt_text,
            is_primary=is_primary,
        )
    )


@products_router.patch(
    "/{product_id}/images/{image_id}/primary",
    summary="Set primary product image",
)
async def set_primary_product_image(
    product_id: str,
    image_id: str,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.set_primary_image(
            product_id,
            image_id,
            business_id=auth.business_id,
        )
    )


@products_router.delete(
    "/{product_id}/images/{image_id}",
    summary="Soft-delete product image",
)
async def delete_product_image(
    product_id: str,
    image_id: str,
    auth: Annotated[AuthContext, Depends(require_seller("products", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    await service.delete_product_image(
        product_id,
        image_id,
        business_id=auth.business_id,
    )
    return success({"deleted": True, "soft_deleted": True})


# ── Inventory ──────────────────────────────────────────────────────────────


@inventory_router.get("/{product_id}", summary="Get current inventory")
async def get_inventory(
    product_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("inventory", "read"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    # Own-company managers stay in their catalog; buyers may view active availability.
    require_own = auth.has_permission("inventory", "manage")
    return success(
        await service.get_inventory(
            product_id,
            business_id=auth.business_id,
            require_own=require_own,
        )
    )


@inventory_router.post("/{product_id}/stock", summary="Add stock (stock received)")
async def add_stock(
    product_id: str,
    body: StockQuantityRequest,
    auth: Annotated[AuthContext, Depends(require_seller("inventory", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.add_stock(
            product_id,
            business_id=auth.business_id,
            user_id=auth.user_id,
            quantity=body.quantity,
            reason=body.reason,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        )
    )


@inventory_router.post("/{product_id}/reserve", summary="Reserve stock")
async def reserve_stock(
    product_id: str,
    body: StockQuantityRequest,
    auth: Annotated[AuthContext, Depends(require_seller("inventory", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.reserve_stock(
            product_id,
            business_id=auth.business_id,
            user_id=auth.user_id,
            quantity=body.quantity,
            reason=body.reason,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        )
    )


@inventory_router.post("/{product_id}/release", summary="Release reserved stock")
async def release_stock(
    product_id: str,
    body: StockQuantityRequest,
    auth: Annotated[AuthContext, Depends(require_seller("inventory", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.release_stock(
            product_id,
            business_id=auth.business_id,
            user_id=auth.user_id,
            quantity=body.quantity,
            reason=body.reason,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        )
    )


@inventory_router.post("/{product_id}/sale", summary="Mark reserved stock as sold")
async def sale_stock(
    product_id: str,
    body: StockQuantityRequest,
    auth: Annotated[AuthContext, Depends(require_seller("inventory", "manage"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    return success(
        await service.sale_stock(
            product_id,
            business_id=auth.business_id,
            user_id=auth.user_id,
            quantity=body.quantity,
            reason=body.reason,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        )
    )


@inventory_router.get("/{product_id}/transactions", summary="List inventory transactions")
async def list_transactions(
    product_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("inventory", "read"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    assert auth.business_id is not None
    items, total = await service.list_transactions(
        product_id,
        business_id=auth.business_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


# Mount sub-routers after route declarations (include copies routes at call time).
router = APIRouter()
router.include_router(categories_router)
router.include_router(products_router)
router.include_router(inventory_router)
