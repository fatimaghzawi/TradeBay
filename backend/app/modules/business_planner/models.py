"""Business Planner document shapes.

ERD §14. `price_estimates.source_type` records where a number came from, so a figure
averaged from real marketplace prices is never confused with an AI guess.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    # Extended structured plan fields (embedded documents)
    title: str | None = None
    preferences: dict[str, Any] | None = None
    concept: dict[str, Any] | None = None
    budget_allocation: dict[str, Any] | None = None
    financial_projection: dict[str, Any] | None = None
    market_snapshot: dict[str, Any] | None = None
    risks: list[dict[str, Any]] | None = None
    milestones: list[dict[str, Any]] | None = None
    assumptions: list[dict[str, Any]] | None = None
    budget_adjustments: list[str] | None = None
    version: int = 1
    parent_plan_id: OptionalDocumentId = None
    session_id: OptionalDocumentId = None
    progress: dict[str, Any] | None = None


class BusinessPlanItemDocument(MongoDocument):
    """Priority is ESSENTIAL | RECOMMENDED | OPTIONAL."""

    business_plan_id: DocumentId
    category_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    supplier_business_id: OptionalDocumentId = None
    item_name: str
    description: str | None = None
    quantity: Money
    unit: str = "unit"
    priority: str
    estimated_unit_price: OptionalMoney = None
    estimated_total_price: OptionalMoney = None
    target_selling_price: OptionalMoney = None
    estimated_margin: OptionalMoney = None
    suggested_moq: int | None = None
    reason: str | None = None
    source_type: str = "AI_ESTIMATE"
    supplier_name: str | None = None
    category_name: str | None = None
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


class BusinessPlanSessionDocument(MongoDocument):
    user_id: DocumentId
    status: str
    current_step: str
    answers: dict[str, Any]
    preferences: dict[str, Any]
    adaptive_questions: list[dict[str, Any]]
    adaptive_answers: dict[str, Any]
    plan_id: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime


class BusinessPlanMessageDocument(MongoDocument):
    business_plan_id: DocumentId
    user_id: DocumentId
    role: str
    content: str
    plan_mutations: dict[str, Any] | None = None
    created_at: datetime
