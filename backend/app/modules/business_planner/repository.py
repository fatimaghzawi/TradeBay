
from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class BusinessPlanRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLANS

    async def list_for_user(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"user_id": parse_object_id(user_id)},
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )

    async def count_for_user(self, user_id: str) -> int:
        return await self.count({"user_id": parse_object_id(user_id)})

class BusinessPlanItemRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLAN_ITEMS

    async def list_for_plan(self, plan_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"business_plan_id": parse_object_id(str(plan_id))},
            limit=100,
            sort=[("priority", 1), ("created_at", 1)],
        )

    async def delete_for_plan(
        self, plan_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"business_plan_id": parse_object_id(str(plan_id))},
            session=session,
        )
        return int(result.deleted_count)

class PriceEstimateRepository(BaseRepository):
    collection_name = CollectionName.PRICE_ESTIMATES

    async def list_for_item(self, item_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"business_plan_item_id": parse_object_id(str(item_id))},
            limit=20,
            sort=[("calculated_at", -1)],
        )

    async def delete_for_items(
        self, item_ids: list[ObjectId], *, session: MongoSession = None
    ) -> int:
        if not item_ids:
            return 0
        result = await self.collection.delete_many(
            {"business_plan_item_id": {"$in": item_ids}},
            session=session,
        )
        return int(result.deleted_count)

class BusinessPlanSessionRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLAN_SESSIONS

    async def list_for_user(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"user_id": parse_object_id(user_id)},
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )

class BusinessPlanMessageRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLAN_MESSAGES

    async def list_for_plan(
        self,
        plan_id: str | ObjectId,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"business_plan_id": parse_object_id(str(plan_id))},
            limit=limit,
            sort=[("created_at", 1)],
        )
