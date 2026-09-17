"""MongoDB multi-document transactions.

Confirm + reserve, invoice + ledger post, and payout + routing row must run
inside one transaction. That requires a replica set (see docker-compose).
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from pymongo.client_session import ClientSession

from app.db.mongodb import mongo_manager

T = TypeVar("T")

TransactionalWork = Callable[[ClientSession], Coroutine[Any, Any, T]]


async def run_in_transaction(work: TransactionalWork[T]) -> T:
    """Run `work(session)` inside a Mongo transaction and return its result."""

    async with await mongo_manager.client.start_session() as session:
        return await session.with_transaction(work)
