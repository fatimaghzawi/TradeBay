
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdaptiveQuestion(BaseModel):
    id: str
    prompt: str
    input_type: Literal["single", "multi", "text", "number"] = "single"
    options: list[str] = Field(default_factory=list)
    why: str | None = None

class AdaptiveAnswers(BaseModel):

    model_config = ConfigDict(extra="allow")

    opportunity_style: str | None = None
    audience: str | None = None
    price_positioning: str | None = None
    electronics_focus: list[str] | None = None
    condition_pref: str | None = None
    food_channel: str | None = None
    channel_pref: str | None = None
    margin_confirm: str | None = None

def read_adaptive(preferences: dict[str, Any]) -> AdaptiveAnswers:
    raw = preferences.get("adaptive") or {}
    if isinstance(raw, AdaptiveAnswers):
        return raw
    if not isinstance(raw, dict):
        return AdaptiveAnswers()
    return AdaptiveAnswers.model_validate(raw)

class PlannerPreferences(BaseModel):
    business_goal: str | None = None
    unsure_goal: bool = False
    location: str | None = None
    budget_range: str | None = None
    budget_min: str | None = None
    budget_max: str | None = None
    inventory_budget: str | None = None
    operating_cash: str | None = None
    business_model: list[str] = Field(default_factory=list)
    experience: str | None = None
    time_commitment: str | None = None
    risk_preference: str | None = None
    desired_monthly_income: str | None = None
    desired_margin: str | None = None
    product_preferences: list[str] = Field(default_factory=list)
    customer_type: str | None = None
    category_hints: list[str] = Field(default_factory=list)
    adaptive: AdaptiveAnswers = Field(default_factory=AdaptiveAnswers)

class CreateSessionRequest(BaseModel):
    pass

class SubmitAnswersRequest(BaseModel):
    step: str = Field(min_length=1, max_length=64)
    answers: dict[str, Any] = Field(default_factory=dict)

class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

class RegeneratePlanRequest(BaseModel):
    preferences: PlannerPreferences | None = None
    reason: str | None = Field(default=None, max_length=500)

class PatchPlanRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    milestone_updates: list[dict[str, Any]] | None = None
    preferences: PlannerPreferences | None = None

                                 

class AIConceptOut(BaseModel):
    name_suggestion: str
    concept: str
    business_model: str
    target_location: str
    target_customer: str
    value_proposition: str
    why_it_fits: str

class AIProductStrategyItem(BaseModel):
    product_id: str | None = None
    category_id: str | None = None
    item_name: str
    priority: Literal["ESSENTIAL", "RECOMMENDED", "OPTIONAL"] = "RECOMMENDED"
    quantity: int = Field(ge=0, le=100000)
    unit: str = "unit"
    estimated_purchase_price: str | None = None
    target_selling_price: str
    suggested_moq: int | None = None
    rationale: str
    source_type: Literal["MARKETPLACE", "AI_ESTIMATE"] = "AI_ESTIMATE"

    @field_validator("estimated_purchase_price", "target_selling_price")
    @classmethod
    def _money_str(cls, v: str | None) -> str | None:
        if v is None:
            return v
                                                                                    
        cleaned = str(v).strip().replace(",", "")
        if not cleaned:
            raise ValueError("empty money")
        float(cleaned)                                                     
        return cleaned

class AIRiskOut(BaseModel):
    title: str
    description: str
    why_it_matters: str
    mitigation: str

class AIMilestoneOut(BaseModel):
    phase: str
    title: str
    description: str
    week: int | None = None
    order: int = 0
    tasks: list[str] = Field(default_factory=list)

class AIAssumptionOut(BaseModel):
    text: str
    label: Literal["AI estimate", "AI projection", "TradeBay data", "User input"] = "AI estimate"

class AIPlanDraft(BaseModel):

    business_concept: AIConceptOut
    product_strategy: list[AIProductStrategyItem] = Field(default_factory=list, max_length=20)
    launch_plan: list[AIMilestoneOut] = Field(default_factory=list, max_length=12)
    risks: list[AIRiskOut] = Field(default_factory=list, max_length=12)
    assumptions: list[AIAssumptionOut] = Field(default_factory=list, max_length=20)
    budget_notes: list[str] = Field(default_factory=list)
