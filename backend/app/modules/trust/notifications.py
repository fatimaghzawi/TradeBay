"""In-app notifications — list, unread count, mark read.

Writers live in `notify.py`. This is not chat (Communication) and not email.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.trust.constants import NotificationType
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

# Chat has its own Messages bell — never mix thread pings into Activity.
_CHAT_EXCLUDED = frozenset({NotificationType.CONVERSATION_MESSAGE})


class NotificationService:
    def _serialize(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "type": doc.get("type"),
            "title": doc.get("title"),
            "message": doc.get("message"),
            "reference_type": doc.get("reference_type"),
            "reference_id": str(doc["reference_id"]) if doc.get("reference_id") else None,
            "cta_path": doc.get("cta_path"),
            "recipient_business_id": str(doc["recipient_business_id"])
            if doc.get("recipient_business_id")
            else None,
            "is_read": bool(doc.get("is_read")),
            "read_at": doc.get("read_at").isoformat() if doc.get("read_at") else None,
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        }

    def _user_query(self, user_id: str, *, unread_only: bool = False) -> dict[str, Any]:
        query: dict[str, Any] = {
            "recipient_user_id": parse_object_id(user_id),
            "type": {"$nin": list(_CHAT_EXCLUDED)},
        }
        if unread_only:
            query["is_read"] = False
        return query

    async def list_for_user(
        self,
        *,
        user_id: str,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 30,
    ) -> tuple[list[dict[str, Any]], int]:
        query = self._user_query(user_id, unread_only=unread_only)
        col = mongo_manager.collection(CollectionName.NOTIFICATIONS)
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize(r) for r in rows], total

    async def unread_count(self, *, user_id: str) -> int:
        return await mongo_manager.collection(CollectionName.NOTIFICATIONS).count_documents(
            self._user_query(user_id, unread_only=True)
        )

    async def mark_read(self, *, user_id: str, notification_id: str) -> dict[str, Any]:
        col = mongo_manager.collection(CollectionName.NOTIFICATIONS)
        doc = await col.find_one({"_id": parse_object_id(notification_id)})
        if doc is None:
            raise NotFoundError("Notification not found")
        if str(doc.get("recipient_user_id")) != str(parse_object_id(user_id)):
            raise ForbiddenError("Not your notification")
        if not doc.get("is_read"):
            now = utc_now()
            await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"is_read": True, "read_at": now}},
            )
            doc["is_read"] = True
            doc["read_at"] = now
        return self._serialize(doc)

    async def mark_all_read(self, *, user_id: str) -> dict[str, Any]:
        now = utc_now()
        result = await mongo_manager.collection(CollectionName.NOTIFICATIONS).update_many(
            {"recipient_user_id": parse_object_id(user_id), "is_read": False},
            {"$set": {"is_read": True, "read_at": now}},
        )
        return {"marked": int(result.modified_count)}
