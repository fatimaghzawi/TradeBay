
from __future__ import annotations

from typing import Any, cast

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClientSession, AsyncIOMotorCollection
from pymongo import ReturnDocument

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.shared.utils.objectid import parse_object_id

MongoSession = AsyncIOMotorClientSession | None

class BaseRepository:
    collection_name: CollectionName

    def __init__(self, collection: AsyncIOMotorCollection[Any] | None = None) -> None:
        self._collection = collection

    @property
    def collection(self) -> AsyncIOMotorCollection[Any]:
        if self._collection is not None:
            return self._collection
        return mongo_manager.collection(self.collection_name)

    async def create(
        self, document: dict[str, Any], *, session: MongoSession = None
    ) -> dict[str, Any]:
        payload = dict(document)
        if "_id" not in payload:
            payload["_id"] = ObjectId()
        await self.collection.insert_one(payload, session=session)
        return payload

    async def get_by_id(
        self, document_id: str | ObjectId, *, session: MongoSession = None
    ) -> dict[str, Any] | None:
        oid = document_id if isinstance(document_id, ObjectId) else parse_object_id(str(document_id))
        return await self.collection.find_one({"_id": oid}, session=session)

    async def find_one(
        self, filter_query: dict[str, Any], *, session: MongoSession = None
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(filter_query, session=session)

    async def find_many(
        self,
        filter_query: dict[str, Any] | None = None,
        *,
        skip: int = 0,
        limit: int = 20,
        sort: list[tuple[str, int]] | None = None,
        session: MongoSession = None,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(filter_query or {}, session=session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count(
        self, filter_query: dict[str, Any] | None = None, *, session: MongoSession = None
    ) -> int:
        return await self.collection.count_documents(filter_query or {}, session=session)

    async def update(
        self,
        document_id: str | ObjectId,
        update_fields: dict[str, Any],
        *,
        upsert: bool = False,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        oid = document_id if isinstance(document_id, ObjectId) else parse_object_id(str(document_id))
        result = await self.collection.find_one_and_update(
            {"_id": oid},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            upsert=upsert,
            session=session,
        )
        return cast(dict[str, Any] | None, result)

    async def delete(
        self, document_id: str | ObjectId, *, session: MongoSession = None
    ) -> bool:
        oid = document_id if isinstance(document_id, ObjectId) else parse_object_id(str(document_id))
        result = await self.collection.delete_one({"_id": oid}, session=session)
        return result.deleted_count == 1

class AppendOnlyRepository(BaseRepository):

    async def update(
        self,
        document_id: str | ObjectId,
        update_fields: dict[str, Any],
        *,
        upsert: bool = False,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        raise RuntimeError(f"{self.collection_name} is append-only")

    async def delete(
        self, document_id: str | ObjectId, *, session: MongoSession = None
    ) -> bool:
        raise RuntimeError(f"{self.collection_name} is append-only")
