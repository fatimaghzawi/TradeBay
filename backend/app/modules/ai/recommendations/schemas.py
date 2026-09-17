from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    business_account_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RecommendationItem(BaseModel):
    product_id: str | None = None
    score: float = 0.0
    reason: str = ""
