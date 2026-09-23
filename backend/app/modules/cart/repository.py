"""Cart repositories."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class CartRepository(BaseRepository):
    collection_name = CollectionName.CARTS

    async def get_for_buyer(
        self, buyer_business_id: str, *, session: MongoSession = None
    ) -> dict[str, Any] | None:
        return await self.find_one(
            {"buyer_business_id": parse_object_id(buyer_business_id)},
            session=session,
        )


class CartItemRepository(BaseRepository):
    collection_name = CollectionName.CART_ITEMS

    async def list_for_buyer(
        self, buyer_business_id: str, *, session: MongoSession = None
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"buyer_business_id": parse_object_id(buyer_business_id)},
            limit=500,
            sort=[("updated_at", -1)],
            session=session,
        )

    async def get_for_buyer_product(
        self,
        buyer_business_id: str,
        product_id: str,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        return await self.find_one(
            {
                "buyer_business_id": parse_object_id(buyer_business_id),
                "product_id": parse_object_id(product_id),
            },
            session=session,
        )

    async def delete_for_buyer(
        self, buyer_business_id: str, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"buyer_business_id": parse_object_id(buyer_business_id)},
            session=session,
        )
        return int(result.deleted_count)

    async def delete_for_product(
        self, product_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"product_id": parse_object_id(str(product_id))},
            session=session,
        )
        return int(result.deleted_count)

    async def delete_for_supplier(
        self, supplier_business_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"supplier_business_id": parse_object_id(str(supplier_business_id))},
            session=session,
        )
        return int(result.deleted_count)

    async def get_for_buyer_item(
        self,
        buyer_business_id: str,
        item_id: str | ObjectId,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        item = await self.get_by_id(item_id, session=session)
        if item is None:
            return None
        if str(item.get("buyer_business_id")) != buyer_business_id:
            return None
        return item
