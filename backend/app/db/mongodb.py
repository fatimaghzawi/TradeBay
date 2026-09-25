
from __future__ import annotations

import asyncio
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.indexes import ensure_indexes

logger = get_logger(__name__)

class MongoManager:

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient[Any] | None = None
        self._database: AsyncIOMotorDatabase[Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._indexes_ready = False
        self._schema_task: asyncio.Task[None] | None = None

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
        loop = asyncio.get_running_loop()
        if self._client is not None:
            if self._loop is loop and not loop.is_closed():
                return
            logger.warning("mongodb_reconnecting_new_event_loop")
            await self.disconnect()

        attempts = 5 if not settings.is_production else 3
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                self._client = AsyncIOMotorClient(
                    settings.mongodb_uri,
                    uuidRepresentation="standard",
                    serverSelectionTimeoutMS=8000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=20000,
                    maxPoolSize=50,
                    minPoolSize=5,
                    retryWrites=True,
                    tz_aware=True,
                )
                self._database = self._client[settings.mongodb_database]
                self._loop = loop
                await self.client.admin.command("ping")
                logger.info("mongodb_connected", database=settings.mongodb_database, attempt=attempt)
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "mongodb_connect_retry",
                    attempt=attempt,
                    attempts=attempts,
                    error_type=type(exc).__name__,
                    error=str(exc)[:200],
                )
                if self._client is not None:
                    self._client.close()
                    self._client = None
                    self._database = None
                    self._loop = None
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** attempt, 10))
        else:
            assert last_error is not None
            raise last_error

                                                                            
                                                                               
                                                                     
        if settings.is_production or settings.is_test:
            await self._ensure_schema(settings)
                                                                             
            self._indexes_ready = True
        else:
            self._indexes_ready = True
            self._schema_task = asyncio.create_task(self._ensure_schema(settings))

    async def _ensure_schema(self, settings: Settings) -> None:
        try:
            if self._database is None:
                return
            await ensure_indexes(self.database, fail_fast=settings.is_production)
            logger.info("mongodb_indexes_ensured")
            from app.db.seed import seed_startup

            await seed_startup()
            logger.info("mongodb_seed_ensured")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mongodb_schema_ensure_failed")
            if settings.is_production or settings.is_test:
                                                                               
                self._indexes_ready = False
                raise

    async def disconnect(self) -> None:
        task = self._schema_task
        self._schema_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            self._loop = None
            self._indexes_ready = False
            logger.info("mongodb_disconnected")

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception as exc:
            logger.warning("mongodb_ping_failed", error=str(exc))
            return False

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self._indexes_ready

mongo_manager = MongoManager()
