
from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import generate_invitation_token, hash_token
from app.db.transactions import run_in_transaction
from app.modules.identity.auth_cache import invalidate_role_permissions, invalidate_session_auth
from app.modules.identity.constants import (
    INVITATION_TTL_DAYS,
    SYSTEM_ROLE_BUSINESS_ADMIN,
    InvitationStatus,
    MembershipStatus,
    UserStatus,
)
from app.modules.identity.email import get_email_sender
from app.modules.identity.exceptions import (
    AccountInactiveError,
    AlreadyBusinessMemberError,
    InvitationInvalidError,
    MemberOutranksActorError,
    PrivilegeEscalationError,
    SystemRoleProtectedError,
)
from app.modules.identity.guards import assert_not_last_admin
from app.modules.identity.permissions import permission_code
from app.modules.identity.repository import (
    BusinessRepository,
    InvitationRepository,
    MembershipRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.modules.identity.service import AuthService
from app.shared.repositories.base import MongoSession
from app.shared.services.audit import AuditService
from app.shared.utils.datetime import as_utc, utc_now
from app.shared.utils.objectid import parse_object_id


def _codes_from_permissions(rows: list[dict[str, Any]]) -> set[str]:
    return {permission_code(str(row["resource"]), str(row["action"])) for row in rows}

def _person_label(user: dict[str, Any] | None, *, fallback: str | None = None) -> str | None:
    if user:
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        if name:
            return name
        email = user.get("email")
        if isinstance(email, str) and email.strip():
            return email.strip()
    if fallback and fallback.strip():
        return fallback.strip()
    return None

def _company_member_avatar(user: dict[str, Any] | None, logo_url: str | None) -> str | None:
    if logo_url:
        return logo_url
    return user.get("avatar_url") if user else None

class DirectoryService:
    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        businesses: BusinessRepository | None = None,
        memberships: MembershipRepository | None = None,
        roles: RoleRepository | None = None,
        permissions: PermissionRepository | None = None,
        role_permissions: RolePermissionRepository | None = None,
        invitations: InvitationRepository | None = None,
        sessions: SessionRepository | None = None,
        auth: AuthService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.businesses = businesses or BusinessRepository()
        self.memberships = memberships or MembershipRepository()
        self.roles = roles or RoleRepository()
        self.permissions = permissions or PermissionRepository()
        self.role_permissions = role_permissions or RolePermissionRepository()
        self.invitations = invitations or InvitationRepository()
        self.sessions = sessions or SessionRepository()
        self.auth = auth or AuthService()
        self.audit = audit or AuditService()

                                                                            

    async def permission_codes_for_role(self, role_id: str | ObjectId) -> set[str]:
        ids = await self.role_permissions.list_permission_ids_for_role(role_id)
        return await self.permissions.codes_for_ids(ids)

    async def assert_subset(self, *, actor_permissions: set[str], requested: set[str]) -> None:
        if not requested <= actor_permissions:
            raise PrivilegeEscalationError()

    async def _assert_outranks_role(
        self, *, actor_permissions: set[str], role_id: str | ObjectId
    ) -> None:
        current = await self.permission_codes_for_role(role_id)
        if not current <= actor_permissions:
            raise MemberOutranksActorError()

    async def _membership_in_business(
        self, membership_id: str, business_id: str
    ) -> dict[str, Any]:
        membership = await self.memberships.get_by_id(membership_id)
        if membership is None or str(membership["business_account_id"]) != business_id:
            raise ForbiddenError("We couldn't find that team member in this company.")
        return membership

                                                                             

    async def list_members(
        self,
        *,
        business_id: str,
        status: str | None = None,
        query: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query: dict[str, Any] = {
            "business_account_id": parse_object_id(business_id),
        }
        if status:
            filter_query["status"] = status
        else:
            filter_query["status"] = {
                "$in": [
                    MembershipStatus.ACTIVE,
                    MembershipStatus.INVITED,
                    MembershipStatus.SUSPENDED,
                ]
            }

        needle = (query or "").strip()
        if needle:
            rx = {"$regex": re.escape(needle), "$options": "i"}
            matched_users = await self.users.find_many(
                {
                    "$or": [
                        {"email": rx},
                        {"first_name": rx},
                        {"last_name": rx},
                    ]
                },
                limit=10_000,
            )
            if not matched_users:
                return [], 0
            filter_query["user_id"] = {"$in": [user["_id"] for user in matched_users]}

        total = await self.memberships.count(filter_query)
        rows = await self.memberships.find_many(
            filter_query,
            skip=skip,
            limit=limit,
            sort=[("joined_at", -1), ("created_at", -1)],
        )
        if not rows:
            return [], total

        user_ids = list({row["user_id"] for row in rows})
        role_ids = list({row["role_id"] for row in rows})
        users, roles, business = await asyncio.gather(
            self.users.find_many({"_id": {"$in": user_ids}}, limit=max(len(user_ids), 1)),
            self.roles.find_many({"_id": {"$in": role_ids}}, limit=max(len(role_ids), 1)),
            self.businesses.get_by_id(business_id),
        )
        users_by_id = {row["_id"]: row for row in users}
        roles_by_id = {row["_id"]: row for row in roles}
        logo_url = business.get("logo_url") if business else None
        results: list[dict[str, Any]] = []
        for membership in rows:
            user = users_by_id.get(membership["user_id"])
            role = roles_by_id.get(membership["role_id"])
            results.append(
                {
                    "id": str(membership["_id"]),
                    "user_id": str(membership["user_id"]),
                    "email": user["email"] if user else None,
                    "first_name": user.get("first_name") if user else None,
                    "last_name": user.get("last_name") if user else None,
                    "avatar_url": _company_member_avatar(user, logo_url),
                    "role_id": str(membership["role_id"]),
                    "role_name": role["name"] if role else None,
                    "status": membership["status"],
                    "joined_at": membership.get("joined_at") or membership.get("created_at"),
                    "user_status": user.get("status") if user else None,
                }
            )
        return results, total

    async def list_all_users(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        email_verified: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query: dict[str, Any] = {}
        if status:
            filter_query["status"] = status
        if email_verified is True:
            filter_query["email_verified_at"] = {"$ne": None}
        elif email_verified is False:
            filter_query["email_verified_at"] = None
        needle = (query or "").strip()
        if needle:
            rx = {"$regex": re.escape(needle), "$options": "i"}
            filter_query["$or"] = [
                {"email": rx},
                {"first_name": rx},
                {"last_name": rx},
            ]

        total = await self.users.count(filter_query)
        users = await self.users.find_many(
            filter_query,
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
        )
        if not users:
            return [], total

        user_ids = [user["_id"] for user in users]
        memberships = await self.memberships.find_many(
            {"user_id": {"$in": user_ids}},
            limit=max(len(user_ids) * 5, 1),
            sort=[("joined_at", -1), ("created_at", -1)],
        )
        business_ids = list({row["business_account_id"] for row in memberships})
        role_ids = list({row["role_id"] for row in memberships})
        businesses: list[dict[str, Any]] = (
            await self.businesses.find_many(
                {"_id": {"$in": business_ids}},
                limit=max(len(business_ids), 1),
            )
            if business_ids
            else []
        )
        roles: list[dict[str, Any]] = (
            await self.roles.find_many(
                {"_id": {"$in": role_ids}},
                limit=max(len(role_ids), 1),
            )
            if role_ids
            else []
        )
        businesses_by_id = {row["_id"]: row for row in businesses}
        roles_by_id = {row["_id"]: row for row in roles}

        memberships_by_user: dict[Any, list[dict[str, Any]]] = {}
        for membership in memberships:
            memberships_by_user.setdefault(membership["user_id"], []).append(membership)

        results: list[dict[str, Any]] = []
        for user in users:
            user_memberships = memberships_by_user.get(user["_id"], [])
            logo_url = None
            businesses_payload: list[dict[str, Any]] = []
            for membership in user_memberships:
                business = businesses_by_id.get(membership["business_account_id"])
                role = roles_by_id.get(membership["role_id"])
                if logo_url is None and business and business.get("logo_url"):
                    logo_url = business.get("logo_url")
                businesses_payload.append(
                    {
                        "membership_id": str(membership["_id"]),
                        "business_id": str(membership["business_account_id"]),
                        "business_name": business.get("name") if business else None,
                        "business_type": business.get("type") if business else None,
                        "role_name": role.get("name") if role else None,
                        "membership_status": membership.get("status"),
                    }
                )
            results.append(
                {
                    "id": str(user["_id"]),
                    "email": user.get("email"),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "status": user.get("status"),
                    "avatar_url": _company_member_avatar(user, logo_url),
                    "email_verified_at": user.get("email_verified_at"),
                    "suspension_reason": user.get("suspension_reason"),
                    "created_at": user.get("created_at"),
                    "businesses": businesses_payload,
                }
            )
        return results, total

    async def get_member(self, *, business_id: str, membership_id: str) -> dict[str, Any]:
        membership = await self._membership_in_business(membership_id, business_id)
        user = await self.users.get_by_id(membership["user_id"])
        role = await self.roles.get_by_id(membership["role_id"])
        business = await self.businesses.get_by_id(business_id)
        logo_url = business.get("logo_url") if business else None
        return {
            "id": str(membership["_id"]),
            "user_id": str(membership["user_id"]),
            "email": user["email"] if user else None,
            "first_name": user.get("first_name") if user else None,
            "last_name": user.get("last_name") if user else None,
            "avatar_url": _company_member_avatar(user, logo_url),
            "role_id": str(membership["role_id"]),
            "role_name": role["name"] if role else None,
            "status": membership["status"],
            "joined_at": membership.get("joined_at") or membership.get("created_at"),
            "user_status": user.get("status") if user else None,
            "suspension_reason": user.get("suspension_reason") if user else None,
        }

    async def get_role(self, *, business_id: str, role_id: str) -> dict[str, Any]:
        role = await self._role_in_business(role_id, business_id)
        codes = sorted(await self.permission_codes_for_role(role["_id"]))
        return {
            "id": str(role["_id"]),
            "name": role["name"],
            "description": role.get("description"),
            "is_system_role": bool(role.get("is_system_role")),
            "permissions": codes,
        }

    async def list_roles(
        self,
        *,
        business_id: str,
        query: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query: dict[str, Any] = {
            "business_account_id": parse_object_id(business_id),
            "is_active": {"$ne": False},
            "deleted_at": None,
        }
        needle = (query or "").strip()
        if needle:
            filter_query["name"] = {"$regex": re.escape(needle), "$options": "i"}

        total = await self.roles.count(filter_query)
        rows = await self.roles.find_many(
            filter_query,
            skip=skip,
            limit=limit,
            sort=[("name", 1)],
        )
        if not rows:
            return [], total

        role_ids = [row["_id"] for row in rows]
        grant_rows = await self.role_permissions.find_many(
            {"role_id": {"$in": role_ids}},
            limit=5000,
        )
        permission_ids = list({row["permission_id"] for row in grant_rows})
        permission_docs = (
            await self.permissions.find_many(
                {"_id": {"$in": permission_ids}},
                limit=max(len(permission_ids), 1),
            )
            if permission_ids
            else []
        )
        code_by_id = {
            doc["_id"]: permission_code(str(doc["resource"]), str(doc["action"]))
            for doc in permission_docs
        }
        codes_by_role: dict[ObjectId, list[str]] = {rid: [] for rid in role_ids}
        for grant in grant_rows:
            code = code_by_id.get(grant["permission_id"])
            if code:
                codes_by_role.setdefault(grant["role_id"], []).append(code)

        items = [
            {
                "id": str(role["_id"]),
                "name": role["name"],
                "description": role.get("description"),
                "is_system_role": bool(role.get("is_system_role")),
                "permissions": sorted(set(codes_by_role.get(role["_id"], []))),
            }
            for role in rows
        ]
        return items, total

    async def get_invitation(
        self,
        *,
        invitation_id: str,
        requester_email: str,
        requester_user_id: str,
        actor_permissions_by_business: dict[str, set[str]] | None = None,
    ) -> dict[str, Any]:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationInvalidError()
        business_id = str(invitation["business_account_id"])
        is_recipient = invitation["invited_email"].lower() == requester_email.lower().strip()
        can_manage = False
        if actor_permissions_by_business and business_id in actor_permissions_by_business:
            perms = actor_permissions_by_business[business_id]
            can_manage = "users.read" in perms or "users.invite" in perms
        if not is_recipient and not can_manage:
                                                                           
            membership = await self.memberships.get_active_membership(requester_user_id, business_id)
            if membership is None:
                raise InvitationInvalidError()
            role_perms = await self.permission_codes_for_role(membership["role_id"])
            if "users.read" not in role_perms and "users.invite" not in role_perms:
                raise InvitationInvalidError()
        business = await self.businesses.get_by_id(business_id)
        role = await self.roles.get_by_id(invitation["role_id"])
        inviter = await self.users.get_by_id(invitation.get("invited_by_user_id"))
        return {
            "id": str(invitation["_id"]),
            "business_account_id": business_id,
            "business_name": business.get("name") if business else None,
            "invited_email": invitation["invited_email"],
            "delivery_email": invitation.get("delivery_email") or invitation["invited_email"],
            "role_id": str(invitation["role_id"]),
            "role_name": role.get("name") if role else None,
            "status": invitation["status"],
            "expires_at": invitation["expires_at"],
            "created_at": invitation.get("created_at"),
            "inviter_name": (
                f"{inviter.get('first_name', '')} {inviter.get('last_name', '')}".strip()
                if inviter
                else None
            ),
        }

    async def decline_invitation(
        self, *, invitation_id: str, user_email: str, user_id: str, ip_address: str | None = None
    ) -> None:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationInvalidError("Invitation link is invalid")
        await self._assert_invitation_recipient(invitation, user_email=user_email, user_id=user_id)
        invitation = await self._ensure_invitation_not_expired(invitation)
        if invitation.get("status") != InvitationStatus.PENDING:
            raise InvitationInvalidError(self._invitation_status_message(invitation.get("status")))
        await self.invitations.update(invitation_id, {"status": InvitationStatus.DECLINED})
        await self.audit.log(
            action="INVITATION_DECLINED",
            resource_type="invitation",
            resource_id=invitation_id,
            business_account_id=invitation["business_account_id"],
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "member_name": _person_label(await self.users.get_by_id(user_id), fallback=user_email),
                "invited_email": invitation.get("invited_email"),
                "email": user_email,
            },
        )

    async def accept_invitation_by_id(
        self, *, invitation_id: str, user_id: str, user_email: str, session_id: str | None = None, ip_address: str | None = None
    ) -> dict[str, Any]:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationInvalidError("Invitation link is invalid")
        return await self._accept_invitation_for_user(
            invitation=invitation,
            user_id=user_id,
            user_email=user_email,
            session_id=session_id,
            ip_address=ip_address,
        )

    async def update_member_role(
        self,
        *,
        business_id: str,
        membership_id: str,
        role_id: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> dict[str, Any]:
        membership = await self._membership_in_business(membership_id, business_id)
        role = await self._role_in_business(role_id, business_id)
        await self._assert_outranks_role(
            actor_permissions=actor_permissions, role_id=membership["role_id"]
        )
        await self.assert_subset(
            actor_permissions=actor_permissions,
            requested=await self.permission_codes_for_role(role["_id"]),
        )
        if str(membership["role_id"]) != str(role["_id"]):
            await assert_not_last_admin(business_account_id=business_id, membership=membership)
        previous_role = await self.roles.get_by_id(membership["role_id"])
        target = await self.users.get_by_id(membership["user_id"])
        actor = await self.users.get_by_id(actor_user_id)
        updated = await self.memberships.update(
            membership_id,
            {"role_id": role["_id"], "updated_at": utc_now()},
        )
        invalidate_session_auth()
        await self.audit.log(
            action="MEMBER_ROLE_CHANGED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "member_name": _person_label(target),
                "target_user_id": str(membership["user_id"]),
                "role_id": str(role["_id"]),
                "role_name": role.get("name"),
                "new_role_name": role.get("name"),
                "previous_role_name": previous_role.get("name") if previous_role else None,
            },
        )
        return {"id": str(updated["_id"]) if updated else membership_id, "role_id": str(role["_id"])}

    async def remove_member(
        self,
        *,
        business_id: str,
        membership_id: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> None:
        membership = await self._membership_in_business(membership_id, business_id)
        await self._assert_outranks_role(
            actor_permissions=actor_permissions, role_id=membership["role_id"]
        )
        await assert_not_last_admin(business_account_id=business_id, membership=membership)
        await self.memberships.update(
            membership_id,
            {"status": MembershipStatus.REMOVED, "updated_at": utc_now()},
        )
        await self.sessions.clear_active_business_for_user(
            membership["user_id"],
            business_id,
        )
        invalidate_session_auth()
        target = await self.users.get_by_id(membership["user_id"])
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="MEMBER_REMOVED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "member_name": _person_label(target),
                "target_user_id": str(membership["user_id"]),
                "email": target.get("email") if target else None,
            },
        )

                                                                            

    async def create_role(
        self,
        *,
        business_id: str,
        name: str,
        permission_codes: list[str],
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> dict[str, Any]:
        requested = set(permission_codes)
        await self.assert_subset(actor_permissions=actor_permissions, requested=requested)
        now = utc_now()
        role = await self.roles.create(
            {
                "business_account_id": parse_object_id(business_id),
                "name": name.strip(),
                "description": None,
                "is_system_role": False,
                "is_active": True,
                "deleted_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await self.role_permissions.replace_for_role(
            role["_id"],
            await self._permission_ids(requested),
            created_at=now,
        )
        invalidate_role_permissions(str(role["_id"]))
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="ROLE_CREATED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "name": name,
                "role_name": name,
                "permissions": sorted(requested),
            },
        )
        return {
            "id": str(role["_id"]),
            "name": role["name"],
            "description": role.get("description"),
            "is_system_role": False,
            "permissions": sorted(requested),
        }

    async def update_role(
        self,
        *,
        business_id: str,
        role_id: str,
        permission_codes: list[str],
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
        protect_owner_role: bool = True,
    ) -> dict[str, Any]:
        role = await self._role_in_business(role_id, business_id)
                                                                                
                                                                   
        if (
            protect_owner_role
            and role.get("is_system_role")
            and role.get("name") == SYSTEM_ROLE_BUSINESS_ADMIN
        ):
            raise SystemRoleProtectedError(
                "Business Admin permissions cannot be changed"
            )
        if protect_owner_role:
            await self._assert_outranks_role(
                actor_permissions=actor_permissions, role_id=role["_id"]
            )
        requested = set(permission_codes)
        await self.assert_subset(actor_permissions=actor_permissions, requested=requested)
        now = utc_now()
        await self.role_permissions.replace_for_role(
            role["_id"],
            await self._permission_ids(requested),
            created_at=now,
        )
        await self.roles.update(role["_id"], {"updated_at": now})
        invalidate_role_permissions(str(role["_id"]))
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="ROLE_UPDATED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "role_name": role.get("name"),
                "name": role.get("name"),
                "permissions": sorted(requested),
                "system_role": bool(role.get("is_system_role")),
            },
        )
        return {
            "id": str(role["_id"]),
            "name": role["name"],
            "description": role.get("description"),
            "is_system_role": bool(role.get("is_system_role")),
            "permissions": sorted(requested),
        }

    async def delete_role(self, *, business_id: str, role_id: str, actor_user_id: str, ip_address: str | None) -> None:
        role = await self._role_in_business(role_id, business_id, allow_inactive=True)
        if role.get("is_system_role"):
            raise SystemRoleProtectedError("System roles cannot be deleted")
        if role.get("is_active") is False or role.get("deleted_at") is not None:
            return
        in_use = await self.memberships.count(
            {
                "business_account_id": parse_object_id(business_id),
                "role_id": role["_id"],
                "status": {
                    "$in": [
                        MembershipStatus.ACTIVE,
                        MembershipStatus.INVITED,
                        MembershipStatus.SUSPENDED,
                    ]
                },
            }
        )
        if in_use:
            raise SystemRoleProtectedError(
                "This role is still assigned to team members. Move them to another role first."
            )
        pending_invites = await self.invitations.count(
            {
                "business_account_id": parse_object_id(business_id),
                "role_id": role["_id"],
                "status": InvitationStatus.PENDING,
                "expires_at": {"$gt": utc_now()},
            }
        )
        if pending_invites:
            raise SystemRoleProtectedError(
                "Open invitations still use this role. Revoke them or wait for them to expire first."
            )
        now = utc_now()
        original_name = str(role.get("name") or "role")
        await self.role_permissions.replace_for_role(role["_id"], [], created_at=now)
        await self.roles.update(
            role["_id"],
            {
                "is_active": False,
                "deleted_at": now,
                "updated_at": now,
                                                                                  
                "name": f"{original_name}·deleted·{str(role['_id'])[-6:]}",
            },
        )
        invalidate_role_permissions(str(role["_id"]))
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="ROLE_DELETED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "role_name": original_name,
                "name": original_name,
                "soft_deleted": True,
            },
        )

                                                                            

    async def create_invitation(
        self,
        *,
        business_id: str,
        email: str,
        role_id: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
        permissions: list[str] | None = None,
        company_email: str | None = None,
    ) -> dict[str, Any]:
        from app.modules.identity.company_domain import (
            email_matches_company_domain,
            generate_company_login_email,
        )
        from app.modules.identity.exceptions import (
            CompanyDomainMismatchError,
            CompanyDomainRequiredError,
        )

        delivery_email = email.lower().strip()
        business = await self.businesses.get_by_id(business_id)
        if business is None:
            raise InvitationInvalidError("Company not found for this invitation")
        company_domain = business.get("email_domain")
        company_name = business.get("name") or "your company"
        if not company_domain:
            raise InvitationInvalidError(
                "This company has no email domain configured. "
                "Set the company domain on Company Profile before inviting teammates."
            )

        try:
            login_email = generate_company_login_email(
                personal_email=delivery_email,
                company_domain=str(company_domain),
                company_email=company_email,
            )
        except ValueError as exc:
            message = str(exc)
            if "company domain" in message.lower():
                raise CompanyDomainMismatchError(
                    company_name=company_name,
                    company_domain=str(company_domain),
                ) from exc
            raise CompanyDomainRequiredError(message) from exc

        if not email_matches_company_domain(login_email, company_domain):
            raise CompanyDomainMismatchError(
                company_name=company_name,
                company_domain=str(company_domain),
            )

        role = await self._role_in_business(role_id, business_id)
        role_codes = await self.permission_codes_for_role(role["_id"])

        requested = set(permissions) if permissions is not None else set(role_codes)
        if not requested:
            raise InvitationInvalidError("Select at least one permission for this invitation")
        if not requested <= role_codes:
            raise PrivilegeEscalationError()
        await self.assert_subset(
            actor_permissions=actor_permissions,
            requested=requested,
        )

                                                          
        existing_user = await self.users.get_by_email(login_email)
        if existing_user is not None:
            membership = await self.memberships.get_for_user_business(
                existing_user["_id"], business_id
            )
            if membership is not None and membership.get("status") in {
                MembershipStatus.ACTIVE,
                MembershipStatus.INVITED,
                MembershipStatus.SUSPENDED,
            }:
                raise AlreadyBusinessMemberError(
                    "This person is already on your team. Open Members to manage their access."
                )

        pending = await self.invitations.find_one(
            {
                "business_account_id": parse_object_id(business_id),
                "invited_email": login_email,
                "status": InvitationStatus.PENDING,
            }
        )
        if pending is not None:
            pending_role = await self.roles.get_by_id(str(pending["role_id"]))
            return {
                "id": str(pending["_id"]),
                "invited_email": pending["invited_email"],
                "delivery_email": pending.get("delivery_email") or pending["invited_email"],
                "role_id": str(pending["role_id"]),
                "role_name": pending_role.get("name") if pending_role else None,
                "status": pending["status"],
                "expires_at": pending.get("expires_at"),
                "created_at": pending.get("created_at"),
                "permissions": sorted(requested),
                "already_pending": True,
                "message": (
                    "This company login email already has a pending invitation. "
                    "Open Invitations to resend it."
                ),
            }

        invite_role = role
        if requested != set(role_codes):
                                                                                 
                                                                     
            base_name = f"{role['name']} · invite"
            candidates = await self.roles.find_many(
                {
                    "business_account_id": parse_object_id(business_id),
                    "name": {"$regex": f"^{re.escape(base_name)}"},
                    "is_system_role": False,
                    "is_active": {"$ne": False},
                },
                limit=100,
            )
            existing_custom = None
            for candidate in candidates:
                if await self.permission_codes_for_role(candidate["_id"]) == requested:
                    existing_custom = candidate
                    break
            if existing_custom is not None:
                invite_role = existing_custom
            else:
                taken = {str(candidate.get("name")) for candidate in candidates}
                custom_name = base_name
                suffix = 2
                while custom_name in taken:
                    custom_name = f"{base_name} {suffix}"
                    suffix += 1
                now_role = utc_now()
                invite_role = await self.roles.create(
                    {
                        "business_account_id": parse_object_id(business_id),
                        "name": custom_name,
                        "description": f"Custom permission set based on {role['name']}",
                        "is_system_role": False,
                        "is_active": True,
                        "deleted_at": None,
                        "created_at": now_role,
                        "updated_at": now_role,
                    }
                )
                await self.role_permissions.replace_for_role(
                    invite_role["_id"],
                    await self._permission_ids(requested),
                    created_at=now_role,
                )
                invalidate_role_permissions(str(invite_role["_id"]))

        raw = generate_invitation_token()
        now = utc_now()
        invitation = await self.invitations.create(
            {
                "business_account_id": parse_object_id(business_id),
                "invited_email": login_email,
                "delivery_email": delivery_email,
                "role_id": invite_role["_id"],
                "invited_by_user_id": parse_object_id(actor_user_id),
                "token_hash": hash_token(raw),
                "status": InvitationStatus.PENDING,
                "expires_at": now + timedelta(days=INVITATION_TTL_DAYS),
                "accepted_at": None,
                "created_at": now,
            }
        )
        inviter = await self.users.get_by_id(actor_user_id)
        inviter_name = (
            f"{inviter.get('first_name', '')} {inviter.get('last_name', '')}".strip()
            if inviter
            else None
        )
        await get_email_sender().send(
            to=delivery_email,
            template="invitation",
            context={
                "business_id": business_id,
                "business_name": business.get("name"),
                "role_id": str(invite_role["_id"]),
                "role_name": invite_role.get("name"),
                "inviter_name": inviter_name,
                "company_email": login_email,
                "delivery_email": delivery_email,
                "token": raw,
            },
        )
        await self.audit.log(
            action="USER_INVITED",
            resource_type="invitation",
            resource_id=invitation["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(inviter),
                "invited_email": login_email,
                "delivery_email": delivery_email,
                "role_id": str(invite_role["_id"]),
                "role_name": invite_role.get("name"),
                "permissions": sorted(requested),
            },
        )
        try:
            from app.modules.trust.notify import notify

            existing_recipient = existing_user or await self.users.find_one(
                {
                    "$or": [
                        {"email": delivery_email},
                        {"personal_email": delivery_email},
                    ]
                }
            )
            if existing_recipient is not None:
                await notify(
                    recipient_user_id=existing_recipient["_id"],
                    recipient_business_id=business_id,
                    fanout_business=False,
                    email=False,
                    type="TEAM_INVITATION",
                    title=f"You're invited to join {business.get('name')}",
                    message=(
                        f"{inviter_name or 'A teammate'} invited you as "
                        f"{invite_role.get('name')}. Check your email to accept."
                    ),
                    reference_type="invitation",
                    reference_id=invitation["_id"],
                    cta_path="/accept-invitation",
                )
        except Exception:
            pass
        return {
            "id": str(invitation["_id"]),
            "invited_email": invitation["invited_email"],
            "delivery_email": delivery_email,
            "role_id": str(invite_role["_id"]),
            "role_name": invite_role.get("name"),
            "status": invitation["status"],
            "expires_at": invitation["expires_at"],
            "created_at": invitation.get("created_at"),
            "permissions": sorted(requested),
            "already_pending": False,
        }

    async def list_invitations(
        self,
        *,
        business_id: str,
        status: str | None = None,
        query: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_query: dict[str, Any] = {
            "business_account_id": parse_object_id(business_id),
        }
        now = utc_now()
        if status == InvitationStatus.EXPIRED:
            filter_query["status"] = InvitationStatus.PENDING
            filter_query["expires_at"] = {"$lt": now}
        elif status == InvitationStatus.PENDING:
            filter_query["status"] = InvitationStatus.PENDING
            filter_query["expires_at"] = {"$gte": now}
        elif status:
            filter_query["status"] = status

        needle = (query or "").strip()
        if needle:
            filter_query["invited_email"] = {
                "$regex": re.escape(needle),
                "$options": "i",
            }

        total = await self.invitations.count(filter_query)
        rows = await self.invitations.find_many(
            filter_query,
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
        )
        if not rows:
            return [], total

        role_ids = list({row["role_id"] for row in rows})
        roles = await self.roles.find_many(
            {"_id": {"$in": role_ids}},
            limit=max(len(role_ids), 1),
        )
        roles_by_id = {row["_id"]: row for row in roles}
        results: list[dict[str, Any]] = []
        for row in rows:
            role = roles_by_id.get(row["role_id"])
            row_status = row["status"]
            if row_status == InvitationStatus.PENDING and as_utc(row["expires_at"]) < now:
                row_status = InvitationStatus.EXPIRED
            results.append(
                {
                    "id": str(row["_id"]),
                    "invited_email": row["invited_email"],
                    "delivery_email": row.get("delivery_email") or row["invited_email"],
                    "role_id": str(row["role_id"]),
                    "role_name": role.get("name") if role else None,
                    "status": row_status,
                    "expires_at": row["expires_at"],
                    "created_at": row.get("created_at"),
                }
            )
        return results, total

    async def preview_invitation_by_token(self, *, raw_token: str) -> dict[str, Any]:
        invitation = await self.invitations.get_by_token_hash(hash_token(raw_token))
        if invitation is None:
            raise InvitationInvalidError("Invitation link is invalid")
        invitation = await self._ensure_invitation_not_expired(invitation, persist=True)
        status = invitation["status"]
        if status == InvitationStatus.PENDING and as_utc(invitation["expires_at"]) < utc_now():
            status = InvitationStatus.EXPIRED
        business = await self.businesses.get_by_id(invitation["business_account_id"])
        role = await self.roles.get_by_id(invitation["role_id"])
        inviter = await self.users.get_by_id(invitation.get("invited_by_user_id"))
        return {
            "id": str(invitation["_id"]),
            "invited_email": invitation["invited_email"],
            "delivery_email": invitation.get("delivery_email") or invitation["invited_email"],
            "business_name": business.get("name") if business else None,
            "role_id": str(invitation["role_id"]),
            "role_name": role.get("name") if role else None,
            "status": status,
            "expires_at": invitation["expires_at"],
            "inviter_name": (
                f"{inviter.get('first_name', '')} {inviter.get('last_name', '')}".strip()
                if inviter
                else None
            ),
        }

    @staticmethod
    def _invitation_status_message(status: str | None) -> str:
        if status == InvitationStatus.REVOKED:
            return "This invitation was revoked. Ask an admin for a new invite."
        if status == InvitationStatus.DECLINED:
            return "This invitation was declined."
        if status == InvitationStatus.EXPIRED:
            return "This invitation has expired. Ask an admin to resend it."
        if status == InvitationStatus.ACCEPTED:
            return "This invitation was already accepted."
        return "Invitation is not valid"

    async def _ensure_invitation_not_expired(
        self,
        invitation: dict[str, Any],
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        if invitation.get("status") != InvitationStatus.PENDING:
            return invitation
        if as_utc(invitation["expires_at"]) >= utc_now():
            return invitation
        if persist:
            updated = await self.invitations.update(
                invitation["_id"],
                {"status": InvitationStatus.EXPIRED, "updated_at": utc_now()},
            )
            if updated is not None:
                return updated
        invitation = dict(invitation)
        invitation["status"] = InvitationStatus.EXPIRED
        return invitation

    async def _assert_invitation_recipient(
        self,
        invitation: dict[str, Any],
        *,
        user_email: str,
        user_id: str,
    ) -> dict[str, Any]:
        if invitation["invited_email"].lower().strip() != user_email.lower().strip():
            raise InvitationInvalidError(
                "Sign in with the company login email on this invitation"
            )
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvitationInvalidError()
        if user.get("status") == UserStatus.SUSPENDED:
            raise AccountInactiveError()
        if user.get("status") not in {UserStatus.ACTIVE, UserStatus.PENDING}:
            raise AccountInactiveError()
        return user

    async def _invitation_membership_result(
        self,
        *,
        invitation: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any] | None:
        business_id = invitation["business_account_id"]
        membership = await self.memberships.get_active_membership(user_id, business_id)
        if membership is None:
            return None
        role = await self.roles.get_by_id(invitation["role_id"])
        return {
            "business_id": str(business_id),
            "role_id": str(invitation["role_id"]),
            "role_name": role.get("name") if role else None,
            "membership_id": str(membership["_id"]),
            "already_accepted": True,
        }

    async def _accept_invitation_for_user(
        self,
        *,
        invitation: dict[str, Any],
        user_id: str,
        user_email: str,
        session_id: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        await self._assert_invitation_recipient(
            invitation, user_email=user_email, user_id=user_id
        )
        invitation = await self._ensure_invitation_not_expired(invitation)

        status = invitation.get("status")
        if status == InvitationStatus.ACCEPTED:
            existing = await self._invitation_membership_result(
                invitation=invitation, user_id=user_id
            )
            if existing is not None:
                return existing
            raise InvitationInvalidError(self._invitation_status_message(status))

        if status != InvitationStatus.PENDING:
            raise InvitationInvalidError(self._invitation_status_message(status))

        business = await self.businesses.get_by_id(invitation["business_account_id"])
        if business is None:
            raise InvitationInvalidError("This company is no longer available")
        company_domain = business.get("email_domain")
        if company_domain:
            from app.modules.identity.company_domain import email_matches_company_domain
            from app.modules.identity.exceptions import CompanyDomainMismatchError

            if not email_matches_company_domain(user_email, company_domain):
                raise CompanyDomainMismatchError(
                    company_name=business.get("name") or "your company",
                    company_domain=str(company_domain),
                )

        return await self._accept_invitation_document(
            invitation=invitation,
            user_id=user_id,
            user_email=user_email,
            session_id=session_id,
            ip_address=ip_address,
        )

    async def resend_invitation(
        self,
        *,
        business_id: str,
        invitation_id: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> dict[str, Any]:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None or str(invitation["business_account_id"]) != business_id:
            raise InvitationInvalidError("Invitation not found")
        invitation = await self._ensure_invitation_not_expired(invitation)
        if invitation["status"] not in {
            InvitationStatus.PENDING,
            InvitationStatus.EXPIRED,
        }:
            raise InvitationInvalidError("Only pending or expired invitations can be resent")
        role = await self._role_in_business(str(invitation["role_id"]), business_id)
        await self.assert_subset(
            actor_permissions=actor_permissions,
            requested=await self.permission_codes_for_role(role["_id"]),
        )
        raw = generate_invitation_token()
        now = utc_now()
        await self.invitations.update(
            invitation_id,
            {
                "token_hash": hash_token(raw),
                "status": InvitationStatus.PENDING,
                "expires_at": now + timedelta(days=INVITATION_TTL_DAYS),
                "updated_at": now,
            },
        )
        business = await self.businesses.get_by_id(business_id)
        inviter = await self.users.get_by_id(actor_user_id)
        inviter_name = (
            f"{inviter.get('first_name', '')} {inviter.get('last_name', '')}".strip()
            if inviter
            else None
        )
        await get_email_sender().send(
            to=invitation.get("delivery_email") or invitation["invited_email"],
            template="invitation",
            context={
                "business_id": business_id,
                "business_name": business.get("name") if business else None,
                "role_id": str(role["_id"]),
                "role_name": role.get("name"),
                "inviter_name": inviter_name,
                "company_email": invitation["invited_email"],
                "delivery_email": invitation.get("delivery_email") or invitation["invited_email"],
                "token": raw,
            },
        )
        await self.audit.log(
            action="INVITATION_RESENT",
            resource_type="invitation",
            resource_id=invitation_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": inviter_name,
                "invited_email": invitation["invited_email"],
                "delivery_email": invitation.get("delivery_email") or invitation["invited_email"],
                "role_id": str(role["_id"]),
                "role_name": role.get("name"),
            },
        )
        return {
            "id": invitation_id,
            "invited_email": invitation["invited_email"],
            "role_id": str(role["_id"]),
            "role_name": role.get("name"),
            "status": InvitationStatus.PENDING,
            "expires_at": now + timedelta(days=INVITATION_TTL_DAYS),
        }

    async def decline_invitation_by_token(
        self, *, raw_token: str, user_email: str, user_id: str, ip_address: str | None = None
    ) -> None:
        invitation = await self.invitations.get_by_token_hash(hash_token(raw_token))
        if invitation is None:
            raise InvitationInvalidError()
        await self.decline_invitation(
            invitation_id=str(invitation["_id"]),
            user_email=user_email,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def revoke_invitation(
        self, *, business_id: str, invitation_id: str, actor_user_id: str, ip_address: str | None
    ) -> None:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None or str(invitation["business_account_id"]) != business_id:
            raise InvitationInvalidError()
        if invitation["status"] != InvitationStatus.PENDING:
            raise InvitationInvalidError("Invitation cannot be revoked")
        await self.invitations.update(invitation_id, {"status": InvitationStatus.REVOKED})
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="INVITATION_REVOKED",
            resource_type="invitation",
            resource_id=invitation_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "invited_email": invitation.get("invited_email"),
                "role_id": str(invitation.get("role_id")) if invitation.get("role_id") else None,
            },
        )

    async def accept_invitation(
        self, *, raw_token: str, user_id: str, user_email: str, session_id: str | None = None, ip_address: str | None = None
    ) -> dict[str, Any]:
        invitation = await self.invitations.get_by_token_hash(hash_token(raw_token))
        if invitation is None:
            raise InvitationInvalidError("Invitation link is invalid")
        return await self._accept_invitation_for_user(
            invitation=invitation,
            user_id=user_id,
            user_email=user_email,
            session_id=session_id,
            ip_address=ip_address,
        )

    async def _accept_invitation_document(
        self,
        *,
        invitation: dict[str, Any],
        user_id: str,
        user_email: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        business_id = invitation["business_account_id"]
        invited_role_id = invitation["role_id"]

                                                                              
        existing_outside = await self.memberships.get_for_user_business(user_id, business_id)
        if existing_outside is not None and str(existing_outside.get("role_id")) != str(
            invited_role_id
        ):
            if existing_outside.get("status") == MembershipStatus.ACTIVE:
                await assert_not_last_admin(
                    business_account_id=business_id,
                    membership=existing_outside,
                    memberships=self.memberships,
                    roles=self.roles,
                )

        async def work(session: MongoSession) -> dict[str, Any]:
            existing = await self.memberships.get_for_user_business(
                user_id, business_id, session=session
            )
            if existing is None:
                membership = await self.memberships.create(
                    {
                        "user_id": parse_object_id(user_id),
                        "business_account_id": business_id,
                        "role_id": invited_role_id,
                        "status": MembershipStatus.ACTIVE,
                        "joined_at": now,
                        "created_at": now,
                        "updated_at": now,
                    },
                    session=session,
                )
            else:
                if (
                    existing.get("status") == MembershipStatus.ACTIVE
                    and str(existing.get("role_id")) != str(invited_role_id)
                ):
                    await assert_not_last_admin(
                        business_account_id=business_id,
                        membership=existing,
                        memberships=self.memberships,
                        roles=self.roles,
                    )
                                                                                  
                membership = await self.memberships.update(
                    existing["_id"],
                    {
                        "role_id": invited_role_id,
                        "status": MembershipStatus.ACTIVE,
                        "joined_at": existing.get("joined_at") or now,
                        "updated_at": now,
                    },
                    session=session,
                ) or existing

            await self.invitations.update(
                invitation["_id"],
                {"status": InvitationStatus.ACCEPTED, "accepted_at": now},
                session=session,
            )
            return membership

        membership = await run_in_transaction(work)

                                                                                         
                                                                                        
        verified_via_invite = False
        user = await self.users.get_by_id(user_id)
        now_updates: dict[str, Any] = {}
        delivery = str(invitation.get("delivery_email") or "").strip().lower()
        if user is not None and delivery and not user.get("personal_email"):
            now_updates["personal_email"] = delivery
        if user is not None and not user.get("email_verified_at"):
            if user.get("status") in {UserStatus.PENDING, UserStatus.ACTIVE}:
                now_updates["email_verified_at"] = now
                now_updates["status"] = UserStatus.ACTIVE
                verified_via_invite = True
        if user is not None and now_updates:
            now_updates["updated_at"] = now
            await self.users.update(user_id, now_updates)

                                                             
        if user is not None:
            business = await self.businesses.get_by_id(business_id)
            logo_url = business.get("logo_url") if business else None
            if logo_url:
                await self.users.update(
                    user_id,
                    {"avatar_url": logo_url, "updated_at": now},
                )

        if session_id:
            await self.sessions.update(
                session_id,
                {
                    "active_business_account_id": parse_object_id(str(business_id)),
                    "last_used_at": now,
                },
            )
            invalidate_session_auth(session_id)
        else:
            invalidate_session_auth()

        role = await self.roles.get_by_id(invited_role_id)
        member_label = _person_label(user, fallback=user_email or invitation.get("invited_email"))
        await self.audit.log(
            action="INVITATION_ACCEPTED",
            resource_type="invitation",
            resource_id=invitation["_id"],
            business_account_id=business_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": member_label,
                "member_name": member_label,
                "invited_email": invitation.get("invited_email"),
                "email": user_email or invitation.get("invited_email"),
                "role_id": str(invited_role_id),
                "role_name": role.get("name") if role else None,
                "membership_id": str(membership["_id"]) if membership else None,
                "email_verified_via": "invitation" if verified_via_invite else None,
            },
        )
        try:
            from app.modules.trust.notify import notify_business_admins

            company = await self.businesses.get_by_id(business_id)
            company_name = (company or {}).get("name") or "your company"
            role_name = (role or {}).get("name") or "a teammate"
            await notify_business_admins(
                business_id=business_id,
                exclude_user_id=user_id,
                extra_user_ids=[invitation.get("invited_by_user_id")],
                type="TEAM_MEMBER_JOINED",
                title=f"{member_label} joined {company_name}",
                message=(
                    f"{member_label} accepted the invitation and joined as {role_name}."
                ),
                reference_type="membership",
                reference_id=membership["_id"] if membership else invitation["_id"],
                cta_path="/members",
            )
        except Exception:
            pass
        return {
            "business_id": str(business_id),
            "role_id": str(invited_role_id),
            "role_name": role.get("name") if role else None,
            "membership_id": str(membership["_id"]) if membership else None,
            "already_accepted": False,
        }

                                                                             

    async def suspend_membership(
        self,
        *,
        business_id: str,
        membership_id: str,
        reason: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> None:
        cleaned = reason.strip()
        if not cleaned:
            raise BadRequestError("Add a short reason for the suspension.")
        membership = await self._membership_in_business(membership_id, business_id)
        if membership["status"] not in {MembershipStatus.ACTIVE, MembershipStatus.INVITED}:
            raise ConflictError("This team member is already suspended or no longer active.")
        await self._assert_outranks_role(
            actor_permissions=actor_permissions, role_id=membership["role_id"]
        )
        await assert_not_last_admin(business_account_id=business_id, membership=membership)
        await self.memberships.update(
            membership_id,
            {"status": MembershipStatus.SUSPENDED, "updated_at": utc_now()},
        )
        invalidate_session_auth()
        target = await self.users.get_by_id(membership["user_id"])
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="MEMBERSHIP_SUSPENDED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "reason": cleaned,
                "actor_name": _person_label(actor),
                "member_name": _person_label(target),
                "target_user_id": str(membership["user_id"]),
                "email": target.get("email") if target else None,
            },
        )

    async def reactivate_membership(
        self,
        *,
        business_id: str,
        membership_id: str,
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> None:
        membership = await self._membership_in_business(membership_id, business_id)
        if membership["status"] != MembershipStatus.SUSPENDED:
            raise ConflictError("This team member isn't suspended.")
        await self._assert_outranks_role(
            actor_permissions=actor_permissions, role_id=membership["role_id"]
        )
        await self.memberships.update(
            membership_id,
            {"status": MembershipStatus.ACTIVE, "updated_at": utc_now()},
        )
        invalidate_session_auth()
        target = await self.users.get_by_id(membership["user_id"])
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="MEMBERSHIP_REACTIVATED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "member_name": _person_label(target),
                "target_user_id": str(membership["user_id"]),
                "email": target.get("email") if target else None,
            },
        )

    async def suspend_user(
        self,
        *,
        target_user_id: str,
        reason: str,
        actor_user_id: str,
        business_id: str | None,
        ip_address: str | None,
    ) -> None:
        cleaned = reason.strip()
        if not cleaned:
            raise BadRequestError("Add a short reason for the suspension.")
        if await self.users.get_by_id(target_user_id) is None:
            raise NotFoundError("We couldn't find that account.")
        if target_user_id == actor_user_id:
            raise ForbiddenError("You can't suspend your own account.")
        now = utc_now()

        async def work(session: MongoSession) -> None:
            await self.users.update(
                target_user_id,
                {
                    "status": UserStatus.SUSPENDED,
                    "suspension_reason": cleaned,
                    "suspended_at": now,
                    "updated_at": now,
                },
                session=session,
            )
            await self.sessions.revoke_all_for_user(target_user_id, now, session=session)

        await run_in_transaction(work)
        invalidate_session_auth()
        target = await self.users.get_by_id(target_user_id)
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="USER_SUSPENDED",
            resource_type="user",
            resource_id=target_user_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "reason": cleaned,
                "actor_name": _person_label(actor),
                "member_name": _person_label(target),
                "target_user_id": target_user_id,
                "email": target.get("email") if target else None,
            },
        )
        try:
            from app.modules.trust.notify import notify

            await notify(
                recipient_user_id=target_user_id,
                recipient_business_id=business_id,
                type="ACCOUNT_SUSPENDED",
                title="Your TradeBay account was suspended",
                message=cleaned,
                reference_type="user",
                reference_id=target_user_id,
                fanout_business=False,
            )
        except Exception:
            pass

    async def reactivate_user(
        self,
        *,
        target_user_id: str,
        actor_user_id: str,
        business_id: str | None,
        ip_address: str | None,
    ) -> None:
        user = await self.users.get_by_id(target_user_id)
        if user is None:
            raise NotFoundError("We couldn't find that account.")
        status = UserStatus.ACTIVE if user.get("email_verified_at") else UserStatus.PENDING
        await self.users.update(
            target_user_id,
            {
                "status": status,
                "suspension_reason": None,
                "suspended_at": None,
                "updated_at": utc_now(),
            },
        )
        actor = await self.users.get_by_id(actor_user_id)
        await self.audit.log(
            action="USER_REACTIVATED",
            resource_type="user",
            resource_id=target_user_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={
                "actor_name": _person_label(actor),
                "member_name": _person_label(user),
                "target_user_id": target_user_id,
                "email": user.get("email"),
            },
        )
        try:
            from app.modules.trust.notify import notify

            await notify(
                recipient_user_id=target_user_id,
                recipient_business_id=business_id,
                type="ACCOUNT_REACTIVATED",
                title="Your TradeBay account was reactivated",
                message="You can sign in again and continue working for this business.",
                reference_type="user",
                reference_id=target_user_id,
                fanout_business=False,
            )
        except Exception:
            pass

    async def _role_in_business(
        self, role_id: str, business_id: str, *, allow_inactive: bool = False
    ) -> dict[str, Any]:
        role = await self.roles.get_by_id(role_id)
        if role is None or str(role["business_account_id"]) != business_id:
            raise ForbiddenError("We couldn't find that role in this company.")
        if (
            not allow_inactive
            and (role.get("is_active") is False or role.get("deleted_at") is not None)
        ):
            raise ConflictError("That role was deleted. Choose another role.")
        return role

    async def _permission_ids(self, codes: set[str]) -> list[ObjectId]:
        ids: list[ObjectId] = []
        for code in codes:
            resource, _, action = code.partition(".")
            perm = await self.permissions.get_by_resource_action(resource, action)
            if perm is None:
                raise PrivilegeEscalationError()
            ids.append(perm["_id"])
        return ids
