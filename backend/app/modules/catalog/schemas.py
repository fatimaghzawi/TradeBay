
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.catalog.constants import ProductStatus, ProductUnit


def _reject_float_money(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("Money must be a string or integer — not a float")
    return value

class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    parent_category_id: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True

class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    parent_category_id: str | None = None
    clear_parent: bool = False
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

class CreateProductRequest(BaseModel):
    category_id: str
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    unit: ProductUnit = ProductUnit.UNIT
    origin: str | None = Field(default=None, max_length=120)
    moq: int = Field(default=1, ge=1, description="Minimum order quantity")
    lead_time_days: int = Field(default=0, ge=0)
    status: ProductStatus = ProductStatus.DRAFT
    is_featured: bool = False

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("SKU is required")
        return cleaned

class UpdateProductRequest(BaseModel):
    category_id: str | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    unit: ProductUnit | None = None
    origin: str | None = Field(default=None, max_length=120)
    moq: int | None = Field(default=None, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    status: ProductStatus | None = None
    is_featured: bool | None = None

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("SKU is required")
        return cleaned

class CreatePriceRequest(BaseModel):
    min_quantity: int = Field(ge=1)
    max_quantity: int | None = Field(default=None, ge=1)
    unit_price: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_active: bool = True

    @field_validator("unit_price", mode="before")
    @classmethod
    def no_float_price(cls, value: Any) -> Any:
        return _reject_float_money(value)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def range_ok(self) -> CreatePriceRequest:
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be >= min_quantity")
        return self

class UpdatePriceRequest(BaseModel):
    min_quantity: int | None = Field(default=None, ge=1)
    max_quantity: int | None = Field(default=None, ge=1)
    clear_max_quantity: bool = False
    unit_price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("unit_price", mode="before")
    @classmethod
    def no_float_price(cls, value: Any) -> Any:
        if value is None:
            return None
        return _reject_float_money(value)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

class StockQuantityRequest(BaseModel):
    quantity: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)
    reference_type: str | None = Field(default=None, max_length=40)
    reference_id: str | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def no_float_qty(cls, value: Any) -> Any:
        return _reject_float_money(value)

class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    parent_category_id: str | None = None
    is_active: bool
    display_order: int
    image_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class ProductPricePublic(BaseModel):
    id: str
    product_id: str
    min_quantity: int
    max_quantity: int | None = None
    unit_price: str
    currency: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

class InventoryPublic(BaseModel):
    id: str
    product_id: str
    available_quantity: str
    reserved_quantity: str
    updated_at: datetime | None = None

class InventoryTransactionPublic(BaseModel):
    id: str
    inventory_id: str
    product_id: str
    transaction_type: str
    quantity: str
    reference_type: str | None = None
    reference_id: str | None = None
    previous_available: str
    previous_reserved: str
    new_available: str
    new_reserved: str
    reason: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None

class ProductImagePublic(BaseModel):
    id: str
    product_id: str
    url: str
    alt_text: str | None = None
    is_primary: bool = False
    display_order: int = 0
    created_at: datetime | None = None

class ProductPublic(BaseModel):
    id: str
    supplier_id: str
    business_account_id: str
    supplier_name: str | None = None
    supplier_logo_url: str | None = None
    supplier_city: str | None = None
    supplier_governorate: str | None = None
    supplier_verified: bool = False
    category_id: str
    sku: str
    name: str
    slug: str
    description: str | None = None
    unit: str
    origin: str | None = None
    moq: int
    lead_time_days: int
    status: str
    is_featured: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    inventory: InventoryPublic | None = None
    prices: list[ProductPricePublic] | None = None
    images: list[ProductImagePublic] | None = None
    primary_image_url: str | None = None
