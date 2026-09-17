from pydantic import BaseModel, Field


class SourcingQuery(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    business_account_id: str | None = None


class SourcingResponse(BaseModel):
    answer: str
    disclaimer: str = "Advisory only; does not create or modify RFQs or orders."


class RecommendationQuery(BaseModel):
    product_id: str | None = None
    category_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RecommendationItem(BaseModel):
    product_id: str
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem]
