from __future__ import annotations

from typing import Any

from app.modules.trust.repository import NotificationRepository


class NotificationService:
    def __init__(self, notification_repository: NotificationRepository) -> None:
        self._notifications = notification_repository

    async def send(self, *, user_id: str, title: str, body: str) -> dict[str, Any]:
        raise NotImplementedError

    async def list_for_user(self, *, user_id: str, skip: int = 0, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
        filter_doc = {"user_id": user_id}
        total = await self._notifications.count(filter_doc)
        items = await self._notifications.find_many(filter_doc, skip=skip, limit=limit, sort=[("created_at", -1)])
        return items, total
