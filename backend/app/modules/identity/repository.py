
from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.collections import CollectionName
from app.modules.identity.constants import MembershipStatus
from app.shared.repositories.base import BaseRepository, MongoSession
from app.shared.utils.objectid import parse_object_id


class UserRepository(BaseRepository):
    collection_name = CollectionName.USERS

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.find_one({"email": email.lower().strip()})

    async def set_avatar_url_for_ids(
        self,
        user_ids: list[Any],
        url: str,
        *,
        updated_at: Any,
    ) -> None:
        ids = [parse_object_id(str(user_id)) for user_id in user_ids if user_id is not None]
        if not ids:
            return
        await self.collection.update_many(
            {"_id": {"$in": ids}},
            {"$set": {"avatar_url": url, "updated_at": updated_at}},
        )

class BusinessRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_ACCOUNTS

    async def list_for_user(self, user_id: str | ObjectId) -> list[dict[str, Any]]:
        raise NotImplementedError("Resolve businesses through memberships, never a global scan")

    async def get_by_email_domain(self, email_domain: str) -> dict[str, Any] | None:
        domain = email_domain.lower().strip()
        if not domain:
            return None
        return await self.find_one({"email_domain": domain})

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
                "status": MembershipStatus.ACTIVE,
            },
            session=session,
        )

    async def list_for_user(self, user_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {"user_id": parse_object_id(str(user_id)), "status": MembershipStatus.ACTIVE},
            limit=100,
            sort=[("joined_at", -1), ("created_at", -1)],
        )

    async def list_for_business(self, business_account_id: str | ObjectId) -> list[dict[str, Any]]:
        return await self.find_many(
            {
                "business_account_id": parse_object_id(str(business_account_id)),
                "status": {
                    "$in": [
                        MembershipStatus.ACTIVE,
                        MembershipStatus.INVITED,
                        MembershipStatus.SUSPENDED,
                    ]
                },
            },
            limit=200,
        )

    async def get_for_user_business(
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
            },
            session=session,
        )

class RoleRepository(BaseRepository):
    collection_name = CollectionName.ROLES

class PermissionRepository(BaseRepository):
    collection_name = CollectionName.PERMISSIONS

    async def get_by_resource_action(self, resource: str, action: str) -> dict[str, Any] | None:
        return await self.find_one({"resource": resource, "action": action})

    async def codes_for_ids(self, permission_ids: list[ObjectId]) -> set[str]:
        if not permission_ids:
            return set()
        rows = await self.find_many(
            {"_id": {"$in": list(permission_ids)}},
            limit=max(len(permission_ids), 1),
        )
        return {f"{row['resource']}.{row['action']}" for row in rows}

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

    async def claim_attempt(
        self, token_id: ObjectId, *, max_attempts: int
    ) -> dict[str, Any] | None:
        from pymongo import ReturnDocument

        return await self.collection.find_one_and_update(
            {
                "_id": token_id,
                "used_at": None,
                "invalidated_at": None,
                "attempts": {"$lt": max_attempts},
            },
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )

    async def mark_used_if_open(
        self, token_id: ObjectId, at: Any, *, session: MongoSession = None
    ) -> bool:
        result = await self.collection.update_one(
            {"_id": token_id, "used_at": None, "invalidated_at": None},
            {"$set": {"used_at": at}},
            session=session,
        )
        return result.modified_count == 1

    async def get_latest_open(
        self, user_id: str | ObjectId, purpose: str
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "user_id": parse_object_id(str(user_id)),
                "purpose": purpose,
                "used_at": None,
                "invalidated_at": None,
            },
            sort=[("created_at", -1)],
        )

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

    async def revoke_if_active(
        self,
        session_id: str | ObjectId,
        revoked_at: Any,
        *,
        session: MongoSession = None,
    ) -> dict[str, Any] | None:
        oid = session_id if isinstance(session_id, ObjectId) else parse_object_id(str(session_id))
        from pymongo import ReturnDocument

        return await self.collection.find_one_and_update(
            {"_id": oid, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at}},
            return_document=ReturnDocument.AFTER,
            session=session,
        )

    async def revoke_all_for_user(
        self,
        user_id: str | ObjectId,
        revoked_at: Any,
        *,
        session: MongoSession = None,
        except_session_id: str | ObjectId | None = None,
    ) -> int:
        query: dict[str, Any] = {
            "user_id": parse_object_id(str(user_id)),
            "revoked_at": None,
        }
        if except_session_id is not None:
            query["_id"] = {"$ne": parse_object_id(str(except_session_id))}
        result = await self.collection.update_many(
            query,
            {"$set": {"revoked_at": revoked_at}},
            session=session,
        )
        return int(result.modified_count)

    async def revoke_family(self, family_id: ObjectId, revoked_at: Any) -> int:
        result = await self.collection.update_many(
            {"family_id": family_id, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at}},
        )
        return int(result.modified_count)

    async def list_active_for_user(
        self, user_id: str | ObjectId, *, now: Any
    ) -> list[dict[str, Any]]:
        return await self.find_many(
            {
                "user_id": parse_object_id(str(user_id)),
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            limit=100,
            sort=[("last_used_at", -1), ("created_at", -1)],
        )

    async def clear_active_business_for_user(
        self,
        user_id: str | ObjectId,
        business_account_id: str | ObjectId,
        *,
        session: MongoSession = None,
    ) -> int:
        result = await self.collection.update_many(
            {
                "user_id": parse_object_id(str(user_id)),
                "active_business_account_id": parse_object_id(str(business_account_id)),
                "revoked_at": None,
            },
            {"$set": {"active_business_account_id": None}},
            session=session,
        )
        return int(result.modified_count)

class SupplierProfileRepository(BaseRepository):
    collection_name = CollectionName.SUPPLIER_PROFILES

    async def get_by_business(self, business_account_id: str | ObjectId) -> dict[str, Any] | None:
        return await self.find_one({"business_account_id": parse_object_id(str(business_account_id))})
