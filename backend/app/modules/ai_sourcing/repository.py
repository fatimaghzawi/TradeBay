"""AI Sourcing persistence."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class SourcingRequestRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_REQUESTS

    async def list_for_business(
        self,
        business_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {"buyer_business_id": parse_object_id(business_id)},
            skip=skip,
            limit=limit,
            sort=[("updated_at", -1)],
        )

    async def count_for_business(self, business_id: str) -> int:
        return await self.count({"buyer_business_id": parse_object_id(business_id)})


class SourcingRequestItemRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_REQUEST_ITEMS

    async def list_for_request(self, sourcing_request_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"sourcing_request_id": parse_object_id(str(sourcing_request_id))},
            limit=100,
            sort=[("created_at", 1)],
        )

    async def delete_for_request(
        self, sourcing_request_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"sourcing_request_id": parse_object_id(str(sourcing_request_id))},
            session=session,
        )
        return int(result.deleted_count)


class SourcingRecommendationRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_RECOMMENDATIONS

    async def list_for_request(self, sourcing_request_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"sourcing_request_id": parse_object_id(str(sourcing_request_id))},
            limit=100,
            sort=[("match_score", -1), ("created_at", -1)],
        )

    async def delete_for_request(
        self, sourcing_request_id: str | ObjectId, *, session: MongoSession = None
    ) -> int:
        result = await self.collection.delete_many(
            {"sourcing_request_id": parse_object_id(str(sourcing_request_id))},
            session=session,
        )
        return int(result.deleted_count)


class BusinessProcurementProfileRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PROCUREMENT_PROFILES

    async def get_by_business(self, business_id: str) -> dict[str, Any] | None:
        return await self.find_one({"business_account_id": parse_object_id(business_id)})
