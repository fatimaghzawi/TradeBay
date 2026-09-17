"""Authentication routes — implemented foundation endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.exceptions import UnauthorizedError
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_current_user,
    get_refresh_token_from_cookie,
)
from app.modules.identity.schemas import (
    AuthMeResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.modules.identity.service import AuthService
from app.shared.schemas.response import success

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookies(response: Response, settings: Settings, tokens: dict[str, Any]) -> None:
    common: dict[str, Any] = {
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        tokens["access_token"],
        max_age=settings.access_token_expire_minutes * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens["refresh_token"],
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        **common,
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    common: dict[str, Any] = {"path": "/"}
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain
    response.delete_cookie(ACCESS_COOKIE_NAME, **common)
    response.delete_cookie(REFRESH_COOKIE_NAME, **common)


@router.post("/register", summary="Register a new user")
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    result = await service.register(
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        business_name=body.business_name,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, settings, result)
    payload: dict[str, Any] = {
        "user": result["user"],
        "business": result.get("business"),
        "access_token_expires_in_minutes": result["access_token_expires_in_minutes"],
    }
    if "verification_token" in result:
        payload["verification_token"] = result["verification_token"]
    return success(payload)


@router.post("/login", summary="Login with email and password")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    result = await service.login(
        email=body.email,
        password=body.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, settings, result)
    return success(
        {
            "user": result["user"],
            "access_token_expires_in_minutes": result["access_token_expires_in_minutes"],
        }
    )


@router.post("/logout", summary="Revoke current session and clear cookies")
async def logout(
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    await service.logout(session_id=auth.session_id)
    _clear_auth_cookies(response, settings)
    return success({"logged_out": True})


@router.post("/refresh", summary="Rotate refresh token and issue new access token")
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_cookie: Annotated[str | None, Depends(get_refresh_token_from_cookie)] = None,
) -> dict[str, Any]:
    if not refresh_cookie:
        raise UnauthorizedError("Refresh token cookie missing")
    result = await service.refresh(
        raw_refresh_token=refresh_cookie,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, settings, result)
    return success(
        {
            "user": result["user"],
            "access_token_expires_in_minutes": result["access_token_expires_in_minutes"],
        }
    )


@router.get("/me", summary="Current authenticated user and business context", response_model=None)
async def me(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = await service.get_me(user_id=auth.user_id, session=auth.session)
    return success(AuthMeResponse(**payload).model_dump())


@router.post("/verify-email", summary="Verify email with a one-time token")
async def verify_email(
    body: VerifyEmailRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    result = await service.verify_email(raw_token=body.token)
    return success(result)


@router.post("/forgot-password", summary="Request a password-reset token")
async def forgot_password(
    body: ForgotPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    await service.request_password_reset(email=body.email)
    return success({"requested": True})


@router.post("/reset-password", summary="Reset password with a one-time token")
async def reset_password(
    body: ResetPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    await service.reset_password(raw_token=body.token, new_password=body.password)
    return success({"reset": True})
