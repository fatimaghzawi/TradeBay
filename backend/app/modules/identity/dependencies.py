"""Auth and authorization FastAPI dependencies.

Permission checks use resource+action codes — never `if role == "admin"`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Cookie, Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, ErrorCode
from app.core.exceptions import UnauthorizedError
from app.core.logging import business_id_ctx, user_id_ctx
from app.core.security import TokenError, decode_access_token
from app.modules.identity.constants import UserStatus, is_business_operational
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
        raise UnauthorizedError("Invalid access token claims")

    sessions = SessionRepository()
    users = UserRepository()
    user = await users.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    # Prefer ACCOUNT_INACTIVE (403) over SESSION_REVOKED (401) after suspend,
    # which revokes sessions before the next authenticated request.
    if user.get("status") in {UserStatus.SUSPENDED, UserStatus.DEACTIVATED}:
        raise AccountInactiveError()

    session = await sessions.get_by_id(session_id)
    if session is None or session.get("revoked_at") is not None:
        raise UnauthorizedError("Session is not valid", code=ErrorCode.SESSION_REVOKED)

    ctx = AuthContext(user=user, session=session)
    user_id_ctx.set(user_id)

    business_id = session.get("active_business_account_id")
    if business_id:
        business = await BusinessRepository().get_by_id(business_id)
        if business is not None and not is_business_operational(str(business.get("status", ""))):
            raise BusinessInactiveError()
        membership = await MembershipRepository().get_active_membership(user_id, business_id)
        ctx.business = business
        ctx.membership = membership
        if membership:
            role = await RoleRepository().get_by_id(membership["role_id"])
            ctx.role = role
            if role:
                perm_ids = await RolePermissionRepository().list_permission_ids_for_role(role["_id"])
                codes: set[str] = set()
                perm_repo = PermissionRepository()
                for pid in perm_ids:
                    perm = await perm_repo.get_by_id(pid)
                    if perm:
                        codes.add(f"{perm['resource']}.{perm['action']}")
                ctx.permissions = codes
        business_id_ctx.set(str(business_id))

    request.state.auth = ctx
    return ctx


async def get_current_business(auth: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    if auth.business is None:
        raise BusinessContextRequiredError()
    return auth.business


async def get_current_membership(
    auth: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    if auth.membership is None:
        raise BusinessContextRequiredError()
    return auth.membership


def assert_email_verified(user: dict[str, Any]) -> None:
    """Reusable FR-AUTH-02 gate for commercial writes in this and future domains."""
    if not user.get("email_verified_at"):
        raise EmailUnverifiedError()
    if user.get("status") != UserStatus.ACTIVE:
        raise AccountInactiveError()


def require_permission(resource: str, action: str) -> Callable[..., Any]:
    async def _dependency(auth: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        if auth.business is None or auth.membership is None:
            raise BusinessContextRequiredError()
        if not auth.has_permission(resource, action):
            raise PermissionDeniedError(resource, action)
        return auth

    return _dependency


async def _load_permissions_for_membership(membership: dict[str, Any]) -> tuple[dict[str, Any] | None, set[str]]:
    role = await RoleRepository().get_by_id(membership["role_id"])
    codes: set[str] = set()
    if role:
        perm_ids = await RolePermissionRepository().list_permission_ids_for_role(role["_id"])
        perm_repo = PermissionRepository()
        for pid in perm_ids:
            perm = await perm_repo.get_by_id(pid)
            if perm:
                codes.add(f"{perm['resource']}.{perm['action']}")
    return role, codes


def require_business_scope() -> Callable[..., Any]:
    """Require an active membership in the path business_id (no specific permission)."""

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
    """Authorize against membership in path business_id (not only the session active business)."""

    async def _dependency(
        business_id: str,
        auth: Annotated[AuthContext, Depends(get_current_user)],
    ) -> AuthContext:
        return await resolve_business_permission(
            business_id=business_id,
            auth=auth,
            resource=resource,
            action=action,
        )

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


def require_verified_email() -> Callable[..., Any]:
    async def _dependency(auth: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
        assert_email_verified(auth.user)
        return auth

    return _dependency


def require_commercial_write(resource: str, action: str) -> Callable[..., Any]:
    """FR-AUTH-02 + FR-AUTH-04: verified email AND resource.action on the active membership."""

    permission_dep = require_permission(resource, action)

    async def _dependency(auth: Annotated[AuthContext, Depends(permission_dep)]) -> AuthContext:
        assert_email_verified(auth.user)
        return auth

    return _dependency


def require_seller(resource: str, action: str) -> Callable[..., Any]:
    """Selling writes: permission + verified supplier profile for the active company."""

    inner = require_commercial_write(resource, action)

    async def _dependency(auth: Annotated[AuthContext, Depends(inner)]) -> AuthContext:
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
