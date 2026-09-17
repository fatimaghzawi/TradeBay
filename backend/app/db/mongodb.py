"""Central async MongoDB connection manager."""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.indexes import ensure_indexes

logger = get_logger(__name__)


class MongoManager:
    """Process-wide Motor client. Created on startup, closed on shutdown."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient[Any] | None = None
        self._database: AsyncIOMotorDatabase[Any] | None = None
        self._indexes_ready = False

    @property
    def client(self) -> AsyncIOMotorClient[Any]:
        if self._client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self._client

    @property
    def database(self) -> AsyncIOMotorDatabase[Any]:
        if self._database is None:
            raise RuntimeError("MongoDB database is not connected")
        return self._database

    def collection(self, name: CollectionName | str) -> AsyncIOMotorCollection[Any]:
        return self.database[str(name)]

    async def connect(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if self._client is not None:
            return
        self._client = AsyncIOMotorClient(
            settings.mongodb_uri,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=5000,
        )
        self._database = self._client[settings.mongodb_database]
        await self.client.admin.command("ping")
        logger.info("mongodb_connected", database=settings.mongodb_database)
        await ensure_indexes(self.database)
        self._indexes_ready = True
        logger.info("mongodb_indexes_ensured")
        from app.db.seed import seed_startup

        await seed_startup()
        logger.info("mongodb_seed_ensured")

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            self._indexes_ready = False
            logger.info("mongodb_disconnected")

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            logger.warning("mongodb_ping_failed")
            return False

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self._indexes_ready


mongo_manager = MongoManager()
