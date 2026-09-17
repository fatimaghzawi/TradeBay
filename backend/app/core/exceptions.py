"""Centralized API exceptions and consistent error envelopes."""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import REQUEST_ID_HEADER, ErrorCode
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class BadRequestError(AppError):
    def __init__(self, message: str = "Bad request", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.BAD_REQUEST, message, status_code=400, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", *, code: ErrorCode | str = ErrorCode.UNAUTHORIZED) -> None:
        super().__init__(code, message, status_code=401)


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "Forbidden",
        *,
        code: ErrorCode | str = ErrorCode.FORBIDDEN,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, status_code=403, details=details)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(ErrorCode.RESOURCE_NOT_FOUND, message, status_code=404)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Conflict",
        *,
        code: ErrorCode | str = ErrorCode.CONFLICT,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, status_code=409, details=details)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(ErrorCode.RATE_LIMITED, message, status_code=429)


class NotReadyError(AppError):
    def __init__(self, message: str = "Application is not ready") -> None:
        super().__init__(ErrorCode.NOT_READY, message, status_code=503)


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _request_id_header() -> dict[str, str]:
    request_id = request_id_ctx.get()
    if not request_id:
        return {}
    return {REQUEST_ID_HEADER: request_id}


async def app_error_handler(_: Request, exc: AppError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
        headers=_request_id_header(),
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> ORJSONResponse:
    mapping = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
    }
    code = mapping.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = str(exc.detail) if exc.detail else "Request failed"
    return ORJSONResponse(
        status_code=exc.status_code,
        content=error_body(str(code), message),
        headers=_request_id_header(),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> ORJSONResponse:
    details = {"errors": exc.errors()}
    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(str(ErrorCode.VALIDATION_ERROR), "Validation error", details),
        headers=_request_id_header(),
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> ORJSONResponse:
    logger.exception("unhandled_exception", error_type=type(exc).__name__)
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(str(ErrorCode.INTERNAL_ERROR), "An unexpected error occurred"),
        headers=_request_id_header(),
    )


def register_exception_handlers(app: Any) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
