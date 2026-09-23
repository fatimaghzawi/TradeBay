"""Identity-domain exceptions (all subclass ``AppError`` / core HTTP errors).

Raised by services; converted to JSON envelopes by ``core/exceptions`` handlers.
"""

from app.core.constants import ErrorCode
from app.core.exceptions import AppError, ConflictError, ForbiddenError, UnauthorizedError

# ── Auth / account ───────────────────────────────────────────────────────────


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Email is already registered", details={"field": "email"})


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password", code=ErrorCode.INVALID_CREDENTIALS)


class InvalidOtpError(UnauthorizedError):
    def __init__(self, *, remaining: int | None = None, max_attempts: int = 5) -> None:
        if remaining is None:
            message = "Invalid verification code"
            details = None
        else:
            message = (
                f"Invalid verification code. {remaining} attempt"
                f"{'s' if remaining != 1 else ''} remaining."
            )
            details = {"remaining_attempts": remaining, "max_attempts": max_attempts}
        super().__init__(message, code=ErrorCode.OTP_INVALID, details=details)


class OtpAttemptsExceededError(UnauthorizedError):
    def __init__(self, *, max_attempts: int = 5) -> None:
        super().__init__(
            "Too many incorrect codes. Request a new code to continue.",
            code=ErrorCode.OTP_ATTEMPTS_EXCEEDED,
            details={"max_attempts": max_attempts},
        )


class SessionRevokedError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__("Session has been revoked", code=ErrorCode.SESSION_REVOKED)


class AccountInactiveError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__("Account is not active", code=ErrorCode.ACCOUNT_INACTIVE        )


# ── Business context / authorization ─────────────────────────────────────────


class BusinessContextRequiredError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Select a company to continue",
            code=ErrorCode.BUSINESS_CONTEXT_REQUIRED,
        )


class PermissionDeniedError(ForbiddenError):
    def __init__(self, resource: str, action: str) -> None:
        super().__init__(
            "You don’t have access to this action",
            code=ErrorCode.PERMISSION_DENIED,
            details={"resource": resource, "action": action},
        )


class EmailUnverifiedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Verify your email before continuing",
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


# ── Invitations / roles / company domain ─────────────────────────────────────


class InvitationInvalidError(ForbiddenError):
    def __init__(self, message: str = "Invitation is not valid") -> None:
        super().__init__(message, code=ErrorCode.INVITATION_INVALID)


class PrivilegeEscalationError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "You can only assign access you already have",
            code=ErrorCode.PRIVILEGE_ESCALATION,
        )


class SystemRoleProtectedError(ConflictError):
    def __init__(self, message: str = "System roles are protected") -> None:
        super().__init__(message)


class BusinessAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "This account already has a business. Only one business is allowed per account.",
            code=ErrorCode.CONFLICT,
        )


class InvitationAlreadyPendingError(ConflictError):
    def __init__(
        self,
        message: str = "This email already has a pending invitation for this business. Open Invitations to resend it.",
        *,
        invitation_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.CONFLICT,
            details={"reason": "already_pending", "invitation_id": invitation_id},
        )


class AlreadyBusinessMemberError(ConflictError):
    def __init__(self, message: str = "This person is already a member of this business") -> None:
        super().__init__(
            message,
            code=ErrorCode.CONFLICT,
            details={"reason": "already_member"},
        )


class VerifiedBusinessLockedError(ForbiddenError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or (
                "Legal identity on a verified supplier cannot be changed. "
                "You can still update phone, description, and other profile details."
            ),
            code=ErrorCode.FORBIDDEN,
        )


class CompanyDomainMismatchError(ForbiddenError):
    def __init__(self, *, company_name: str, company_domain: str) -> None:
        super().__init__(
            (
                f"This email doesn't belong to the {company_name} company domain. "
                f"Team members must use a @{company_domain} email address."
            ),
            code=ErrorCode.COMPANY_DOMAIN_MISMATCH,
            details={
                "reason": "company_domain_mismatch",
                "company_name": company_name,
                "company_domain": company_domain,
            },
        )


class CompanyDomainRequiredError(AppError):
    def __init__(self, message: str = "Company email domain is required") -> None:
        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            message,
            status_code=422,
        )


class CompanyDomainTakenError(ConflictError):
    def __init__(self, domain: str) -> None:
        super().__init__(
            f"The company domain @{domain} is already registered on TradeBay.",
            code=ErrorCode.COMPANY_DOMAIN_TAKEN,
            details={"email_domain": domain},
        )


class IdentityError(AppError):
    """Generic identity-domain error."""
