"""Application constants."""

from enum import StrEnum

API_V1_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"
REFRESH_COOKIE_NAME = "tb_refresh"
ACCESS_COOKIE_NAME = "tb_access"

SENSITIVE_LOG_FIELDS = frozenset(
    {
        "password",
        "password_hash",
        "refresh_token",
        "access_token",
        "token",
        "otp",
        "token_hash",
        "invitation_token",
        "verification_token",
        "secret",
        "jwt",
        "authorization",
        "ai_api_key",
        "secret_key",
        "jwt_secret_key",
    }
)


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ErrorCode(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_READY = "NOT_READY"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    OTP_INVALID = "OTP_INVALID"
    OTP_ATTEMPTS_EXCEEDED = "OTP_ATTEMPTS_EXCEEDED"
    SESSION_REVOKED = "SESSION_REVOKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BUSINESS_CONTEXT_REQUIRED = "BUSINESS_CONTEXT_REQUIRED"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    EMAIL_UNVERIFIED = "EMAIL_UNVERIFIED"
    SELLING_NOT_VERIFIED = "SELLING_NOT_VERIFIED"
    LAST_ADMIN_PROTECTED = "LAST_ADMIN_PROTECTED"
    INVITATION_INVALID = "INVITATION_INVALID"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    COMPANY_DOMAIN_MISMATCH = "COMPANY_DOMAIN_MISMATCH"
    COMPANY_DOMAIN_TAKEN = "COMPANY_DOMAIN_TAKEN"


class PermissionAction(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"
    INVITE = "invite"
    REMOVE = "remove"
    RESPOND = "respond"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    APPROVE = "approve"
    VERIFY = "verify"
    RESOLVE = "resolve"
    ACCEPT = "accept"


class PermissionResource(StrEnum):
    USERS = "users"
    ROLES = "roles"
    SETTINGS = "settings"
    AUDIT_LOGS = "audit_logs"
    BUSINESSES = "businesses"
    PRODUCTS = "products"
    CATEGORIES = "categories"
    INVENTORY = "inventory"
    RFQS = "rfqs"
    QUOTATIONS = "quotations"
    ORDERS = "orders"
    SHIPMENTS = "shipments"
    PAYMENTS = "payments"
    INVOICES = "invoices"
    CREDIT_NOTES = "credit_notes"
    REFUNDS = "refunds"
    COMMISSIONS = "commissions"
    PAYABLES = "payables"
    SETTLEMENTS = "settlements"
    REVIEWS = "reviews"
    DISPUTES = "disputes"
    NOTIFICATIONS = "notifications"
    SUPPLIERS = "suppliers"
    CONVERSATIONS = "conversations"
    MESSAGES = "messages"
    NEGOTIATIONS = "negotiations"
    SOURCING = "sourcing"
    BUSINESS_PLANS = "business_plans"
