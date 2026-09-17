from decimal import Decimal

from pydantic import BaseModel, Field


class BusinessPlanSummary(BaseModel):
    id: str
    business_type: str
    business_name: str | None = None
    status: str
    estimated_total_cost: Decimal | None = None


class BusinessPlanItemSummary(BaseModel):
    id: str
    item_name: str
    priority: str
    quantity: Decimal | None = None


class BusinessPlanCreatePlaceholder(BaseModel):
    """Input reserved for later planner AI — not executed now."""

    business_type: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    ai_prompt: str | None = Field(default=None, max_length=4000)
