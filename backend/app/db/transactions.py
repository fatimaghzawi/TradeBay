
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from pymongo.errors import PyMongoError

from app.db.mongodb import mongo_manager
from app.shared.repositories.base import MongoSession

T = TypeVar("T")

TransactionalWork = Callable[[MongoSession], Coroutine[Any, Any, T]]

async def transactions_supported() -> bool:
    try:
        hello = await mongo_manager.client.admin.command("hello")
    except Exception:
        return False
    return bool(hello.get("setName"))

_TRANSIENT_ATTEMPTS = 4

async def run_in_transaction(work: TransactionalWork[T]) -> T:

    if not await transactions_supported():
        return await work(None)

    for attempt in range(1, _TRANSIENT_ATTEMPTS + 1):
        try:
            async with await mongo_manager.client.start_session() as session:
                return await session.with_transaction(work)
        except PyMongoError as exc:
            if attempt == _TRANSIENT_ATTEMPTS or not exc.has_error_label("TransientTransactionError"):
                raise
            await asyncio.sleep(0.05 * attempt)
    raise RuntimeError("unreachable")
