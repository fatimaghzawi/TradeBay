"""Identity repositories — persistence only."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class UserRepository(BaseRepository):
    collection_name = CollectionName.USERS

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.find_one({"email": email.lower().strip()})


class BusinessRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_ACCOUNTS

    async def list_for_user(self, user_id: str | ObjectId) -> list[dict[str, Any]]:
        raise NotImplementedError("Resolve businesses through memberships, never a global scan")


class MembershipRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_MEMBERSHIPS

    async def get_active_membership(
        self,
        user_id: str | ObjectId,
        business_account_id: str | ObjectId,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        return await self.find_one(
            {
                "user_id": parse_object_id(str(user_id)),
                "business_account_id": parse_object_id(str(business_account_id)),
                "status": "active",
            },
            session=session,
        )

    async def list_for_user(self, user_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"user_id": parse_object_id(str(user_id)), "status": "active"},
            limit=100,
        )

    async def list_for_business(self, business_account_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {
                "business_account_id": parse_object_id(str(business_account_id)),
                "status": {"$in": ["active", "invited", "suspended"]},
            },
            limit=200,
        )


class RoleRepository(BaseRepository):
    collection_name = CollectionName.ROLES


class PermissionRepository(BaseRepository):
    collection_name = CollectionName.PERMISSIONS

    async def get_by_resource_action(self, resource: str, action: str) -> dict[str, Any] | None:
        return await self.find_one({"resource": resource, "action": action})


class RolePermissionRepository(BaseRepository):
    collection_name = CollectionName.ROLE_PERMISSIONS

    async def list_permission_ids_for_role(
        self, role_id: str | ObjectId, *, session: MongoSession = None
    ) -> list[ObjectId]:
        rows = await self.find_many(
            {"role_id": parse_object_id(str(role_id))},
            limit=500,
            session=session,
        )
        return [row["permission_id"] for row in rows]

    async def replace_for_role(
        self,
        role_id: str | ObjectId,
        permission_ids: list[ObjectId],
        *,
        created_at: Any,
        session: MongoSession = None,
    ) -> None:
        oid = parse_object_id(str(role_id))
        await self.collection.delete_many({"role_id": oid}, session=session)
        for pid in permission_ids:
            await self.create(
                {"role_id": oid, "permission_id": pid, "created_at": created_at},
                session=session,
            )


class InvitationRepository(BaseRepository):
    collection_name = CollectionName.INVITATIONS

    async def get_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return await self.find_one({"token_hash": token_hash})

    async def list_for_business(self, business_account_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"business_account_id": parse_object_id(str(business_account_id))},
            limit=200,
            sort=[("created_at", -1)],
        )


class AuthTokenRepository(BaseRepository):
    collection_name = CollectionName.AUTH_TOKENS

    async def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        return await self.find_one({"token_hash": token_hash})

    async def invalidate_open(
        self,
        user_id: str | ObjectId,
        purpose: str,
        *,
        at: Any,
        session: MongoSession = None,
    ) -> None:
        await self.collection.update_many(
            {
                "user_id": parse_object_id(str(user_id)),
                "purpose": purpose,
                "used_at": None,
                "invalidated_at": None,
            },
            {"$set": {"invalidated_at": at}},
            session=session,
        )


class SessionRepository(BaseRepository):
    collection_name = CollectionName.SESSIONS

    async def get_by_refresh_hash(self, refresh_token_hash: str) -> dict[str, Any] | None:
        return await self.find_one({"refresh_token_hash": refresh_token_hash})

    async def revoke(
        self,
        session_id: str | ObjectId,
        revoked_at: Any,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        return await self.update(session_id, {"revoked_at": revoked_at}, session=session)

    async def revoke_all_for_user(
        self,
        user_id: str | ObjectId,
        revoked_at: Any,
        *,
        session: MongoSession = None,
    ) -> int:
        result = await self.collection.update_many(
            {"user_id": parse_object_id(str(user_id)), "revoked_at": None},
            {"$set": {"revoked_at": revoked_at}},
            session=session,
        )
        return int(result.modified_count)


class SupplierProfileRepository(BaseRepository):
    collection_name = CollectionName.SUPPLIER_PROFILES

    async def get_by_business(self, business_account_id: str | ObjectId) -> dict[str, Any] | None:
        return await self.find_one({"business_account_id": parse_object_id(str(business_account_id))})
