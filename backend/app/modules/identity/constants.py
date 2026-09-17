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
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


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
    EMAIL_VERIFY = "email_verify"
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
