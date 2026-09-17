"""Identity document shapes (MongoDB-oriented).

ERD §4. A person (`users`) logs in; a company (`business_accounts`) trades. The two
are connected only through `business_memberships`, so one person can act for several
companies under a different role in each.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.shared.types.address import AddressEmbedded
from app.shared.types.document import MongoDocument, MongoEmbedded
from app.shared.types.ids import DocumentId, OptionalDocumentId

# Retained for callers that imported the old local base.
MongoModel = MongoEmbedded

__all__ = [
    "AddressEmbedded",
    "AuditLogDocument",
    "AuthTokenDocument",
    "BusinessAccountDocument",
    "InvitationDocument",
    "MembershipDocument",
    "MongoModel",
    "PermissionDocument",
    "RoleDocument",
    "RolePermissionDocument",
    "SessionDocument",
    "SupplierDocumentEmbedded",
    "SupplierProfileDocument",
    "SupplierRatingSummaryEmbedded",
    "UserDocument",
]


class UserDocument(MongoDocument):
    email: EmailStr
    password_hash: str
    first_name: str
    last_name: str
    phone: str | None = None
    status: str
    email_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BusinessAccountDocument(MongoDocument):
    name: str
    type: str
    status: str
    legal_name: str | None = None
    tax_number: str | None = None
    address: AddressEmbedded | None = None
    created_at: datetime
    updated_at: datetime


class MembershipDocument(MongoDocument):
    """Unique on (user_id, business_account_id) — one membership per person per company."""

    user_id: DocumentId
    business_account_id: DocumentId
    role_id: DocumentId
    status: str
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RoleDocument(MongoDocument):
    """Roles belong to one business. System roles are seeded per company and cannot be deleted."""

    business_account_id: DocumentId
    name: str
    description: str | None = None
    is_system_role: bool = False
    created_at: datetime
    updated_at: datetime


class PermissionDocument(MongoDocument):
    """Global atomic grant, unique on (resource, action). Never assigned to a user directly."""

    resource: str
    action: str
    description: str | None = None


class RolePermissionDocument(MongoDocument):
    role_id: DocumentId
    permission_id: DocumentId
    created_at: datetime


class InvitationDocument(MongoDocument):
    """Carries a role, never permissions — grants always resolve through the role."""

    business_account_id: DocumentId
    invited_email: EmailStr
    role_id: DocumentId
    invited_by_user_id: DocumentId
    token_hash: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class SessionDocument(MongoDocument):
    user_id: DocumentId
    active_business_account_id: OptionalDocumentId = None
    refresh_token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AuthTokenDocument(MongoDocument):
    """Hashed one-time token for email verification or password reset."""

    user_id: DocumentId
    purpose: str
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime


class AuditLogDocument(MongoDocument):
    business_account_id: OptionalDocumentId = None
    user_id: OptionalDocumentId = None
    action: str
    resource_type: str
    resource_id: OptionalDocumentId = None
    metadata: dict[str, object] = Field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime


class SupplierDocumentEmbedded(MongoEmbedded):
    """Verification paperwork. Replaces a separate `verification_cases` collection."""

    document_type: str
    url: str
    file_name: str | None = None
    uploaded_at: datetime | None = None
    verified_at: datetime | None = None


class SupplierRatingSummaryEmbedded(MongoEmbedded):
    """Cached rollup of published reviews. Recomputed from `reviews`, never authoritative."""

    average_rating: float = 0.0
    review_count: int = 0
    last_reviewed_at: datetime | None = None


class SupplierProfileDocument(MongoDocument):
    """One per trading company. Selling requires verification_status = verified."""

    business_account_id: DocumentId
    verification_status: str
    documents: list[SupplierDocumentEmbedded] = Field(default_factory=list)
    service_areas: list[str] = Field(default_factory=list)
    rating_summary: SupplierRatingSummaryEmbedded = Field(
        default_factory=SupplierRatingSummaryEmbedded
    )
    verified_at: datetime | None = None
    verified_by: OptionalDocumentId = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
