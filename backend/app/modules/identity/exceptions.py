"""Identity-domain exceptions."""

from app.core.constants import ErrorCode
from app.core.exceptions import AppError, ConflictError, ForbiddenError, UnauthorizedError


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Email is already registered", details={"field": "email"})


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password", code=ErrorCode.INVALID_CREDENTIALS)


class SessionRevokedError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__("Session has been revoked", code=ErrorCode.SESSION_REVOKED)


class AccountInactiveError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("Account is not active", code=ErrorCode.ACCOUNT_INACTIVE)


class BusinessContextRequiredError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Active business context is required",
            code=ErrorCode.BUSINESS_CONTEXT_REQUIRED,
        )


class PermissionDeniedError(ForbiddenError):
    def __init__(self, resource: str, action: str) -> None:
        super().__init__(
            "Permission denied",
            code=ErrorCode.PERMISSION_DENIED,
            details={"resource": resource, "action": action},
        )


class EmailUnverifiedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Email verification is required before this action",
            code=ErrorCode.EMAIL_UNVERIFIED,
        )


class SellingNotVerifiedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Selling requires a verified supplier profile",
            code=ErrorCode.SELLING_NOT_VERIFIED,
        )


class BusinessInactiveError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("Business account is not active", code=ErrorCode.ACCOUNT_INACTIVE)


class MembershipRequiredError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("No active membership in the selected business", code=ErrorCode.FORBIDDEN)


class LastAdminError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "The last Business Admin cannot be removed or demoted",
            code=ErrorCode.LAST_ADMIN_PROTECTED,
        )


class IdentityError(AppError):
    """Generic identity-domain error."""
