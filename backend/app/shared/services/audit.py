"""Reusable audit logging. Domain modules must not roll their own audit writers."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.constants import SENSITIVE_LOG_FIELDS
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository
from app.shared.utils.datetime import utc_now

logger = get_logger(__name__)

_SECRET_METADATA_KEYS = SENSITIVE_LOG_FIELDS | {
    "otp",
    "raw_token",
    "refresh_token_hash",
    "current_password",
    "new_password",
}


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if lowered in _SECRET_METADATA_KEYS or any(secret in lowered for secret in _SECRET_METADATA_KEYS):
            continue
        cleaned[key] = value
    return cleaned


class AuditLogRepository(BaseRepository):
    collection_name = CollectionName.AUDIT_LOGS


class AuditService:
    def __init__(self, repository: AuditLogRepository | None = None) -> None:
        self._repository = repository or AuditLogRepository()

    async def log(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | ObjectId | None = None,
        business_account_id: str | ObjectId | None = None,
        user_id: str | ObjectId | None = None,
        actor_id: str | ObjectId | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        resolved_user = user_id or actor_id
        document: dict[str, Any] = {
            "action": action,
            "resource_type": resource_type,
            "resource_id": ObjectId(str(resource_id)) if resource_id else None,
            "business_account_id": (
                ObjectId(str(business_account_id)) if business_account_id else None
            ),
            "user_id": ObjectId(str(resolved_user)) if resolved_user else None,
            "metadata": _sanitize_metadata(metadata or {}),
            "ip_address": ip_address,
            "created_at": utc_now(),
        }
        created = await self._repository.create(document)
        logger.info(
            "audit_logged",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
        )
        return created

    async def list_for_business(
        self,
        business_account_id: str | ObjectId,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = await self._repository.find_many(
            {"business_account_id": ObjectId(str(business_account_id))},
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
        )
        return [self._serialize(row) for row in rows]

    async def get_for_business(
        self,
        business_account_id: str | ObjectId,
        audit_log_id: str | ObjectId,
    ) -> dict[str, Any] | None:
        row = await self._repository.get_by_id(audit_log_id)
        if row is None:
            return None
        if str(row.get("business_account_id")) != str(business_account_id):
            return None
        return self._serialize(row)

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["_id"]),
            "action": row.get("action"),
            "resource_type": row.get("resource_type"),
            "resource_id": str(row["resource_id"]) if row.get("resource_id") else None,
            "business_account_id": (
                str(row["business_account_id"]) if row.get("business_account_id") else None
            ),
            "user_id": str(row["user_id"]) if row.get("user_id") else None,
            "metadata": row.get("metadata") or {},
            "ip_address": row.get("ip_address"),
            "created_at": row.get("created_at"),
        }
