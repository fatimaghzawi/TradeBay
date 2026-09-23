"""AI Sourcing document shapes.

ERD §14. Recommendations point at real `products` and `business_accounts` —
the model turns language into structured requirements, and marketplace search
supplies the matches. AI never writes authoritative commercial state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class BusinessProcurementProfileDocument(MongoDocument):
    """Reusable buyer procurement profile — one active profile per business."""

    business_account_id: DocumentId
    business_description: str
    business_type: str | None = None
    location: str | None = None
    product_requirements: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    quantity_requirements: list[dict[str, Any]] = Field(default_factory=list)
    purchase_frequency: str | None = None
    delivery_requirements: str | None = None
    supplier_preferences: list[str] = Field(default_factory=list)
    budget_range: str | None = None
    ai_summary: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SourcingRequestDocument(MongoDocument):
    """`rfq_id` is set only after an explicit buyer conversion to RFQ."""

    buyer_user_id: DocumentId
    buyer_business_id: OptionalDocumentId = None
    original_prompt: str
    destination: str | None = None
    required_date: datetime | None = None
    status: str
    rfq_id: OptionalDocumentId = None
    business_plan_id: OptionalDocumentId = None
    profile_id: OptionalDocumentId = None
    requirements: dict[str, Any] | None = None
    ai_summary: str | None = None
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
    relevance_label: str | None = None
    matched_requirements: list[str] = Field(default_factory=list)
    unmatched_requirements: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    estimated_unit_price: OptionalMoney = None
    estimated_total_price: OptionalMoney = None
    availability_status: str = "UNKNOWN"
    created_at: datetime
