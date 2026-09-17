from pydantic import BaseModel, Field


class ProductSummary(BaseModel):
    id: str
    name: str
    sku: str
    status: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=100)
    category_id: str
    description: str | None = None
    unit: str = "unit"
    moq: int = Field(default=1, ge=1)
