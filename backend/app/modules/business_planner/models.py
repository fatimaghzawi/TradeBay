"""Business Planner document shapes.

ERD §14. `price_estimates.source_type` records where a number came from, so a figure
averaged from real marketplace prices is never confused with an AI guess.
"""

from __future__ import annotations

from datetime import datetime

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class BusinessPlanDocument(MongoDocument):
    user_id: DocumentId
    business_account_id: OptionalDocumentId = None
    business_type: str
    business_name: str | None = None
    description: str | None = None
    location: str | None = None
    currency: str = "USD"
    budget: OptionalMoney = None
    status: str
    ai_prompt: str | None = None
    estimated_total_cost: OptionalMoney = None
    sourcing_request_id: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime


class BusinessPlanItemDocument(MongoDocument):
    """Priority is ESSENTIAL | RECOMMENDED | OPTIONAL."""

    business_plan_id: DocumentId
    category_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    item_name: str
    description: str | None = None
    quantity: Money
    unit: str = "unit"
    priority: str
    estimated_unit_price: OptionalMoney = None
    estimated_total_price: OptionalMoney = None
    reason: str | None = None
    created_at: datetime


class PriceEstimateDocument(MongoDocument):
    """Derived from marketplace prices where possible, falling back to an AI estimate."""

    business_plan_item_id: DocumentId
    source_type: str
    sample_count: int = 0
    min_price: OptionalMoney = None
    average_price: OptionalMoney = None
    max_price: OptionalMoney = None
    currency: str = "USD"
    calculated_at: datetime
