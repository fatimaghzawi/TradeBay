"""Business, members, roles, invitations, and account suspension."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_business_service,
    get_current_user,
    get_directory_service,
    require_permission,
    require_verified_email,
)
from app.modules.identity.directory import DirectoryService
from app.modules.identity.http import client_ip
from app.modules.identity.permissions import DEFAULT_PERMISSION_CATALOG
from app.modules.identity.schemas import (
    AcceptInvitationRequest,
    CreateBusinessRequest,
    CreateInvitationRequest,
    CreateRoleRequest,
    SuspendUserRequest,
    SwitchBusinessRequest,
    UpdateMemberRoleRequest,
    UpdateRoleRequest,
)
from app.modules.identity.service import AuthService, BusinessService
from app.shared.schemas.response import paginated, success

businesses_router = APIRouter(prefix="/businesses", tags=["Businesses"])
members_router = APIRouter(prefix="/members", tags=["Identity"])
roles_router = APIRouter(prefix="/roles", tags=["Identity"])
permissions_router = APIRouter(prefix="/permissions", tags=["Identity"])
invitations_router = APIRouter(prefix="/invitations", tags=["Identity"])
users_router = APIRouter(prefix="/users", tags=["Identity"])


@businesses_router.get("", summary="List businesses for current user")
async def list_businesses(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    items = await service.list_for_user(auth.user_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@businesses_router.post("", summary="Create a business account for current user")
async def create_business(
    body: CreateBusinessRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_verified_email())],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    business = await service.create_for_user(
        user_id=auth.user_id,
        name=body.name,
        account_type=body.type,
        legal_name=body.legal_name,
        tax_number=body.tax_number,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        address=body.address.model_dump() if body.address else None,
        ip_address=client_ip(request),
    )
    return success(business)


@businesses_router.get("/current", summary="Get active business from session")
async def current_business(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    business = await service.get_current(auth.business_id)
    return success(business)


@businesses_router.post("/current/switch", summary="Switch the session's active business")
async def switch_business(
    body: SwitchBusinessRequest,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    result = await service.switch_business(
        session_id=auth.session_id,
        user_id=auth.user_id,
        business_id=body.business_id,
    )
    cookie: dict[str, Any] = {
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.access_token_expire_minutes * 60,
    }
    if settings.cookie_domain:
        cookie["domain"] = settings.cookie_domain
    response.set_cookie(ACCESS_COOKIE_NAME, result["access_token"], **cookie)
    return success({"business": result["business"]})


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
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
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


@invitations_router.post("/accept", summary="Accept an invitation for the current user")
async def accept_invitation(
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


@invitations_router.post("/{invitation_id}/revoke", summary="Revoke a pending invitation")
async def revoke_invitation(
    invitation_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("users", "invite"))],
    directory: Annotated[DirectoryService, Depends(get_directory_service)],
) -> dict[str, Any]:
    await directory.revoke_invitation(
        business_id=str(auth.business_id),
        invitation_id=invitation_id,
        actor_user_id=auth.user_id,
        ip_address=client_ip(request),
    )
    return success({"revoked": True})


@users_router.post("/suspend", summary="Suspend a user with a required reason")
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
