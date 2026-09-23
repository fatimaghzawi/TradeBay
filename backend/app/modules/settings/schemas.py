"""System Settings request schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_float(v: Any) -> Any:
    if isinstance(v, float):
        raise ValueError("Money/rate must be string or int — not float")
    return v


class AddressIn(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    governorate: str | None = None
    country: str | None = "Lebanon"
    postal_code: str | None = None


class UpdatePlatformSettingsRequest(BaseModel):
    platform_name: str | None = Field(default=None, min_length=1, max_length=120)
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    commission_rate: str | None = None
    commission_type: str | None = None
    commission_base: str | None = None
    minimum_order_value: str | None = None
    payment_provider: str | None = Field(default=None, max_length=64)
    payment_provider_active: bool | None = None

    @field_validator("commission_rate", "minimum_order_value", mode="before")
    @classmethod
    def _no_float_money(cls, v: Any) -> Any:
        return _reject_float(v)

    @field_validator("default_currency")
    @classmethod
    def _currency_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class UpdateTaxSettingsRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    rate: str | None = None
    type: str | None = None
    is_active: bool | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    @field_validator("rate", mode="before")
    @classmethod
    def _no_float_rate(cls, v: Any) -> Any:
        return _reject_float(v)


class UpdateBusinessSettingsRequest(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    business_email: str | None = Field(default=None, max_length=200)
    business_phone: str | None = Field(default=None, max_length=40)
    address: AddressIn | None = None
    tax_registration_number: str | None = Field(default=None, max_length=80)
    invoice_prefix: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("business_email")
    @classmethod
    def _email_or_empty(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid business email")
        return v.strip()
