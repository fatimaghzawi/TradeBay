
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_current_user,
    get_optional_user,
    get_refresh_token_from_cookie,
)
from app.modules.identity.http import client_ip
from app.modules.identity.schemas import (
    AuthMeResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
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
    common: dict[str, Any] = {
        "path": "/",
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": settings.cookie_samesite,
    }
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
        business_type=body.business_type,
        invitation_token=body.invitation_token,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, settings, result)
    payload: dict[str, Any] = {
        "user": result["user"],
        "business": result.get("business"),
        "access_token_expires_in_minutes": result["access_token_expires_in_minutes"],
    }
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
        ip_address=client_ip(request),
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
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    await service.logout(session_id=auth.session_id, user_id=auth.user_id, ip_address=client_ip(request))
    _clear_auth_cookies(response, settings)
    return success({"logged_out": True})

@router.post("/logout-all", summary="Revoke all sessions for the current user")
async def logout_all(
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    result = await service.logout_all(
        user_id=auth.user_id,
        current_session_id=auth.session_id,
        include_current=True,
        ip_address=client_ip(request),
    )
    _clear_auth_cookies(response, settings)
    return success(result)

@router.post("/refresh", summary="Rotate refresh token and issue new access token")
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_cookie: Annotated[str | None, Depends(get_refresh_token_from_cookie)] = None,
) -> dict[str, Any]:
    if not refresh_cookie:
        raise UnauthorizedError()
    result = await service.refresh(
        raw_refresh_token=refresh_cookie,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, settings, result)
    return success(
        {
            "user": result["user"],
            "access_token_expires_in_minutes": result["access_token_expires_in_minutes"],
        }
    )

@router.get(
    "/me",
    summary="Current authenticated user and business context",
    description="Canonical session context. Prefer this over GET /me.",
    response_model=None,
)
async def me(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    payload = await service.get_me(user_id=auth.user_id, session=auth.session)
    return success(AuthMeResponse(**payload).model_dump())

                                                                               

async def _verify_email(
    body: VerifyEmailRequest,
    request: Request,
    service: AuthService,
    auth: AuthContext | None,
) -> dict[str, Any]:
    result = await service.verify_email(
        raw_token=body.token,
        email=str(body.email) if body.email else None,
        user_id=auth.user_id if auth else None,
        ip_address=client_ip(request),
    )
    return success(result)

@router.post("/email/verify", summary="Verify email with a one-time token")
async def verify_email_brd(
    body: VerifyEmailRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
) -> dict[str, Any]:
    return await _verify_email(body, request, service, auth)

@router.post("/verify-email", summary="Verify email (legacy alias)", include_in_schema=False)
async def verify_email_legacy(
    body: VerifyEmailRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
) -> dict[str, Any]:
    return await _verify_email(body, request, service, auth)

@router.post("/email/resend", summary="Resend email verification challenge")
async def resend_email_verification(
    service: Annotated[AuthService, Depends(get_auth_service)],
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
    body: ResendVerificationRequest | None = None,
) -> dict[str, Any]:
    if auth is not None:
        await service.resend_verification(user_id=auth.user_id)
        return success({"requested": True})
    if body and body.email:
        await service.resend_verification_for_email(email=str(body.email))
        return success({"requested": True})
    raise BadRequestError("Enter your email address to get a new code.")

@router.post("/resend-verification", summary="Resend verification (legacy authenticated)", include_in_schema=False)
async def resend_verification_legacy(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    await service.resend_verification(user_id=auth.user_id)
    return success({"requested": True})

                                                                                

@router.post("/forgot-password", summary="Request a password-reset token")
async def forgot_password(
    body: ForgotPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    await service.request_password_reset(email=body.email)
    return success({"requested": True})

async def _reset_password(
    body: ResetPasswordRequest,
    request: Request,
    service: AuthService,
) -> dict[str, Any]:
    await service.reset_password(
        raw_token=body.token,
        email=str(body.email),
        new_password=body.password,
        ip_address=client_ip(request),
    )
    return success({"reset": True})

@router.post("/password/reset", summary="Reset password with a one-time token")
async def reset_password_brd(
    body: ResetPasswordRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await _reset_password(body, request, service)

@router.post("/reset-password", summary="Reset password (legacy alias)", include_in_schema=False)
async def reset_password_legacy(
    body: ResetPasswordRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await _reset_password(body, request, service)

async def _change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    auth: AuthContext,
    service: AuthService,
    settings: Settings,
) -> dict[str, Any]:
    await service.change_password(
        user_id=auth.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
        ip_address=client_ip(request),
    )
    _clear_auth_cookies(response, settings)
    return success({"changed": True})

@router.post("/password/change", summary="Change password while authenticated")
async def change_password_brd(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _change_password(body, request, response, auth, service, settings)

@router.post("/change-password", summary="Change password (legacy alias)", include_in_schema=False)
async def change_password_legacy(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _change_password(body, request, response, auth, service, settings)
