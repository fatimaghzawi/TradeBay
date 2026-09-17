"""Identity domain routes: members, roles, invitations, sessions, account, platform.

Nested `/businesses/{id}/...` team routes are registered on `businesses_router`
so the business account file stays focused on company CRUD/context.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME
from app.modules.identity.business_router import businesses_router
from app.modules.identity.constants import BusinessAccountType
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_current_user,
    get_directory_service,
    require_business_permission,
    require_business_scope,
    require_permission,
    resolve_business_permission,
)
from app.modules.identity.directory import DirectoryService
from app.modules.identity.exceptions import InvitationInvalidError, MembershipRequiredError
from app.modules.identity.http import client_ip
from app.modules.identity.permissions import DEFAULT_PERMISSION_CATALOG
from app.modules.identity.repository import BusinessRepository
from app.modules.identity.schemas import (
    AcceptInvitationRequest,
    AuthMeResponse,
    CreateInvitationRequest,
    CreateRoleRequest,
    SuspendMembershipRequest,
    SuspendUserRequest,
    UpdateMemberRoleRequest,
    UpdateProfileRequest,
    UpdateRoleRequest,
)
from app.modules.identity.service import AuthService
from app.shared.schemas.response import paginated, success
from app.shared.services.audit import AuditService

members_router = APIRouter(prefix="/members", tags=["Identity"])
roles_router = APIRouter(prefix="/roles", tags=["Identity"])
permissions_router = APIRouter(prefix="/permissions", tags=["Identity"])
invitations_router = APIRouter(prefix="/invitations", tags=["Identity"])
users_router = APIRouter(prefix="/users", tags=["Identity"])
me_router = APIRouter(prefix="/me", tags=["Account"])
sessions_router = APIRouter(prefix="/sessions", tags=["Sessions"])
platform_router = APIRouter(prefix="/platform", tags=["Platform"])


# ── Nested members ───────────────────────────────────────────────────────────


@businesses_router.get("/{business_id}/members", summary="List members of a business")
async def list_business_members(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    items = await directory.list_members(business_id=business_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@businesses_router.get(
    "/{business_id}/members/{membership_id}",
    summary="View a specific membership",
)
async def get_business_member(
    business_id: str,
    membership_id: str,
    auth: Annotated[AuthContext, Depends(require_business_scope())],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    return success(await directory.get_member(business_id=business_id, membership_id=membership_id))


@businesses_router.patch(
    "/{business_id}/members/{membership_id}/role",
    summary="Change a member's role",
)
async def update_business_member_role(
    business_id: str,
    membership_id: str,
    body: UpdateMemberRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.update_member_role(
        business_id=business_id,
        membership_id=membership_id,
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.delete(
    "/{business_id}/members/{membership_id}",
    summary="Remove a member",
)
async def remove_business_member(
    business_id: str,
    membership_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "remove"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.remove_member(
        business_id=business_id,
        membership_id=membership_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"removed": True})


@businesses_router.post(
    "/{business_id}/members/{membership_id}/suspend",
    summary="Suspend a membership",
)
async def suspend_membership(
    business_id: str,
    membership_id: str,
    body: SuspendMembershipRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.suspend_membership(
        business_id=business_id,
        membership_id=membership_id,
        reason=body.reason,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"suspended": True})


@businesses_router.post(
    "/{business_id}/members/{membership_id}/reactivate",
    summary="Reactivate a suspended membership",
)
async def reactivate_membership(
    business_id: str,
    membership_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.reactivate_membership(
        business_id=business_id,
        membership_id=membership_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"reactivated": True})


# ── Nested invitations ───────────────────────────────────────────────────────


@businesses_router.get("/{business_id}/invitations", summary="List invitations for a business")
async def list_business_invitations(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    items = await directory.list_invitations(business_id=business_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@businesses_router.post("/{business_id}/invitations", summary="Invite a person by email and role")
async def create_business_invitation(
    business_id: str,
    body: CreateInvitationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "invite"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.create_invitation(
        business_id=business_id,
        email=str(body.email),
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


# ── Nested roles ─────────────────────────────────────────────────────────────


@businesses_router.get("/{business_id}/roles", summary="List roles for a business")
async def list_business_roles(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    items = await directory.list_roles(business_id=business_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@businesses_router.get("/{business_id}/roles/{role_id}", summary="View a role and its permissions")
async def get_business_role(
    business_id: str,
    role_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    return success(await directory.get_role(business_id=business_id, role_id=role_id))


@businesses_router.post("/{business_id}/roles", summary="Create a custom role")
async def create_business_role(
    business_id: str,
    body: CreateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.create_role(
        business_id=business_id,
        name=body.name,
        permission_codes=body.permissions,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.patch("/{business_id}/roles/{role_id}", summary="Update a role's permissions")
async def update_business_role(
    business_id: str,
    role_id: str,
    body: UpdateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.update_role(
        business_id=business_id,
        role_id=role_id,
        permission_codes=body.permissions,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.delete("/{business_id}/roles/{role_id}", summary="Delete a custom role")
async def delete_business_role(
    business_id: str,
    role_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.delete_role(
        business_id=business_id,
        role_id=role_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"deleted": True})


# ── Nested audit logs ────────────────────────────────────────────────────────


@businesses_router.get("/{business_id}/audit-logs", summary="List business audit events")
async def list_business_audit_logs(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("audit_logs", "read"))],
) -> dict[str, Any]:
    del auth
    items = await AuditService().list_for_business(business_id)
    return paginated(items, page=1, page_size=len(items) or 50, total=len(items))


@businesses_router.get(
    "/{business_id}/audit-logs/{audit_log_id}",
    summary="View one business audit event",
)
async def get_business_audit_log(
    business_id: str,
    audit_log_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("audit_logs", "read"))],
) -> dict[str, Any]:
    del auth
    item = await AuditService().get_for_business(business_id, audit_log_id)
    if item is None:
        raise InvitationInvalidError("Audit log not found")
    return success(item)


# ── Flat legacy aliases (active-business scoped) ─────────────────────────────


@members_router.get("", summary="List members of the active business")
async def list_members(
    auth: Annotated[AuthContext, Depends(require_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    items = await directory.list_members(business_id=str(auth.business_id))
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@members_router.patch("/{membership_id}", summary="Change a member's role")
async def update_member(
    membership_id: str,
    body: UpdateMemberRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.update_member_role(
        business_id=str(auth.business_id),
        membership_id=membership_id,
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@members_router.delete("/{membership_id}", summary="Remove a member")
async def remove_member(
    membership_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "remove"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.remove_member(
        business_id=str(auth.business_id),
        membership_id=membership_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"removed": True})


@roles_router.get("", summary="List roles for the active business")
async def list_roles(
    auth: Annotated[AuthContext, Depends(require_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    items = await directory.list_roles(business_id=str(auth.business_id))
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@roles_router.post("", summary="Create a custom role")
async def create_role(
    body: CreateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.create_role(
        business_id=str(auth.business_id),
        name=body.name,
        permission_codes=body.permissions,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@roles_router.patch("/{role_id}", summary="Update custom or system role grants")
async def update_role(
    role_id: str,
    body: UpdateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.update_role(
        business_id=str(auth.business_id),
        role_id=role_id,
        permission_codes=body.permissions,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@roles_router.delete("/{role_id}", summary="Delete a custom role")
async def delete_role(
    role_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("roles", "manage"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.delete_role(
        business_id=str(auth.business_id),
        role_id=role_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"deleted": True})


@permissions_router.get("", summary="List permission catalog")
async def list_permissions(
    auth: Annotated[AuthContext, Depends(require_permission("roles", "read"))],
) -> dict[str, Any]:
    del auth
    items = [
        {"resource": resource, "action": action, "code": f"{resource}.{action}", "description": description}
        for resource, action, description in DEFAULT_PERMISSION_CATALOG
    ]
    return paginated(items, page=1, page_size=len(items), total=len(items))


@invitations_router.get("", summary="List invitations for the active business")
async def list_invitations(
    auth: Annotated[AuthContext, Depends(require_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    items = await directory.list_invitations(business_id=str(auth.business_id))
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@invitations_router.post("", summary="Invite a person by email and role")
async def create_invitation(
    body: CreateInvitationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "invite"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.create_invitation(
        business_id=str(auth.business_id),
        email=str(body.email),
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@invitations_router.get("/{invitation_id}", summary="View a specific invitation")
async def get_invitation(
    invitation_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.get_invitation(
        invitation_id=invitation_id,
        requester_email=str(auth.user["email"]),
        requester_user_id=auth.user_id,
    )
    return success(result)


@invitations_router.post("/accept", summary="Accept invitation by token (legacy)", include_in_schema=False)
async def accept_invitation_by_token(
    body: AcceptInvitationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.accept_invitation(
        raw_token=body.token,
        user_id=auth.user_id,
        user_email=str(auth.user["email"]),
        ip_address=client_ip(request),
    )
    return success(result)


@invitations_router.post("/{invitation_id}/accept", summary="Accept a valid invitation")
async def accept_invitation_by_id(
    invitation_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    body: AcceptInvitationRequest | None = None,
) -> dict[str, Any]:
    if body and body.token:
        result = await directory.accept_invitation(
            raw_token=body.token,
            user_id=auth.user_id,
            user_email=str(auth.user["email"]),
            ip_address=client_ip(request),
        )
    else:
        result = await directory.accept_invitation_by_id(
            invitation_id=invitation_id,
            user_id=auth.user_id,
            user_email=str(auth.user["email"]),
            ip_address=client_ip(request),
        )
    return success(result)


@invitations_router.post("/{invitation_id}/decline", summary="Decline an invitation")
async def decline_invitation(
    invitation_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.decline_invitation(
        invitation_id=invitation_id,
        user_email=str(auth.user["email"]),
        user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"declined": True})


@invitations_router.post("/{invitation_id}/revoke", summary="Revoke a pending invitation")
async def revoke_invitation(
    invitation_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    invitation = await directory.invitations.get_by_id(invitation_id)
    if invitation is None:
        raise InvitationInvalidError()
    business_id = str(invitation["business_account_id"])
    scoped = await resolve_business_permission(
        business_id=business_id,
        auth=auth,
        resource="users",
        action="invite",
    )
    await directory.revoke_invitation(
        business_id=business_id,
        invitation_id=invitation_id,
        actor_user_id=scoped.user_id,
        ip_address=client_ip(request),
    )
    return success({"revoked": True})


@users_router.post("/suspend", summary="Suspend a user account with a required reason")
async def suspend_user(
    body: SuspendUserRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.suspend_user(
        target_user_id=body.user_id,
        reason=body.reason,
        actor_user_id=auth.user_id,
        business_id=auth.business_id,
        ip_address=client_ip(request),
    )
    return success({"suspended": True})


@users_router.post("/{user_id}/reactivate", summary="Reactivate a suspended user")
async def reactivate_user(
    user_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.reactivate_user(
        target_user_id=user_id,
        actor_user_id=auth.user_id,
        business_id=auth.business_id,
        ip_address=client_ip(request),
    )
    return success({"reactivated": True})


# ── /me ──────────────────────────────────────────────────────────────────────


@me_router.get("", summary="Current user profile")
async def get_me(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = await service.get_me(user_id=auth.user_id, session=auth.session)
    return success(AuthMeResponse(**payload).model_dump())


@me_router.patch("", summary="Update personal profile fields")
async def patch_me(
    body: UpdateProfileRequest,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    user = await service.update_profile(
        user_id=auth.user_id,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    return success({"user": user})


# ── Sessions ─────────────────────────────────────────────────────────────────


@sessions_router.get("", summary="List active sessions for the current user")
async def list_sessions(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    items = await service.list_sessions(user_id=auth.user_id, current_session_id=auth.session_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@sessions_router.delete("/{session_id}", summary="Revoke a specific session")
async def revoke_session(
    session_id: str,
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    await service.revoke_session(
        user_id=auth.user_id, session_id=session_id, ip_address=client_ip(request)
    )
    if session_id == auth.session_id:
        common: dict[str, Any] = {"path": "/"}
        if settings.cookie_domain:
            common["domain"] = settings.cookie_domain
        response.delete_cookie(ACCESS_COOKIE_NAME, **common)
    return success({"revoked": True})


@sessions_router.delete("", summary="Revoke other sessions (keep current)")
async def revoke_other_sessions(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    result = await service.logout_all(
        user_id=auth.user_id,
        current_session_id=auth.session_id,
        include_current=False,
        ip_address=client_ip(request),
    )
    return success(result)


# ── Platform ─────────────────────────────────────────────────────────────────


@platform_router.get("/me", summary="Platform business membership context")
async def platform_me(
    auth: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    scoped = await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="businesses",
        action="read",
    )
    return success(
        {
            "platform_business": {
                "id": str(platform["_id"]),
                "name": platform["name"],
                "type": platform["type"],
                "status": platform["status"],
            },
            "membership_id": str(scoped.membership["_id"]) if scoped.membership else None,
            "role_id": str(scoped.membership["role_id"]) if scoped.membership else None,
            "role_name": scoped.role["name"] if scoped.role else None,
            "active_is_platform": auth.business_id == str(platform["_id"]),
            "permissions": sorted(scoped.permissions),
        }
    )


@platform_router.get("/audit-logs", summary="Platform-level audit access")
async def platform_audit_logs(
    auth: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="audit_logs",
        action="read",
    )
    items = await AuditService().list_for_business(platform["_id"])
    return paginated(items, page=1, page_size=len(items) or 50, total=len(items))
