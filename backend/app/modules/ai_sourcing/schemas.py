from pydantic import BaseModel, Field


class SourcingRequestSummary(BaseModel):
    id: str
    status: str
    original_prompt: str
    destination: str | None = None


class SourcingRecommendationSummary(BaseModel):
    id: str
    product_id: str | None = None
    business_account_id: str | None = None
    match_score: float | None = None
    reason: str | None = None


class SourcingPromptPlaceholder(BaseModel):
    """Natural-language input shape reserved for later AI implementation."""

    prompt: str = Field(min_length=1, max_length=4000)
    destination: str | None = None
