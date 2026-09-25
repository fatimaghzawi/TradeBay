
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.modules.ai.requirements import ProcurementRequirements, QuantityRequirement


class AnalyzeSourcingRequest(BaseModel):
    business_description: str = Field(min_length=8, max_length=8000)

class ConfirmRequirementsRequest(BaseModel):
    sourcing_request_id: str
    requirements: ProcurementRequirements

class RecommendRequest(BaseModel):
    sourcing_request_id: str
    limit: int = Field(default=20, ge=1, le=40)

class CreateSourcingDraftRequest(BaseModel):
    sourcing_request_id: str

class QuantityRequirementOut(QuantityRequirement):
    pass

class ProcurementRequirementsOut(ProcurementRequirements):
    pass

class AnalyzeSourcingResponse(BaseModel):
    sourcing_request_id: str
    requirements: ProcurementRequirementsOut
    status: str
    clarification: str | None = None

class RecommendationOut(BaseModel):
    id: str
    product_id: str | None = None
    product_name: str | None = None
    product_sku: str | None = None
    category_name: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_verified: bool = False
    moq: int | None = None
    unit: str | None = None
    unit_price: str | None = None
    currency: str | None = None
    primary_image_url: str | None = None
    availability_status: str
    relevance_label: str | None = None
    match_score: float | None = None
    matched_requirements: list[str] = Field(default_factory=list)
    unmatched_requirements: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    signals: dict[str, float] = Field(default_factory=dict)

class SupplierMatchOut(BaseModel):
    supplier_id: str
    supplier_name: str
    verified: bool
    product_count: int
    matched_requirements: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    relevance_label: str | None = None

class RecommendationsResponse(BaseModel):
    sourcing_request_id: str
    status: str
    products: list[RecommendationOut]
    suppliers: list[SupplierMatchOut]
    message: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    loose_match: bool = False

class SourcingRequestOut(BaseModel):
    id: str
    status: str
    original_prompt: str
    requirements: dict[str, Any] | None = None
    ai_summary: str | None = None
    destination: str | None = None
    item_count: int = 0
    recommendation_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None
