"""Members, roles, invitations, and account suspension — permission-code authorization only."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.security import generate_invitation_token, hash_token
from app.db.transactions import run_in_transaction
from app.modules.identity.constants import (
    INVITATION_TTL_DAYS,
    InvitationStatus,
    MembershipStatus,
    UserStatus,
)
from app.modules.identity.email import get_email_sender
from app.modules.identity.exceptions import (
    InvitationInvalidError,
    PrivilegeEscalationError,
    SystemRoleProtectedError,
)
from app.modules.identity.guards import assert_not_last_admin
from app.modules.identity.permissions import permission_code
from app.modules.identity.repository import (
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


class DirectoryService:
    def __init__(
        self,
        *,
        users: UserRepository | None = None,
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
        codes: set[str] = set()
        for pid in ids:
            perm = await self.permissions.get_by_id(pid)
            if perm:
                codes.add(permission_code(str(perm["resource"]), str(perm["action"])))
        return codes

    async def assert_subset(self, *, actor_permissions: set[str], requested: set[str]) -> None:
        if not requested <= actor_permissions:
            raise PrivilegeEscalationError()

    async def list_members(self, *, business_id: str) -> list[dict[str, Any]]:
        rows = await self.memberships.list_for_business(business_id)
        results: list[dict[str, Any]] = []
        for membership in rows:
            user = await self.users.get_by_id(membership["user_id"])
            role = await self.roles.get_by_id(membership["role_id"])
            results.append(
                {
                    "id": str(membership["_id"]),
                    "user_id": str(membership["user_id"]),
                    "email": user["email"] if user else None,
                    "role_id": str(membership["role_id"]),
                    "role_name": role["name"] if role else None,
                    "status": membership["status"],
                }
            )
        return results

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
        membership = await self.memberships.get_by_id(membership_id)
        if membership is None or str(membership["business_account_id"]) != business_id:
            raise InvitationInvalidError("Membership not found")
        role = await self._role_in_business(role_id, business_id)
        await self.assert_subset(
            actor_permissions=actor_permissions,
            requested=await self.permission_codes_for_role(role["_id"]),
        )
        if str(membership["role_id"]) != str(role["_id"]):
            await assert_not_last_admin(business_account_id=business_id, membership=membership)
        updated = await self.memberships.update(
            membership_id,
            {"role_id": role["_id"], "updated_at": utc_now()},
        )
        await self.audit.log(
            action="MEMBER_ROLE_CHANGED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"target_user_id": str(membership["user_id"]), "role_id": str(role["_id"])},
        )
        return {"id": str(updated["_id"]) if updated else membership_id, "role_id": str(role["_id"])}

    async def remove_member(
        self,
        *,
        business_id: str,
        membership_id: str,
        actor_user_id: str,
        ip_address: str | None,
    ) -> None:
        membership = await self.memberships.get_by_id(membership_id)
        if membership is None or str(membership["business_account_id"]) != business_id:
            raise InvitationInvalidError("Membership not found")
        await assert_not_last_admin(business_account_id=business_id, membership=membership)
        await self.memberships.update(
            membership_id,
            {"status": MembershipStatus.REMOVED, "updated_at": utc_now()},
        )
        await self.audit.log(
            action="MEMBER_REMOVED",
            resource_type="membership",
            resource_id=membership_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"target_user_id": str(membership["user_id"])},
        )

    async def list_roles(self, *, business_id: str) -> list[dict[str, Any]]:
        rows = await self.roles.find_many({"business_account_id": parse_object_id(business_id)}, limit=100)
        results: list[dict[str, Any]] = []
        for role in rows:
            codes = sorted(await self.permission_codes_for_role(role["_id"]))
            results.append(
                {
                    "id": str(role["_id"]),
                    "name": role["name"],
                    "is_system_role": bool(role.get("is_system_role")),
                    "permissions": codes,
                }
            )
        return results

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
                "created_at": now,
                "updated_at": now,
            }
        )
        await self.role_permissions.replace_for_role(
            role["_id"],
            await self._permission_ids(requested),
            created_at=now,
        )
        await self.audit.log(
            action="ROLE_CREATED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"name": name, "permissions": sorted(requested)},
        )
        return {"id": str(role["_id"]), "name": role["name"], "is_system_role": False, "permissions": sorted(requested)}

    async def update_role(
        self,
        *,
        business_id: str,
        role_id: str,
        permission_codes: list[str],
        actor_user_id: str,
        actor_permissions: set[str],
        ip_address: str | None,
    ) -> dict[str, Any]:
        role = await self._role_in_business(role_id, business_id)
        requested = set(permission_codes)
        await self.assert_subset(actor_permissions=actor_permissions, requested=requested)
        now = utc_now()
        await self.role_permissions.replace_for_role(
            role["_id"],
            await self._permission_ids(requested),
            created_at=now,
        )
        await self.roles.update(role["_id"], {"updated_at": now})
        await self.audit.log(
            action="ROLE_UPDATED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"permissions": sorted(requested)},
        )
        return {"id": str(role["_id"]), "name": role["name"], "permissions": sorted(requested)}

    async def delete_role(self, *, business_id: str, role_id: str, actor_user_id: str, ip_address: str | None) -> None:
        role = await self._role_in_business(role_id, business_id)
        if role.get("is_system_role"):
            raise SystemRoleProtectedError()
        in_use = await self.memberships.count(
            {
                "business_account_id": parse_object_id(business_id),
                "role_id": role["_id"],
                "status": MembershipStatus.ACTIVE,
            }
        )
        if in_use:
            raise SystemRoleProtectedError()
        await self.role_permissions.replace_for_role(role["_id"], [], created_at=utc_now())
        await self.roles.delete(role["_id"])
        await self.audit.log(
            action="ROLE_DELETED",
            resource_type="role",
            resource_id=role["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
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
    ) -> dict[str, Any]:
        role = await self._role_in_business(role_id, business_id)
        await self.assert_subset(
            actor_permissions=actor_permissions,
            requested=await self.permission_codes_for_role(role["_id"]),
        )
        raw = generate_invitation_token()
        now = utc_now()
        invitation = await self.invitations.create(
            {
                "business_account_id": parse_object_id(business_id),
                "invited_email": email.lower().strip(),
                "role_id": role["_id"],
                "invited_by_user_id": parse_object_id(actor_user_id),
                "token_hash": hash_token(raw),
                "status": InvitationStatus.PENDING,
                "expires_at": now + timedelta(days=INVITATION_TTL_DAYS),
                "accepted_at": None,
                "created_at": now,
            }
        )
        await get_email_sender().send(
            to=email.lower().strip(),
            template="invitation",
            context={"business_id": business_id, "role_id": str(role["_id"]), "token": raw},
        )
        await self.audit.log(
            action="USER_INVITED",
            resource_type="invitation",
            resource_id=invitation["_id"],
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"invited_email": email.lower().strip(), "role_id": str(role["_id"])},
        )
        return {
            "id": str(invitation["_id"]),
            "invited_email": invitation["invited_email"],
            "role_id": str(role["_id"]),
            "status": invitation["status"],
        }

    async def list_invitations(self, *, business_id: str) -> list[dict[str, Any]]:
        rows = await self.invitations.list_for_business(business_id)
        return [
            {
                "id": str(row["_id"]),
                "invited_email": row["invited_email"],
                "role_id": str(row["role_id"]),
                "status": row["status"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]

    async def revoke_invitation(
        self, *, business_id: str, invitation_id: str, actor_user_id: str, ip_address: str | None
    ) -> None:
        invitation = await self.invitations.get_by_id(invitation_id)
        if invitation is None or str(invitation["business_account_id"]) != business_id:
            raise InvitationInvalidError()
        if invitation["status"] != InvitationStatus.PENDING:
            raise InvitationInvalidError("Invitation cannot be revoked")
        await self.invitations.update(invitation_id, {"status": InvitationStatus.REVOKED})
        await self.audit.log(
            action="INVITATION_REVOKED",
            resource_type="invitation",
            resource_id=invitation_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
        )

    async def accept_invitation(
        self, *, raw_token: str, user_id: str, user_email: str, ip_address: str | None = None
    ) -> dict[str, Any]:
        invitation = await self.invitations.get_by_token_hash(hash_token(raw_token))
        now = utc_now()
        if (
            invitation is None
            or invitation.get("status") != InvitationStatus.PENDING
            or as_utc(invitation["expires_at"]) < now
            or invitation["invited_email"].lower() != user_email.lower().strip()
        ):
            raise InvitationInvalidError()

        async def work(session: MongoSession) -> None:
            existing = await self.memberships.get_active_membership(
                user_id, invitation["business_account_id"], session=session
            )
            if existing is None:
                await self.memberships.create(
                    {
                        "user_id": parse_object_id(user_id),
                        "business_account_id": invitation["business_account_id"],
                        "role_id": invitation["role_id"],
                        "status": MembershipStatus.ACTIVE,
                        "joined_at": now,
                        "created_at": now,
                        "updated_at": now,
                    },
                    session=session,
                )
            await self.invitations.update(
                invitation["_id"],
                {"status": InvitationStatus.ACCEPTED, "accepted_at": now},
                session=session,
            )

        await run_in_transaction(work)
        await self.audit.log(
            action="INVITATION_ACCEPTED",
            resource_type="invitation",
            resource_id=invitation["_id"],
            business_account_id=invitation["business_account_id"],
            user_id=user_id,
            ip_address=ip_address,
        )
        return {
            "business_id": str(invitation["business_account_id"]),
            "role_id": str(invitation["role_id"]),
        }

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
            raise InvitationInvalidError("Suspension reason is required")
        now = utc_now()

        async def work(session: MongoSession) -> None:
            await self.users.update(
                target_user_id,
                {"status": UserStatus.SUSPENDED, "updated_at": now},
                session=session,
            )
            await self.sessions.revoke_all_for_user(target_user_id, now, session=session)

        await run_in_transaction(work)
        await self.audit.log(
            action="USER_SUSPENDED",
            resource_type="user",
            resource_id=target_user_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"reason": cleaned, "target_user_id": target_user_id},
        )

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
            raise InvitationInvalidError("User not found")
        status = UserStatus.ACTIVE if user.get("email_verified_at") else UserStatus.PENDING
        await self.users.update(target_user_id, {"status": status, "updated_at": utc_now()})
        await self.audit.log(
            action="USER_REACTIVATED",
            resource_type="user",
            resource_id=target_user_id,
            business_account_id=business_id,
            user_id=actor_user_id,
            ip_address=ip_address,
            metadata={"target_user_id": target_user_id},
        )

    async def _role_in_business(self, role_id: str, business_id: str) -> dict[str, Any]:
        role = await self.roles.get_by_id(role_id)
        if role is None or str(role["business_account_id"]) != business_id:
            raise InvitationInvalidError("Role does not belong to this business")
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
