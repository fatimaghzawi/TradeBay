from pydantic import BaseModel, Field


class SourcingRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    business_account_id: str | None = None


class SourcingSuggestion(BaseModel):
    summary: str
    suggested_product_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
