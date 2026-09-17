"""Identity status and role constants."""

from enum import StrEnum


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
    """ERD: pending | verified | suspended | rejected. `active` is accepted as a legacy alias of verified."""

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

AUTH_TOKEN_MAX_ATTEMPTS = 5
EMAIL_VERIFY_TTL_HOURS = 24
PASSWORD_RESET_TTL_HOURS = 2
INVITATION_TTL_DAYS = 7
CHALLENGE_RATE_LIMIT_MAX = 5
CHALLENGE_RATE_LIMIT_WINDOW_SECONDS = 15 * 60


def is_business_operational(status: str | None) -> bool:
    return status in OPERATIONAL_BUSINESS_STATUSES


class MembershipStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
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


VERIFICATION_TRANSITIONS: dict[str, set[str]] = {
    SupplierVerificationStatus.UNVERIFIED: {SupplierVerificationStatus.PENDING},
    SupplierVerificationStatus.PENDING: {
        SupplierVerificationStatus.VERIFIED,
        SupplierVerificationStatus.REJECTED,
    },
    SupplierVerificationStatus.REJECTED: {SupplierVerificationStatus.PENDING},
    SupplierVerificationStatus.VERIFIED: {SupplierVerificationStatus.REVOKED},
    SupplierVerificationStatus.REVOKED: {SupplierVerificationStatus.PENDING},
}


# System role names seeded per business (is_system_role=True). Grants live in MongoDB.
SYSTEM_ROLE_BUSINESS_ADMIN = "Business Admin"
SYSTEM_ROLE_SALES_MANAGER = "Sales Manager"
SYSTEM_ROLE_SALES_REPRESENTATIVE = "Sales Representative"
SYSTEM_ROLE_FINANCE = "Finance"
SYSTEM_ROLE_VIEWER = "Viewer"
SYSTEM_ROLE_PLATFORM_ADMIN = "Platform Admin"
SYSTEM_ROLE_PLATFORM_OPERATOR = "Platform Operator"
