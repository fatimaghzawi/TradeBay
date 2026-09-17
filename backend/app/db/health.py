"""Database readiness helpers."""

from __future__ import annotations

from app.db.mongodb import mongo_manager


async def mongodb_is_healthy() -> bool:
    if not mongo_manager.is_ready:
        return False
    return await mongo_manager.ping()
