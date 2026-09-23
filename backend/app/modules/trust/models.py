"""Trust document shapes.

ERD §9. One review per completed order, so a rating always traces back to a real
purchase. Notifications are the platform poking a user — distinct from Communication
messages, which are people talking to each other.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.shared.types.document import MongoDocument, MongoEmbedded
from app.shared.types.ids import DocumentId, OptionalDocumentId


class ReviewDocument(MongoDocument):
    """`order_id` is unique — you cannot review the same purchase twice."""

    order_id: DocumentId
    buyer_business_id: DocumentId
    supplier_business_id: DocumentId
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class DisputeEvidenceEmbedded(MongoEmbedded):
    evidence_type: str
    url: str
    description: str | None = None
    submitted_by_business_id: OptionalDocumentId = None
    submitted_at: datetime | None = None


class DisputeDocument(MongoDocument):
    """Opening a dispute may set the order to `disputed`. Platform staff resolve it."""

    dispute_number: str
    order_id: DocumentId
    opened_by_business_id: DocumentId
    buyer_business_id: DocumentId
    supplier_business_id: DocumentId
    reason: str
    description: str | None = None
    status: str
    resolution: str | None = None
    resolution_notes: str | None = None
    resolved_by: OptionalDocumentId = None
    resolved_at: datetime | None = None
    evidence: list[DisputeEvidenceEmbedded] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NotificationDocument(MongoDocument):
    """In-app only in v1. No templates and no delivery log collection."""

    recipient_user_id: DocumentId
    recipient_business_id: OptionalDocumentId = None
    type: str
    title: str
    message: str | None = None
    reference_type: str | None = None
    reference_id: OptionalDocumentId = None
    cta_path: str | None = None
    is_read: bool = False
    read_at: datetime | None = None
    created_at: datetime
