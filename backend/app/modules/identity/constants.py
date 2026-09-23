"""Identity statuses, TTLs, and system role name constants.

Statuses are stored as these string values in MongoDB (StrEnum).
Prefer importing enums here instead of scattering raw string literals.
"""

from enum import StrEnum

# ── User / company / membership statuses ─────────────────────────────────────


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class BusinessAccountType(StrEnum):
    BUYER = "buyer"
    SUPPLIER = "supplier"
    PLATFORM = "platform"


class BusinessAccountStatus(StrEnum):
    """ERD: pending | verified | suspended | rejected.

    ``active`` is accepted as a legacy alias of verified.
    """

    PENDING = "pending"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REJECTED = "rejected"
    ACTIVE = "active"


OPERATIONAL_BUSINESS_STATUSES: frozenset[str] = frozenset(
    {
        BusinessAccountStatus.VERIFIED,
        BusinessAccountStatus.PENDING,
        BusinessAccountStatus.ACTIVE,
    }
)


def is_business_operational(status: str | None) -> bool:
    """True when the company may participate in trading APIs."""
    return status in OPERATIONAL_BUSINESS_STATUSES


class MembershipStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SupplierVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REVOKED = "revoked"


class AuthTokenPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


# ── Challenge / invitation timing ────────────────────────────────────────────

AUTH_TOKEN_MAX_ATTEMPTS = 5
EMAIL_OTP_LENGTH = 6
EMAIL_VERIFY_TTL_MINUTES = 15
EMAIL_VERIFY_TTL_HOURS = 24  # legacy alias; OTP uses EMAIL_VERIFY_TTL_MINUTES
PASSWORD_RESET_TTL_MINUTES = 15
PASSWORD_RESET_TTL_HOURS = 2  # legacy alias; OTP uses PASSWORD_RESET_TTL_MINUTES
INVITATION_TTL_DAYS = 7
CHALLENGE_RATE_LIMIT_MAX = 5
CHALLENGE_RATE_LIMIT_WINDOW_SECONDS = 15 * 60


# ── Supplier verification ────────────────────────────────────────────────────

VERIFICATION_TRANSITIONS: dict[str, set[str]] = {
    SupplierVerificationStatus.UNVERIFIED: {SupplierVerificationStatus.PENDING},
    SupplierVerificationStatus.PENDING: {
        SupplierVerificationStatus.VERIFIED,
        SupplierVerificationStatus.REJECTED,
        # Supplier may withdraw docs before admin review.
        SupplierVerificationStatus.UNVERIFIED,
    },
    SupplierVerificationStatus.REJECTED: {SupplierVerificationStatus.PENDING},
    SupplierVerificationStatus.VERIFIED: {SupplierVerificationStatus.REVOKED},
    SupplierVerificationStatus.REVOKED: {SupplierVerificationStatus.PENDING},
}

REQUIRED_SUPPLIER_DOCUMENT_TYPES: frozenset[str] = frozenset(
    {
        "commercial_registration",
        "tax_certificate",
        "address_proof",
    }
)


# ── System role display names (seeded; grants live in MongoDB) ────────────────

SYSTEM_ROLE_BUSINESS_ADMIN = "Business Admin"
SYSTEM_ROLE_SALES_MANAGER = "Sales Manager"
SYSTEM_ROLE_SALES_REPRESENTATIVE = "Sales Representative"
SYSTEM_ROLE_FINANCE = "Finance"
SYSTEM_ROLE_VIEWER = "Viewer"
SYSTEM_ROLE_PLATFORM_ADMIN = "Platform Admin"
SYSTEM_ROLE_PLATFORM_OPERATOR = "Platform Operator"
