
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_float(v: Any) -> Any:
    if isinstance(v, float):
        raise ValueError("Money must be string or int — not float")
    return v

class RecordPaymentRequest(BaseModel):
    amount: str
    payment_method: str | None = None
    reference: str | None = Field(default=None, max_length=120)
                                                        
    complete: bool = True

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, v: Any) -> Any:
        return _reject_float(v)

class CreateCreditNoteRequest(BaseModel):
    amount: str
    reason: str = Field(min_length=1, max_length=500)
                                                                                    
    apply: bool = True
    lines: list[dict[str, Any]] | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, v: Any) -> Any:
        return _reject_float(v)

class CreateRefundRequest(BaseModel):
    amount: str
    reason: str | None = Field(default=None, max_length=500)
    credit_note_id: str | None = None
                                                                   
    process: bool = True

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, v: Any) -> Any:
        return _reject_float(v)
