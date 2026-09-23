"""Reusable audit logging. Domain modules must not roll their own audit writers."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.core.constants import SENSITIVE_LOG_FIELDS
from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
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
        if value is None:
            continue
        lowered = key.lower()
        if lowered in _SECRET_METADATA_KEYS or any(secret in lowered for secret in _SECRET_METADATA_KEYS):
            continue
        cleaned[key] = value
    return cleaned


def _person_label(user: dict[str, Any] | None) -> str | None:
    if not user:
        return None
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    if name:
        return name
    email = user.get("email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return None


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
        meta = _sanitize_metadata(metadata or {})
        if resolved_user and not meta.get("actor_name"):
            labels = await self._user_labels({str(resolved_user)})
            actor = labels.get(str(resolved_user))
            if actor:
                meta["actor_name"] = actor
        document: dict[str, Any] = {
            "action": action,
            "resource_type": resource_type,
            "resource_id": ObjectId(str(resource_id)) if resource_id else None,
            "business_account_id": (
                ObjectId(str(business_account_id)) if business_account_id else None
            ),
            "user_id": ObjectId(str(resolved_user)) if resolved_user else None,
            "metadata": meta,
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
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self._business_filter(
            business_account_id,
            action=action,
            resource_type=resource_type,
        )
        rows = await self._repository.find_many(
            query,
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
        )
        return await self._serialize_many(rows)

    async def count_for_business(
        self,
        business_account_id: str | ObjectId,
        *,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> int:
        query = self._business_filter(
            business_account_id,
            action=action,
            resource_type=resource_type,
        )
        return await self._repository.count(query)

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
        enriched = await self._serialize_many([row])
        return enriched[0] if enriched else None

    @staticmethod
    def _business_filter(
        business_account_id: str | ObjectId,
        *,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"business_account_id": ObjectId(str(business_account_id))}
        if action:
            query["action"] = action.strip()
        if resource_type:
            query["resource_type"] = resource_type.strip()
        return query

    async def _serialize_many(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        user_ids: set[str] = set()
        role_ids: set[str] = set()
        invitation_ids: set[str] = set()
        for row in rows:
            if row.get("user_id"):
                user_ids.add(str(row["user_id"]))
            meta = row.get("metadata") or {}
            for key in ("target_user_id",):
                value = meta.get(key)
                if value:
                    user_ids.add(str(value))
            for key in ("role_id",):
                value = meta.get(key)
                if value:
                    role_ids.add(str(value))
            if row.get("resource_type") == "invitation" and row.get("resource_id"):
                invitation_ids.add(str(row["resource_id"]))
            if row.get("resource_type") == "role" and row.get("resource_id"):
                role_ids.add(str(row["resource_id"]))

        user_labels = await self._user_labels(user_ids)
        role_names = await self._role_names(role_ids)
        invitation_emails = await self._invitation_emails(invitation_ids)
        return [
            self._serialize(
                row,
                user_labels=user_labels,
                role_names=role_names,
                invitation_emails=invitation_emails,
            )
            for row in rows
        ]

    @staticmethod
    def _serialize(
        row: dict[str, Any],
        *,
        user_labels: dict[str, str] | None = None,
        role_names: dict[str, str] | None = None,
        invitation_emails: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        user_labels = user_labels or {}
        role_names = role_names or {}
        invitation_emails = invitation_emails or {}
        meta = dict(row.get("metadata") or {})
        user_id = str(row["user_id"]) if row.get("user_id") else None

        if user_id and not meta.get("actor_name") and user_id in user_labels:
            meta["actor_name"] = user_labels[user_id]

        target_id = meta.get("target_user_id")
        if target_id:
            tid = str(target_id)
            if tid in user_labels:
                meta.setdefault("member_name", user_labels[tid])
                meta.setdefault("target_name", user_labels[tid])

        role_id = meta.get("role_id") or (
            str(row["resource_id"])
            if row.get("resource_type") == "role" and row.get("resource_id")
            else None
        )
        if role_id and not meta.get("role_name") and str(role_id) in role_names:
            meta["role_name"] = role_names[str(role_id)]

        if (
            row.get("resource_type") == "invitation"
            and row.get("resource_id")
            and not meta.get("invited_email")
        ):
            email = invitation_emails.get(str(row["resource_id"]))
            if email:
                meta["invited_email"] = email

        # Accept events: actor is the joiner — prefer their name for member copy.
        action = str(row.get("action") or "").upper()
        if action in {"INVITATION_ACCEPTED", "MEMBER_JOINED"}:
            if user_id and user_id in user_labels:
                meta["member_name"] = user_labels[user_id]
            elif not meta.get("member_name") and meta.get("invited_email"):
                meta["member_name"] = meta["invited_email"]
        elif (
            row.get("resource_type") == "invitation"
            and meta.get("invited_email")
            and not meta.get("member_name")
        ):
            meta["member_name"] = meta["invited_email"]

        return {
            "id": str(row["_id"]),
            "action": row.get("action"),
            "resource_type": row.get("resource_type"),
            "resource_id": str(row["resource_id"]) if row.get("resource_id") else None,
            "business_account_id": (
                str(row["business_account_id"]) if row.get("business_account_id") else None
            ),
            "user_id": user_id,
            "metadata": meta,
            "ip_address": row.get("ip_address"),
            "created_at": row.get("created_at"),
        }

    async def _user_labels(self, user_ids: set[str]) -> dict[str, str]:
        oids = self._safe_oids(user_ids)
        if not oids:
            return {}
        cursor = mongo_manager.collection(CollectionName.USERS).find(
            {"_id": {"$in": oids}},
            {"first_name": 1, "last_name": 1, "email": 1},
        )
        rows = await cursor.to_list(length=len(oids))
        labels: dict[str, str] = {}
        for row in rows:
            label = _person_label(row)
            if label:
                labels[str(row["_id"])] = label
        return labels

    async def _role_names(self, role_ids: set[str]) -> dict[str, str]:
        oids = self._safe_oids(role_ids)
        if not oids:
            return {}
        cursor = mongo_manager.collection(CollectionName.ROLES).find(
            {"_id": {"$in": oids}},
            {"name": 1},
        )
        rows = await cursor.to_list(length=len(oids))
        return {
            str(row["_id"]): str(row["name"])
            for row in rows
            if isinstance(row.get("name"), str) and row["name"].strip()
        }

    async def _invitation_emails(self, invitation_ids: set[str]) -> dict[str, str]:
        oids = self._safe_oids(invitation_ids)
        if not oids:
            return {}
        cursor = mongo_manager.collection(CollectionName.INVITATIONS).find(
            {"_id": {"$in": oids}},
            {"invited_email": 1},
        )
        rows = await cursor.to_list(length=len(oids))
        return {
            str(row["_id"]): str(row["invited_email"])
            for row in rows
            if isinstance(row.get("invited_email"), str) and row["invited_email"].strip()
        }

    @staticmethod
    def _safe_oids(raw_ids: set[str]) -> list[ObjectId]:
        oids: list[ObjectId] = []
        for value in raw_ids:
            text = str(value)
            if ObjectId.is_valid(text):
                oids.append(ObjectId(text))
        return oids
