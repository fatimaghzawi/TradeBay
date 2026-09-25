from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlaceCheckoutRequest(BaseModel):

    model_config = ConfigDict(extra="forbid")

    payment_method: str = Field(pattern="^(cash|card)$")
                                                                                               
    expected_total: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("expected_total", mode="before")
    @classmethod
    def no_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("Send amounts as strings, not floats")
        return value

class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=300)

class ConfirmCashRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=300)
