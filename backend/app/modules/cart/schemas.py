
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AddCartItemRequest(BaseModel):
    product_id: str = Field(min_length=24, max_length=24)
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    suggested_unit_price: str | None = Field(default=None, max_length=40)

class UpdateCartItemRequest(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=1_000_000)
    suggested_unit_price: str | None = Field(default=None, max_length=40)

    @field_validator("suggested_unit_price", mode="before")
    @classmethod
    def _empty_price_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

class CheckoutCartRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
                                                                                          
    publish: bool = False

class PlaceCartOrderRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
