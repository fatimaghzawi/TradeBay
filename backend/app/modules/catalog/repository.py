"""Catalog & inventory repositories — persistence only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bson import Decimal128, ObjectId
from pymongo import ReturnDocument

from app.db.collections import CollectionName
from app.shared.repositories.base import AppendOnlyRepository, BaseRepository, MongoSession
from app.shared.types.money import to_decimal128
from app.shared.utils.objectid import parse_object_id


def _qty(value: Decimal | int | str) -> Decimal128:
    if isinstance(value, Decimal):
        return to_decimal128(value)
    return to_decimal128(Decimal(value))


class CategoryRepository(BaseRepository):
    collection_name = CollectionName.CATEGORIES

    async def get_by_slug(self, slug: str, *, session: MongoSession = None) -> dict[str, Any] | None:
        return await self.find_one({"slug": slug}, session=session)

    async def list_children(
        self, parent_id: str | ObjectId | None, *, session: MongoSession = None
    ) -> list[dict[str, Any]]:
        if parent_id is None:
            query: dict[str, Any] = {"parent_category_id": None}
        else:
            query = {"parent_category_id": parse_object_id(str(parent_id))}
        return await self.find_many(query, limit=500, sort=[("display_order", 1), ("name", 1)], session=session)


class ProductRepository(BaseRepository):
    collection_name = CollectionName.PRODUCTS

    async def get_by_supplier_sku(
        self,
        supplier_id: str | ObjectId,
        sku: str,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        return await self.find_one(
            {
                "supplier_id": parse_object_id(str(supplier_id)),
                "sku": sku.strip().upper(),
            },
            session=session,
        )


class ProductPriceRepository(BaseRepository):
    collection_name = CollectionName.PRODUCT_PRICES

    async def list_for_product(
        self, product_id: str | ObjectId, *, session: MongoSession = None
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {
                "product_id": parse_object_id(str(product_id)),
                "deleted_at": None,
            },
            limit=100,
            sort=[("min_quantity", 1)],
            session=session,
        )

    async def count_active_for_product(
        self, product_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        return await self.count(
            {
                "product_id": parse_object_id(str(product_id)),
                "is_active": True,
                "deleted_at": None,
            },
            session=session,
        )


class ProductImageRepository(BaseRepository):
    collection_name = CollectionName.PRODUCT_IMAGES

    async def list_for_product(
        self, product_id: str | ObjectId, *, session: MongoSession = None
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {
                "product_id": parse_object_id(str(product_id)),
                "deleted_at": None,
            },
            limit=50,
            sort=[("display_order", 1), ("created_at", 1)],
            session=session,
        )


class InventoryRepository(BaseRepository):
    collection_name = CollectionName.INVENTORIES

    async def get_by_product(
        self, product_id: str | ObjectId, *, session: MongoSession = None
    ) -> dict[str, Any] | None:
        return await self.find_one(
            {"product_id": parse_object_id(str(product_id))},
            session=session,
        )

    async def conditional_reserve(
        self,
        *,
        product_id: str | ObjectId,
        quantity: Decimal,
        updated_at: Any,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        """Atomically move qty from available → reserved if enough stock exists."""
        qty = _qty(quantity)
        return await self.collection.find_one_and_update(
            {
                "product_id": parse_object_id(str(product_id)),
                "$expr": {"$gte": ["$available_quantity", qty]},
            },
            {
                "$inc": {"available_quantity": to_decimal128(-quantity), "reserved_quantity": qty},
                "$set": {"updated_at": updated_at},
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )

    async def conditional_release(
        self,
        *,
        product_id: str | ObjectId,
        quantity: Decimal,
        updated_at: Any,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        qty = _qty(quantity)
        return await self.collection.find_one_and_update(
            {
                "product_id": parse_object_id(str(product_id)),
                "$expr": {"$gte": ["$reserved_quantity", qty]},
            },
            {
                "$inc": {"available_quantity": qty, "reserved_quantity": to_decimal128(-quantity)},
                "$set": {"updated_at": updated_at},
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )

    async def conditional_sale(
        self,
        *,
        product_id: str | ObjectId,
        quantity: Decimal,
        updated_at: Any,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        """Consume reserved stock as sold (reserved ↓)."""
        qty = _qty(quantity)
        return await self.collection.find_one_and_update(
            {
                "product_id": parse_object_id(str(product_id)),
                "$expr": {"$gte": ["$reserved_quantity", qty]},
            },
            {
                "$inc": {"reserved_quantity": to_decimal128(-quantity)},
                "$set": {"updated_at": updated_at},
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )

    async def add_stock(
        self,
        *,
        product_id: str | ObjectId,
        quantity: Decimal,
        updated_at: Any,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        qty = _qty(quantity)
        return await self.collection.find_one_and_update(
            {"product_id": parse_object_id(str(product_id))},
            {
                "$inc": {"available_quantity": qty},
                "$set": {"updated_at": updated_at},
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )


class InventoryTransactionRepository(AppendOnlyRepository):
    collection_name = CollectionName.INVENTORY_TRANSACTIONS

    async def list_for_inventory(
        self,
        inventory_id: str | ObjectId,
        *,
        skip: int = 0,
        limit: int = 50,
        session: MongoSession = None,
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"inventory_id": parse_object_id(str(inventory_id))},
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
            session=session,
        )
