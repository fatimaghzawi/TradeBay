"""MongoDB multi-document transactions.

Confirm + reserve, invoice + ledger post, and Identity atomic flows (business
create, invitation accept, password reset, suspension) should run inside one
transaction when the deployment is a replica set (see docker-compose).

CI and some local installs use standalone MongoDB, which does not support
transactions. In that case work runs without a session so the same code path
still executes.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

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


async def run_in_transaction(work: TransactionalWork[T]) -> T:
    """Run `work(session)` inside a Mongo transaction when the server allows it."""

    if not await transactions_supported():
        return await work(None)

    async with await mongo_manager.client.start_session() as session:
        return await session.with_transaction(work)
