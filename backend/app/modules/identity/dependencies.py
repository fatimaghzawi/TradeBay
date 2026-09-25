
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Cookie, Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, ErrorCode
from app.core.exceptions import UnauthorizedError
from app.core.logging import business_id_ctx, user_id_ctx
from app.core.security import TokenError, decode_access_token
from app.modules.identity.auth_cache import (
    get_cached_role_permissions,
    get_cached_session_auth,
    set_cached_role_permissions,
    set_cached_session_auth,
)
from app.modules.identity.constants import (
    BusinessAccountType,
    UserStatus,
    is_business_operational,
)
from app.modules.identity.directory import DirectoryService
from app.modules.identity.exceptions import (
    AccountInactiveError,
    BusinessContextRequiredError,
    BusinessInactiveError,
    EmailUnverifiedError,
    PermissionDeniedError,
    SellingNotVerifiedError,
)
from app.modules.identity.repository import (
    BusinessRepository,
    MembershipRepository,
    PermissionRepository,
    RolePermissionRepository,
    RoleRepository,
    SessionRepository,
    SupplierProfileRepository,
    UserRepository,
)
from app.modules.identity.service import AuthService, BusinessService


@dataclass(slots=True)
class AuthContext:

    user: dict[str, Any]
    session: dict[str, Any]
    business: dict[str, Any] | None = None
    membership: dict[str, Any] | None = None
    role: dict[str, Any] | None = None
    permissions: set[str] = field(default_factory=set)
                                                                                               
    inactive_business: dict[str, Any] | None = None

    @property
    def user_id(self) -> str:
        return str(self.user["_id"])

    @property
    def session_id(self) -> str:
        return str(self.session["_id"])

    @property
    def business_id(self) -> str | None:
        if self.business is None:
            return None
        return str(self.business["_id"])

    def has_permission(self, resource: str, action: str) -> bool:
        return f"{resource}.{action}" in self.permissions

                                                                               

def get_auth_service() -> AuthService:
    return AuthService()

def get_business_service() -> BusinessService:
    return BusinessService()

def get_directory_service() -> DirectoryService:
    return DirectoryService()

def _extract_access_token(
    authorization: str | None,
    access_cookie: str | None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return access_cookie

                                                                               

async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    access_cookie: Annotated[str | None, Cookie(alias=ACCESS_COOKIE_NAME)] = None,
) -> AuthContext:
    token = _extract_access_token(authorization, access_cookie)
    if not token:
        raise UnauthorizedError("Authentication required")

    try:
        payload = decode_access_token(token, settings)
    except TokenError as exc:
        raise UnauthorizedError("Invalid or expired access token") from exc

    user_id = str(payload.get("sub", ""))
    session_id = str(payload.get("sid", ""))
    if not user_id or not session_id:
        raise UnauthorizedError()

    cached = get_cached_session_auth(session_id)
    if cached is not None and str(cached.get("user_id")) == user_id:
        ctx = AuthContext(
            user=cached["user"],
            session=cached["session"],
            business=cached.get("business"),
            membership=cached.get("membership"),
            role=cached.get("role"),
            permissions=set(cached.get("permissions") or ()),
            inactive_business=cached.get("inactive_business"),
        )
        if ctx.user.get("status") in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
            raise AccountInactiveError()
        if ctx.session.get("revoked_at") is not None:
            raise UnauthorizedError(code=ErrorCode.SESSION_REVOKED)
        user_id_ctx.set(user_id)
        if ctx.business_id:
            business_id_ctx.set(ctx.business_id)
        request.state.auth = ctx
        return ctx

    users = UserRepository()
    sessions = SessionRepository()
    user, session = await asyncio.gather(
        users.get_by_id(user_id),
        sessions.get_by_id(session_id),
    )
    if user is None:
        raise UnauthorizedError()
                                                                             
                                                                   
    if user.get("status") in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
        raise AccountInactiveError()

    if session is None or session.get("revoked_at") is not None:
        raise UnauthorizedError(code=ErrorCode.SESSION_REVOKED)
    if str(session.get("user_id")) != str(user["_id"]):
        raise UnauthorizedError(code=ErrorCode.SESSION_REVOKED)

    ctx = AuthContext(user=user, session=session)
    user_id_ctx.set(user_id)

    business_id = session.get("active_business_account_id")
    if business_id:
        business, membership = await asyncio.gather(
            BusinessRepository().get_by_id(business_id),
            MembershipRepository().get_active_membership(user_id, business_id),
        )
        if business is not None and not is_business_operational(str(business.get("status", ""))):
            ctx.inactive_business = business
        else:
            ctx.business = business
            ctx.membership = membership
            if membership:
                role, codes = await _load_permissions_for_membership(membership)
                ctx.role = role
                ctx.permissions = codes
        business_id_ctx.set(str(business_id))

    set_cached_session_auth(
        session_id,
        {
            "user_id": user_id,
            "user": ctx.user,
            "session": ctx.session,
            "business": ctx.business,
            "membership": ctx.membership,
            "role": ctx.role,
            "permissions": frozenset(ctx.permissions),
            "inactive_business": ctx.inactive_business,
        },
    )
    request.state.auth = ctx
    return ctx

async def get_optional_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    access_cookie: Annotated[str | None, Cookie(alias=ACCESS_COOKIE_NAME)] = None,
) -> AuthContext | None:
    token = _extract_access_token(authorization, access_cookie)
    if not token:
        return None
    try:
        return await get_current_user(
            request=request,
            settings=settings,
            authorization=authorization,
            access_cookie=access_cookie,
        )
    except UnauthorizedError:
        return None
    except AccountInactiveError:
        raise
    except BusinessInactiveError:
        raise

SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

def _require_active_business(auth: AuthContext) -> None:
    if auth.inactive_business is not None:
        raise BusinessInactiveError()
    if auth.business is None or auth.membership is None:
        raise BusinessContextRequiredError()

def _require_verified_email_for_writes(request: Request, auth: AuthContext) -> None:
    if request.method.upper() not in SAFE_HTTP_METHODS:
        assert_email_verified(auth.user)

async def get_current_business(auth: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    _require_active_business(auth)
    assert auth.business is not None
    return auth.business

async def get_current_membership(
    auth: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_active_business(auth)
    assert auth.membership is not None
    return auth.membership

def assert_email_verified(user: dict[str, Any]) -> None:
    if not user.get("email_verified_at"):
        raise EmailUnverifiedError()
    if user.get("status") != UserStatus.ACTIVE:
        raise AccountInactiveError()

                                                                               

def require_permission(resource: str, action: str) -> Callable[..., Any]:

    async def _dependency(
        request: Request,
        auth: Annotated[AuthContext, Depends(get_current_user)],
    ) -> AuthContext:
        _require_active_business(auth)
        if not auth.has_permission(resource, action):
            raise PermissionDeniedError(resource, action)
        _require_verified_email_for_writes(request, auth)
        return auth

    return _dependency

async def _load_permissions_for_membership(membership: dict[str, Any]) -> tuple[dict[str, Any] | None, set[str]]:
    role = await RoleRepository().get_by_id(membership["role_id"])
    codes: set[str] = set()
    if role:
        role_key = str(role["_id"])
        cached = get_cached_role_permissions(role_key)
        if cached is not None:
            return role, set(cached)
        perm_ids = await RolePermissionRepository().list_permission_ids_for_role(role["_id"])
        codes = await PermissionRepository().codes_for_ids(perm_ids)
        set_cached_role_permissions(role_key, codes)
    return role, codes

def require_business_scope() -> Callable[..., Any]:

    async def _dependency(
        business_id: str,
        auth: Annotated[AuthContext, Depends(get_current_user)],
    ) -> AuthContext:
        membership = await MembershipRepository().get_active_membership(auth.user_id, business_id)
        if membership is None:
            raise BusinessContextRequiredError()
        business = await BusinessRepository().get_by_id(business_id)
        if business is None or not is_business_operational(str(business.get("status", ""))):
            raise BusinessInactiveError()
        role, codes = await _load_permissions_for_membership(membership)
        return AuthContext(
            user=auth.user,
            session=auth.session,
            business=business,
            membership=membership,
            role=role,
            permissions=codes,
        )

    return _dependency

def require_business_permission(resource: str, action: str) -> Callable[..., Any]:

    async def _dependency(
        business_id: str,
        request: Request,
        auth: Annotated[AuthContext, Depends(get_current_user)],
    ) -> AuthContext:
        scoped = await resolve_business_permission(
            business_id=business_id,
            auth=auth,
            resource=resource,
            action=action,
        )
        _require_verified_email_for_writes(request, scoped)
        return scoped

    return _dependency

async def resolve_business_permission(
    *,
    business_id: str,
    auth: AuthContext,
    resource: str,
    action: str,
) -> AuthContext:
    membership = await MembershipRepository().get_active_membership(auth.user_id, business_id)
    if membership is None:
        raise BusinessContextRequiredError()
    business = await BusinessRepository().get_by_id(business_id)
    if business is None or not is_business_operational(str(business.get("status", ""))):
        raise BusinessInactiveError()
    role, codes = await _load_permissions_for_membership(membership)
    scoped = AuthContext(
        user=auth.user,
        session=auth.session,
        business=business,
        membership=membership,
        role=role,
        permissions=codes,
    )
    if not scoped.has_permission(resource, action):
        raise PermissionDeniedError(resource, action)
    return scoped

def require_verification_document_access() -> Callable[..., Any]:

    async def _dependency(
        business_id: str,
        auth: Annotated[AuthContext, Depends(get_current_user)],
    ) -> AuthContext:
        membership = await MembershipRepository().get_active_membership(
            auth.user_id, business_id
        )
        if membership is not None:
            try:
                return await resolve_business_permission(
                    business_id=business_id,
                    auth=auth,
                    resource="businesses",
                    action="read",
                )
            except (PermissionDeniedError, BusinessInactiveError):
                pass
        platform = await BusinessRepository().find_one(
            {"type": BusinessAccountType.PLATFORM}
        )
        if platform is None:
            raise PermissionDeniedError("suppliers", "read")
        return await resolve_business_permission(
            business_id=str(platform["_id"]),
            auth=auth,
            resource="suppliers",
            action="read",
        )

    return _dependency

def require_verified_email() -> Callable[..., Any]:
    async def _dependency(auth: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        assert_email_verified(auth.user)
        return auth

    return _dependency

def require_commercial_write(resource: str, action: str) -> Callable[..., Any]:

    async def _dependency(auth: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        _require_active_business(auth)
        if not auth.has_permission(resource, action):
            raise PermissionDeniedError(resource, action)
        assert_email_verified(auth.user)
        return auth

    return _dependency

def require_seller(resource: str, action: str) -> Callable[..., Any]:

    async def _dependency(auth: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        _require_active_business(auth)
        if not auth.has_permission(resource, action):
            raise PermissionDeniedError(resource, action)
        assert_email_verified(auth.user)
        if auth.business_id is None:
            raise BusinessContextRequiredError()
        profile = await SupplierProfileRepository().get_by_business(auth.business_id)
        if profile is None or profile.get("verification_status") != "verified":
            raise SellingNotVerifiedError()
        return auth

    return _dependency

def get_refresh_token_from_cookie(
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> str | None:
    return refresh_cookie
