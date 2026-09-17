"""Business / members / roles / permissions router placeholders + implemented business basics."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_business_service,
    get_current_user,
    require_permission,
)
from app.modules.identity.permissions import DEFAULT_PERMISSION_CATALOG
from app.modules.identity.schemas import CreateBusinessRequest, SwitchBusinessRequest
from app.modules.identity.service import AuthService, BusinessService
from app.shared.schemas.response import paginated, success

businesses_router = APIRouter(prefix="/businesses", tags=["Businesses"])
members_router = APIRouter(prefix="/members", tags=["Identity"])
roles_router = APIRouter(prefix="/roles", tags=["Identity"])
permissions_router = APIRouter(prefix="/permissions", tags=["Identity"])


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
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    business = await service.create_for_user(
        user_id=auth.user_id,
        name=body.name,
        account_type=body.type,
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


@members_router.get("", summary="List members (scaffolded)")
async def list_members(
    _: Annotated[AuthContext, Depends(require_permission("users", "read"))],
) -> dict[str, Any]:
    return paginated([], total=0)


@roles_router.get("", summary="List roles (scaffolded)")
async def list_roles(
    _: Annotated[AuthContext, Depends(require_permission("roles", "read"))],
) -> dict[str, Any]:
    return paginated([], total=0)


@permissions_router.get("", summary="List permission catalog")
async def list_permissions(
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    items = [
        {"resource": resource, "action": action, "code": f"{resource}.{action}", "description": description}
        for resource, action, description in DEFAULT_PERMISSION_CATALOG
    ]
    return paginated(items, page=1, page_size=len(items), total=len(items))
