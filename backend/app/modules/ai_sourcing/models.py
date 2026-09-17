"""AI Sourcing document shapes.

ERD §14. Recommendations point at real `products` and `business_accounts` — the model
turns language into structured requirements, and the marketplace search supplies the
matches. AI never writes to authoritative commercial state.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class SourcingRequestDocument(MongoDocument):
    """`rfq_id` is set on conversion; the RFQ then owns the commercial flow."""

    buyer_user_id: DocumentId
    buyer_business_id: OptionalDocumentId = None
    original_prompt: str
    destination: str | None = None
    required_date: datetime | None = None
    status: str
    rfq_id: OptionalDocumentId = None
    business_plan_id: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime


class SourcingRequestItemDocument(MongoDocument):
    """One structured requirement extracted from the prompt."""

    sourcing_request_id: DocumentId
    product_id: OptionalDocumentId = None
    category_id: OptionalDocumentId = None
    requested_name: str
    description: str | None = None
    quantity: Money
    unit: str = "unit"
    budget_min: OptionalMoney = None
    budget_max: OptionalMoney = None
    required_date: datetime | None = None
    destination: str | None = None
    created_at: datetime


class SourcingRecommendationDocument(MongoDocument):
    """A suggestion only. Persisted so rendering never re-runs the provider."""

    sourcing_request_id: DocumentId
    sourcing_request_item_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    business_account_id: OptionalDocumentId = None
    reason: str | None = None
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    estimated_unit_price: OptionalMoney = None
    estimated_total_price: OptionalMoney = None
    availability_status: str = "UNKNOWN"
    created_at: datetime
