"""Catalog services. InventoryService is the only layer that mutates stock."""

from __future__ import annotations

from typing import Any

from app.modules.catalog.repository import (
    CategoryRepository,
    InventoryRepository,
    InventoryTransactionRepository,
    ProductRepository,
)
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class CategoryService:
    def __init__(self, repo: CategoryRepository | None = None) -> None:
        self.repo = repo or CategoryRepository()

    async def list_categories(self, pagination: PaginationParams) -> tuple[list[dict[str, Any]], int]:
        filt = {"is_active": True}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        total = await self.repo.count(filt)
        return items, total


class ProductService:
    def __init__(self, repo: ProductRepository | None = None) -> None:
        self.repo = repo or ProductRepository()

    async def list_products(self, pagination: PaginationParams) -> tuple[list[dict[str, Any]], int]:
        """Marketplace discovery: only active products. Drafts never leak across businesses."""
        filt = {"status": "active"}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        total = await self.repo.count(filt)
        return items, total


class PricingService:
    """Live catalog pricing tiers. Agreed deal prices live on quotation/order items."""

    async def get_tiers_for_product(self, product_id: str) -> list[dict[str, Any]]:
        _ = product_id
        return []


class InventoryService:
    """SOLE authority for inventory mutations.

    Mutations must run inside `run_in_transaction` together with an
    `inventory_transactions` row. Implementation of reserve/release/sale is deferred.
    """

    def __init__(
        self,
        inventories: InventoryRepository | None = None,
        transactions: InventoryTransactionRepository | None = None,
    ) -> None:
        self.inventories = inventories or InventoryRepository()
        self.transactions = transactions or InventoryTransactionRepository()

    async def get_state(self, product_id: str) -> dict[str, Any] | None:
        return await self.inventories.find_one({"product_id": parse_object_id(product_id)})

    async def adjust(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("Inventory mutations are deferred to domain implementation")

    async def reserve(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("Inventory reservation is deferred")
