
from __future__ import annotations

from pydantic import BaseModel, Field


class QuantityRequirement(BaseModel):
    product: str = Field(min_length=1, max_length=200)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=40)

class ProcurementRequirements(BaseModel):

    business_type: str | None = Field(default=None, max_length=120)
    business_description: str = Field(min_length=1, max_length=8000)
    location: str | None = Field(default=None, max_length=200)
    product_requirements: list[str] = Field(default_factory=list, max_length=40)
    categories: list[str] = Field(default_factory=list, max_length=40)
    quantities: list[QuantityRequirement] = Field(default_factory=list, max_length=40)
    purchase_frequency: str | None = Field(default=None, max_length=80)
    delivery_requirements: str | None = Field(default=None, max_length=400)
    supplier_preferences: list[str] = Field(default_factory=list, max_length=20)
    budget_range: str | None = Field(default=None, max_length=120)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
