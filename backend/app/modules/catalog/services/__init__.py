"""Canonical catalog services live in `app.modules.catalog.service`.

This package re-exports them so older `catalog.services.*` imports stay valid.
"""

from app.modules.catalog.service import (
    CategoryService,
    InventoryService,
    PricingService,
    ProductService,
)

__all__ = [
    "CategoryService",
    "InventoryService",
    "PricingService",
    "ProductService",
]
