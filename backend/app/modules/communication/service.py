"""Communication service skeletons — no send/receive logic yet."""

from __future__ import annotations

from typing import Any

from app.modules.communication.repository import ConversationRepository, MessageRepository
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class ConversationService:
    def __init__(self, repo: ConversationRepository | None = None) -> None:
        self.repo = repo or ConversationRepository()

    async def list_conversations(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        oid = parse_object_id(business_id)
        filt = {"$or": [{"initiator_business_id": oid}, {"counterparty_business_id": oid}]}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.repo.count(filt)


class MessageService:
    """DEFERRED: send, edit, soft-delete, attachments."""

    def __init__(self, repo: MessageRepository | None = None) -> None:
        self.repo = repo or MessageRepository()

    async def list_for_conversation(
        self, conversation_id: str, pagination: PaginationParams
    ) -> tuple[list[dict[str, Any]], int]:
        filt = {"conversation_id": conversation_id}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.repo.count(filt)
