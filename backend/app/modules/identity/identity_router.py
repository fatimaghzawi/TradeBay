"""Identity domain routes: members, roles, invitations, sessions, account, platform.

Canonical trading-company APIs are session-scoped (`/members`, `/roles`,
`/invitations`, `/audit-logs`) and use the active business from the JWT.

Nested `/businesses/{id}/...` mirrors of those endpoints still work for
explicit-id clients but are hidden from OpenAPI to avoid Swagger duplicates.

Platform routes (`/platform/...`) are a separate tenant (TradeBay staff), not
duplicates of trading-company audit.
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
    get_business_service,
    get_current_user,
    get_directory_service,
    require_business_permission,
    require_permission,
    resolve_business_permission,
)
from app.modules.identity.directory import DirectoryService
from app.modules.identity.exceptions import (
    InvitationInvalidError,
    MembershipRequiredError,
    PrivilegeEscalationError,
)
from app.modules.identity.http import client_ip
from app.modules.identity.permissions import (
    DEFAULT_PERMISSION_CATALOG,
    TRADING_CODES,
    permission_code,
)
from app.modules.identity.repository import BusinessRepository
from app.modules.identity.schemas import (
    AcceptInvitationRequest,
    AuthMeResponse,
    CreateInvitationRequest,
    CreateRoleRequest,
    PlatformCreateTradingBusinessRequest,
    PlatformCreateUserRequest,
    ReviewSupplierVerificationRequest,
    SuspendMembershipRequest,
    SuspendUserRequest,
    UpdateMemberRoleRequest,
    UpdateProfileRequest,
    UpdateRoleRequest,
)
from app.modules.identity.service import AuthService, BusinessService
from app.shared.schemas.pagination import PaginationParams, get_pagination
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
audit_logs_router = APIRouter(prefix="/audit-logs", tags=["Audit"])


# ── Nested mirrors (hidden from Swagger; prefer session-scoped routes below) ─


@businesses_router.get(
    "/{business_id}/members",
    summary="List members of a business",
    include_in_schema=False,
)
async def list_business_members(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    del auth
    items, total = await directory.list_members(
        business_id=business_id,
        status=status,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@businesses_router.get(
    "/{business_id}/members/{membership_id}",
    summary="View a specific membership",
    include_in_schema=False,
)
async def get_business_member(
    business_id: str,
    membership_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    return success(await directory.get_member(business_id=business_id, membership_id=membership_id))


@businesses_router.patch(
    "/{business_id}/members/{membership_id}/role",
    summary="Change a member's role",
    include_in_schema=False,
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
    include_in_schema=False,
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
    include_in_schema=False,
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
    include_in_schema=False,
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


@businesses_router.get(
    "/{business_id}/invitations",
    summary="List invitations for a business",
    include_in_schema=False,
)
async def list_business_invitations(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    del auth
    items, total = await directory.list_invitations(
        business_id=business_id,
        status=status,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@businesses_router.post(
    "/{business_id}/invitations",
    summary="Invite a person by email and role",
    include_in_schema=False,
)
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
        company_email=str(body.company_email) if body.company_email else None,
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
        permissions=body.permissions,
    )
    return success(result)


@businesses_router.get(
    "/{business_id}/roles",
    summary="List roles for a business",
    include_in_schema=False,
)
async def list_business_roles(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str | None = None,
) -> dict[str, Any]:
    del auth
    items, total = await directory.list_roles(
        business_id=business_id,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@businesses_router.get(
    "/{business_id}/roles/{role_id}",
    summary="View a role and its permissions",
    include_in_schema=False,
)
async def get_business_role(
    business_id: str,
    role_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    del auth
    return success(await directory.get_role(business_id=business_id, role_id=role_id))


@businesses_router.post(
    "/{business_id}/roles",
    summary="Create a custom role",
    include_in_schema=False,
)
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


@businesses_router.patch(
    "/{business_id}/roles/{role_id}",
    summary="Update a role's permissions",
    include_in_schema=False,
)
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


@businesses_router.delete(
    "/{business_id}/roles/{role_id}",
    summary="Soft-delete a custom role",
    include_in_schema=False,
)
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


@businesses_router.get(
    "/{business_id}/audit-logs",
    summary="List business audit events",
    include_in_schema=False,
)
async def list_business_audit_logs(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("audit_logs", "read"))],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    action: str | None = None,
    resource_type: str | None = None,
) -> dict[str, Any]:
    del auth
    audit = AuditService()
    total = await audit.count_for_business(
        business_id, action=action, resource_type=resource_type
    )
    items = await audit.list_for_business(
        business_id,
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
        resource_type=resource_type,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@businesses_router.get(
    "/{business_id}/audit-logs/{audit_log_id}",
    summary="View one business audit event",
    include_in_schema=False,
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


# ── Session-scoped trading APIs (active business from JWT) ───────────────────


@members_router.get("", summary="List members of the active business")
async def list_members(
    auth: Annotated[AuthContext, Depends(require_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    items, total = await directory.list_members(
        business_id=str(auth.business_id),
        status=status,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@members_router.get("/{membership_id}", summary="View a membership in the active business")
async def get_member(
    membership_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("users", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    return success(
        await directory.get_member(business_id=str(auth.business_id), membership_id=membership_id)
    )


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


@members_router.post("/{membership_id}/suspend", summary="Suspend a membership in the active business")
async def suspend_member(
    membership_id: str,
    body: SuspendMembershipRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.suspend_membership(
        business_id=str(auth.business_id),
        membership_id=membership_id,
        reason=body.reason,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"suspended": True})


@members_router.post("/{membership_id}/reactivate", summary="Reactivate a suspended membership")
async def reactivate_member(
    membership_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "update"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.reactivate_membership(
        business_id=str(auth.business_id),
        membership_id=membership_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"reactivated": True})


@roles_router.get("", summary="List roles for the active business")
async def list_roles(
    auth: Annotated[AuthContext, Depends(require_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str | None = None,
) -> dict[str, Any]:
    items, total = await directory.list_roles(
        business_id=str(auth.business_id),
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@roles_router.get("/{role_id}", summary="View a role and its permissions")
async def get_role(
    role_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("roles", "read"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    return success(await directory.get_role(business_id=str(auth.business_id), role_id=role_id))


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


@roles_router.delete("/{role_id}", summary="Soft-delete a custom role")
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
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    items, total = await directory.list_invitations(
        business_id=str(auth.business_id),
        status=status,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@invitations_router.get("/preview", summary="Preview invitation details by token")
async def preview_invitation(
    token: str,
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    return success(await directory.preview_invitation_by_token(raw_token=token))


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
        company_email=str(body.company_email) if body.company_email else None,
        role_id=body.role_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
        permissions=body.permissions,
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


def _set_access_cookie(response: Response, settings: Settings, access_token: str) -> None:
    cookie: dict[str, Any] = {
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.access_token_expire_minutes * 60,
    }
    if settings.cookie_domain:
        cookie["domain"] = settings.cookie_domain
    response.set_cookie(ACCESS_COOKIE_NAME, access_token, **cookie)


async def _finalize_invitation_accept(
    *,
    result: dict[str, Any],
    response: Response,
    auth: AuthContext,
    auth_service: AuthService,
    settings: Settings,
) -> dict[str, Any]:
    """Activate the invited business on the session and refresh the access cookie."""
    switched = await auth_service.switch_business(
        session_id=auth.session_id,
        user_id=auth.user_id,
        business_id=result["business_id"],
    )
    _set_access_cookie(response, settings, switched["access_token"])
    return {
        **result,
        "business": switched["business"],
        "role_name": result.get("role_name") or switched["business"].get("role_name"),
    }


@invitations_router.post(
    "/accept",
    summary="Accept invitation by email link token",
    description="Invitee flow: body.token from the invitation email. Prefer this over /{invitation_id}/accept.",
)
async def accept_invitation_by_token(
    body: AcceptInvitationRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    result = await directory.accept_invitation(
        raw_token=body.token,
        user_id=auth.user_id,
        user_email=str(auth.user["email"]),
        session_id=auth.session_id,
        ip_address=client_ip(request),
    )
    return success(
        await _finalize_invitation_accept(
            result=result,
            response=response,
            auth=auth,
            auth_service=auth_service,
            settings=settings,
        )
    )


@invitations_router.post(
    "/decline",
    summary="Decline invitation by email link token",
    description="Invitee flow: body.token from the invitation email.",
)
async def decline_invitation_by_token(
    body: AcceptInvitationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.decline_invitation_by_token(
        raw_token=body.token,
        user_id=auth.user_id,
        user_email=str(auth.user["email"]),
        ip_address=client_ip(request),
    )
    return success({"declined": True})


@invitations_router.post("/{invitation_id}/resend", summary="Resend a pending invitation email")
async def resend_invitation(
    invitation_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "invite"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    result = await directory.resend_invitation(
        business_id=str(auth.business_id),
        invitation_id=invitation_id,
        actor_user_id=auth.user_id,
        actor_permissions=auth.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@invitations_router.post(
    "/{invitation_id}/accept",
    summary="Accept invitation by id",
    description="Same outcome as POST /invitations/accept when you already know the invitation id.",
)
async def accept_invitation_by_id(
    invitation_id: str,
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: AcceptInvitationRequest | None = None,
) -> dict[str, Any]:
    if body and body.token:
        result = await directory.accept_invitation(
            raw_token=body.token,
            user_id=auth.user_id,
            user_email=str(auth.user["email"]),
            session_id=auth.session_id,
            ip_address=client_ip(request),
        )
    else:
        result = await directory.accept_invitation_by_id(
            invitation_id=invitation_id,
            user_id=auth.user_id,
            user_email=str(auth.user["email"]),
            session_id=auth.session_id,
            ip_address=client_ip(request),
        )
    return success(
        await _finalize_invitation_accept(
            result=result,
            response=response,
            auth=auth,
            auth_service=auth_service,
            settings=settings,
        )
    )


@invitations_router.post(
    "/{invitation_id}/decline",
    summary="Decline invitation by id",
    description="Same outcome as POST /invitations/decline when you already know the invitation id.",
)
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


@users_router.post(
    "/suspend",
    summary="Suspend a user account (platform staff only)",
)
async def suspend_user(
    body: SuspendUserRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    """Global account suspension is a platform capability — not a trading-company action.

    Trading companies must use membership suspend (`POST /members/{id}/suspend`).
    """
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="update",
    )
    await directory.suspend_user(
        target_user_id=body.user_id,
        reason=body.reason,
        actor_user_id=auth.user_id,
        business_id=str(platform["_id"]),
        ip_address=client_ip(request),
    )
    return success({"suspended": True})


@users_router.post(
    "/{user_id}/reactivate",
    summary="Reactivate a suspended user (platform staff only)",
)
async def reactivate_user(
    user_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="update",
    )
    await directory.reactivate_user(
        target_user_id=user_id,
        actor_user_id=auth.user_id,
        business_id=str(platform["_id"]),
        ip_address=client_ip(request),
    )
    return success({"reactivated": True})


# ── /me ──────────────────────────────────────────────────────────────────────


@me_router.get(
    "",
    summary="Current user profile",
    include_in_schema=False,
    description="Alias of GET /auth/me — hidden from OpenAPI to avoid duplicate docs.",
)
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


# ── Audit logs (active trading business from JWT) ─────────────────────────────


@audit_logs_router.get(
    "",
    summary="List audit events for the active business",
    description="Uses the session active business. Prefer this over /businesses/{id}/audit-logs.",
)
async def list_audit_logs(
    auth: Annotated[AuthContext, Depends(require_permission("audit_logs", "read"))],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    action: str | None = None,
    resource_type: str | None = None,
) -> dict[str, Any]:
    audit = AuditService()
    total = await audit.count_for_business(
        str(auth.business_id), action=action, resource_type=resource_type
    )
    items = await audit.list_for_business(
        str(auth.business_id),
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
        resource_type=resource_type,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@audit_logs_router.get(
    "/{audit_log_id}",
    summary="View one audit event for the active business",
)
async def get_audit_log(
    audit_log_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("audit_logs", "read"))],
) -> dict[str, Any]:
    item = await AuditService().get_for_business(str(auth.business_id), audit_log_id)
    if item is None:
        raise InvitationInvalidError("Audit log not found")
    return success(item)


# ── Platform (TradeBay staff tenant — not the same as trading-company audit) ─


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


@platform_router.get(
    "/audit-logs",
    summary="List platform (TradeBay staff) audit events",
    description="Audit trail for the platform tenant only — not buyer/supplier company logs.",
)
async def platform_audit_logs(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    action: str | None = None,
    resource_type: str | None = None,
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
    audit = AuditService()
    total = await audit.count_for_business(
        platform["_id"], action=action, resource_type=resource_type
    )
    items = await audit.list_for_business(
        platform["_id"],
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
        resource_type=resource_type,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.get(
    "/audit-logs/{audit_log_id}",
    summary="View one platform audit event",
)
async def platform_audit_log_detail(
    audit_log_id: str,
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
    item = await AuditService().get_for_business(platform["_id"], audit_log_id)
    if item is None:
        raise InvitationInvalidError("Audit log not found")
    return success(item)


@platform_router.get("/businesses", summary="List all trading businesses for platform staff")
async def list_platform_businesses(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    account_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="businesses",
        action="read",
    )
    items, total = await service.list_trading_businesses(
        account_type=account_type,
        status=status,
        q=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.post(
    "/businesses",
    summary="Provision a buyer or supplier company with an owner admin",
)
async def create_platform_trading_business(
    body: PlatformCreateTradingBusinessRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="businesses",
        action="manage",
    )
    result = await service.provision_trading_account_by_platform(
        account_type=body.account_type,
        business_name=body.business_name,
        owner_email=str(body.owner_email),
        owner_password=body.owner_password,
        owner_first_name=body.owner_first_name,
        owner_last_name=body.owner_last_name,
        actor_user_id=auth.user_id,
        email_domain=body.email_domain,
        legal_name=body.legal_name,
        tax_number=body.tax_number,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        verify_supplier=body.verify_supplier,
        ip_address=client_ip(request),
    )
    return success(result)


@platform_router.get(
    "/businesses/{business_id}",
    summary="Get a buyer or supplier profile for platform staff",
)
async def get_platform_business(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="businesses",
        action="read",
    )
    payload = await service.get_trading_business(business_id)
    return success(payload)


@platform_router.get(
    "/businesses/{business_id}/members",
    summary="List members of a buyer or supplier for platform staff",
)
async def list_platform_business_members(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="businesses",
        action="read",
    )
    # Ensures the target is a trading company (buyer/supplier), not the platform tenant.
    await service.get_trading_business(business_id)
    items, total = await directory.list_members(
        business_id=business_id,
        status=status,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


def _trading_only_permission_codes(codes: list[str]) -> list[str]:
    """Trading company roles may never receive platform-only grants."""
    allowed = {permission_code(resource, action) for resource, action in TRADING_CODES}
    requested = set(codes)
    if not requested <= allowed:
        raise PrivilegeEscalationError()
    return sorted(requested)


@platform_router.get(
    "/businesses/{business_id}/roles",
    summary="List roles for a trading company (platform staff)",
)
async def list_platform_business_roles(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str | None = None,
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="read",
    )
    await service.get_trading_business(business_id)
    items, total = await directory.list_roles(
        business_id=business_id,
        query=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.get(
    "/businesses/{business_id}/roles/{role_id}",
    summary="View a trading-company role (platform staff)",
)
async def get_platform_business_role(
    business_id: str,
    role_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="read",
    )
    await service.get_trading_business(business_id)
    return success(await directory.get_role(business_id=business_id, role_id=role_id))


@platform_router.post(
    "/businesses/{business_id}/roles",
    summary="Create a custom role on a trading company (platform staff)",
)
async def create_platform_business_role(
    business_id: str,
    body: CreateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    scoped = await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="manage",
    )
    await service.get_trading_business(business_id)
    result = await directory.create_role(
        business_id=business_id,
        name=body.name,
        permission_codes=_trading_only_permission_codes(body.permissions),
        actor_user_id=scoped.user_id,
        actor_permissions=scoped.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@platform_router.patch(
    "/businesses/{business_id}/roles/{role_id}",
    summary="Update a trading-company role, including Business Admin (platform staff)",
)
async def update_platform_business_role(
    business_id: str,
    role_id: str,
    body: UpdateRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    scoped = await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="manage",
    )
    await service.get_trading_business(business_id)
    result = await directory.update_role(
        business_id=business_id,
        role_id=role_id,
        permission_codes=_trading_only_permission_codes(body.permissions),
        actor_user_id=scoped.user_id,
        actor_permissions=scoped.permissions,
        ip_address=client_ip(request),
        protect_owner_role=False,
    )
    return success(result)


@platform_router.delete(
    "/businesses/{business_id}/roles/{role_id}",
    summary="Soft-delete a custom trading-company role (platform staff)",
)
async def delete_platform_business_role(
    business_id: str,
    role_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    scoped = await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="manage",
    )
    await service.get_trading_business(business_id)
    await directory.delete_role(
        business_id=business_id,
        role_id=role_id,
        actor_user_id=scoped.user_id,
        ip_address=client_ip(request),
    )
    return success({"deleted": True})


@platform_router.patch(
    "/businesses/{business_id}/members/{membership_id}/role",
    summary="Change a trading-company member role (platform staff)",
)
async def update_platform_business_member_role(
    business_id: str,
    membership_id: str,
    body: UpdateMemberRoleRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    scoped = await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="roles",
        action="manage",
    )
    await service.get_trading_business(business_id)
    result = await directory.update_member_role(
        business_id=business_id,
        membership_id=membership_id,
        role_id=body.role_id,
        actor_user_id=scoped.user_id,
        actor_permissions=scoped.permissions,
        ip_address=client_ip(request),
    )
    return success(result)


@platform_router.get(
    "/businesses/{business_id}/audit-logs",
    summary="List audit events for a trading company (platform staff)",
    description=(
        "Company activity trail for buyer/supplier tenants. "
        "Requires platform audit_logs.read. Distinct from /platform/audit-logs "
        "which only covers the TradeBay staff tenant."
    ),
)
async def list_platform_business_audit_logs(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    action: str | None = None,
    resource_type: str | None = None,
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
    # Ensures the target is a trading company (buyer/supplier), not the platform tenant.
    await service.get_trading_business(business_id)
    audit = AuditService()
    total = await audit.count_for_business(
        business_id, action=action, resource_type=resource_type
    )
    items = await audit.list_for_business(
        business_id,
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
        resource_type=resource_type,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.get(
    "/businesses/{business_id}/audit-logs/{audit_log_id}",
    summary="View one company audit event (platform staff)",
)
async def get_platform_business_audit_log(
    business_id: str,
    audit_log_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
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
    await service.get_trading_business(business_id)
    item = await AuditService().get_for_business(business_id, audit_log_id)
    if item is None:
        raise InvitationInvalidError("Audit log not found")
    return success(item)


@platform_router.get(
    "/businesses/{business_id}/purchase-orders",
    summary="List purchase orders for a trading company (platform staff)",
)
async def list_platform_business_orders(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
) -> dict[str, Any]:
    from app.core.exceptions import BadRequestError
    from app.modules.procurement.service import ProcurementService

    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="orders",
        action="read",
    )
    trading = await service.get_trading_business(business_id)
    account_type = str(trading.get("type") or "")
    if account_type not in {BusinessAccountType.BUYER, BusinessAccountType.SUPPLIER}:
        raise BadRequestError("Purchase orders are only available for buyer or supplier companies")
    items, total = await ProcurementService().list_orders_for_business(
        business_id=business_id,
        as_buyer=account_type == BusinessAccountType.BUYER,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.get(
    "/businesses/{business_id}/rfqs",
    summary="List RFQs for a buyer company (platform staff)",
)
async def list_platform_business_rfqs(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
) -> dict[str, Any]:
    from app.core.exceptions import BadRequestError
    from app.modules.procurement.service import ProcurementService

    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="rfqs",
        action="read",
    )
    trading = await service.get_trading_business(business_id)
    if str(trading.get("type")) != BusinessAccountType.BUYER:
        raise BadRequestError("RFQs are only listed for buyer companies")
    items, total = await ProcurementService().list_rfqs_for_buyer_business(
        business_id=business_id,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.get("/users", summary="List all user accounts for platform staff")
async def list_platform_users(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    q: str | None = None,
    email_verified: bool | None = None,
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="read",
    )
    items, total = await directory.list_all_users(
        status=status,
        query=q,
        email_verified=email_verified,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.post("/users", summary="Provision a user account (platform staff)")
async def create_platform_user(
    body: PlatformCreateUserRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="invite",
    )
    user = await service.provision_user_by_platform(
        email=str(body.email),
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success(user)


@platform_router.post("/users/suspend", summary="Suspend any user account (platform staff)")
async def platform_suspend_user(
    body: SuspendUserRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="update",
    )
    await directory.suspend_user(
        target_user_id=body.user_id,
        reason=body.reason,
        actor_user_id=auth.user_id,
        business_id=str(platform["_id"]),
        ip_address=client_ip(request),
    )
    return success({"suspended": True})


@platform_router.post(
    "/users/{user_id}/reactivate",
    summary="Reactivate a suspended user account (platform staff)",
)
async def platform_reactivate_user(
    user_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="users",
        action="update",
    )
    await directory.reactivate_user(
        target_user_id=user_id,
        actor_user_id=auth.user_id,
        business_id=str(platform["_id"]),
        ip_address=client_ip(request),
    )
    return success({"reactivated": True})


@platform_router.get("/suppliers", summary="List supplier businesses for verification review")
async def list_platform_suppliers(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    verification_status: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="suppliers",
        action="read",
    )
    items, total = await service.list_supplier_verifications(
        verification_status=verification_status,
        q=q,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@platform_router.post(
    "/suppliers/{business_id}/review",
    summary="Approve, reject, or revoke supplier verification",
)
async def review_platform_supplier(
    business_id: str,
    body: ReviewSupplierVerificationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    platform = await BusinessRepository().find_one({"type": BusinessAccountType.PLATFORM})
    if platform is None:
        raise MembershipRequiredError()
    await resolve_business_permission(
        business_id=str(platform["_id"]),
        auth=auth,
        resource="suppliers",
        action="verify",
    )
    result = await service.review_supplier_verification(
        business_id=business_id,
        decision=body.decision,
        actor_user_id=auth.user_id,
        reason=body.reason,
        ip_address=client_ip(request),
    )
    return success(result)
