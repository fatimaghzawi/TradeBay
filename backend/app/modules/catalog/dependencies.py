"""Catalog FastAPI dependencies."""

from app.modules.catalog.service import (
    CategoryService,
    InventoryService,
    PricingService,
    ProductService,
)


def get_product_service() -> ProductService:
    return ProductService()


def get_category_service() -> CategoryService:
    return CategoryService()


def get_pricing_service() -> PricingService:
    return PricingService()


def get_inventory_service() -> InventoryService:
    return InventoryService()
