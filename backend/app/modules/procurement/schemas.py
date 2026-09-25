
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _reject_float(v: Any) -> Any:
    if isinstance(v, float):
        raise ValueError("Money must be string or int — not float")
    return v

def _parse_money_str(v: Any, *, required: bool) -> str | None:
    v = _reject_float(v)
    if v is None:
        if required:
            raise ValueError("Amount is required")
        return None
    if isinstance(v, bool):
        raise ValueError("Money must be string or int — not bool")
    if isinstance(v, Decimal):
        text = format(v, "f")
    elif isinstance(v, int):
        text = str(v)
    elif isinstance(v, str):
        text = v.strip()
    else:
        raise ValueError("Money must be string or int")
    if not text:
        if required:
            raise ValueError("Amount is required")
        return None
    try:
        Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Invalid money amount") from exc
    return text

class AddressIn(BaseModel):
    street: str | None = None
    city: str | None = None
    district: str | None = None
    governorate: str | None = None
    postal_code: str | None = None
    country: str | None = "Lebanon"

class RFQItemIn(BaseModel):
    product_id: str | None = None
    category_id: str | None = None
    product_name: str = Field(min_length=1, max_length=200)
    sku: str | None = None
    quantity: str
    unit: str = "unit"
    catalog_unit_price: str | None = None
    target_unit_price: str | None = None
    primary_image_url: str | None = Field(default=None, max_length=2048)
    requirements: str | None = None
    notes: str | None = None
    supplier_business_id: str | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v: Any) -> Any:
        return _parse_money_str(v, required=True)

    @field_validator("catalog_unit_price", "target_unit_price", mode="before")
    @classmethod
    def _money_fields(cls, v: Any) -> Any:
        return _parse_money_str(v, required=False)

class CreateRFQRequest(BaseModel):

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    destination: AddressIn | None = None
    required_by: datetime | None = None
    response_deadline: datetime | None = None
    currency: str = "USD"
    notes: str | None = None
    visibility: str = "invited"
    rfq_type: str | None = None
    items: list[RFQItemIn] = Field(min_length=1)
    sourcing_request_id: str | None = None
    business_plan_id: str | None = None

class CreateProductRFQRequest(BaseModel):

    product_id: str = Field(min_length=24, max_length=24)
    quantity: str
    unit: str | None = None
    target_unit_price: str | None = None
    required_by: datetime | None = None
    response_deadline: datetime | None = None
    destination: AddressIn | None = None
    requirements: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=2000)
    currency: str = "USD"
    publish: bool = False

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v: Any) -> Any:
        return _parse_money_str(v, required=True)

    @field_validator("target_unit_price", mode="before")
    @classmethod
    def _target_unit_price(cls, v: Any) -> Any:
        return _parse_money_str(v, required=False)

class CreateSourcingRFQRequest(BaseModel):

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    requirements: str | None = Field(default=None, max_length=8000)
    quantity: str
    unit: str = "unit"
    target_unit_price: str | None = None
    category_id: str | None = None
    product_name: str | None = Field(default=None, max_length=200)
    required_by: datetime | None = None
    response_deadline: datetime | None = None
    destination: AddressIn | None = None
    notes: str | None = Field(default=None, max_length=2000)
    currency: str = "USD"
    visibility: str = "open"
    publish: bool = False
    items: list[RFQItemIn] | None = None
    sourcing_request_id: str | None = None
    business_plan_id: str | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v: Any) -> Any:
        return _parse_money_str(v, required=True)

    @field_validator("target_unit_price", mode="before")
    @classmethod
    def _target_unit_price(cls, v: Any) -> Any:
        return _parse_money_str(v, required=False)

class UpdateRFQRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    destination: AddressIn | None = None
    required_by: datetime | None = None
    response_deadline: datetime | None = None
    currency: str | None = None
    notes: str | None = None
    visibility: str | None = None
    items: list[RFQItemIn] | None = None

class InviteSuppliersRequest(BaseModel):
    supplier_business_ids: list[str] = Field(min_length=1, max_length=50)

class DeclineInviteRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

class ReportIssueRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

class QuotationLineIn(BaseModel):
    rfq_item_id: str
    quantity: str
    unit_price: str
    moq: int | None = None
    lead_time_days: int | None = None
    discount: str = "0"
    tax: str = "0"
    shipping_allocation: str = "0"
    notes: str | None = None

    @field_validator(
        "quantity",
        "unit_price",
        "discount",
        "tax",
        "shipping_allocation",
        mode="before",
    )
    @classmethod
    def _money(cls, v: Any) -> Any:
        return _reject_float(v)

class UpsertQuotationRequest(BaseModel):
    valid_until: datetime | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None
    currency: str = "USD"
    notes: str | None = None
    document_discount: str = "0"
    document_shipping: str = "0"
    document_tax: str = "0"
    lines: list[QuotationLineIn] = Field(min_length=1)

    @field_validator("document_discount", "document_shipping", "document_tax", mode="before")
    @classmethod
    def _doc_money(cls, v: Any) -> Any:
        return _reject_float(v)

class AwardRFQRequest(BaseModel):
    quotation_id: str
    confirm: bool = False

class HandshakeRFQRequest(BaseModel):

    quotation_id: str
    confirm: bool = False

class RejectQuotationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

class IssuePORequest(BaseModel):

    payment_method: str = Field(min_length=1, max_length=120)
    payment_terms: str | None = Field(default=None, max_length=200)
    delivery_terms: str | None = Field(default=None, max_length=200)

class ShipmentLineIn(BaseModel):
    order_item_id: str
    quantity: str

    @field_validator("quantity", mode="before")
    @classmethod
    def _qty(cls, v: Any) -> Any:
        return _reject_float(v)

class CreateShipmentRequest(BaseModel):
    carrier_name: str | None = None
    tracking_number: str | None = None
    origin: str | None = None
    estimated_delivery_at: datetime | None = None
    shipping_notes: str | None = None
    lines: list[ShipmentLineIn] = Field(min_length=1)

class TrackingEventRequest(BaseModel):
    status: str
    description: str | None = None
    location: str | None = None
    occurred_at: datetime | None = None

class DeliveryEvidenceRequest(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=2000)
    note: str | None = None

class ReceivingLineIn(BaseModel):
    order_item_id: str
    received_quantity: str = "0"
    damaged_quantity: str = "0"
    missing_quantity: str = "0"
    rejected_quantity: str = "0"
    notes: str | None = None

    @field_validator(
        "received_quantity",
        "damaged_quantity",
        "missing_quantity",
        "rejected_quantity",
        mode="before",
    )
    @classmethod
    def _qty(cls, v: Any) -> Any:
        return _reject_float(v)

class ReceiveShipmentRequest(BaseModel):
    lines: list[ReceivingLineIn] = Field(min_length=1)
    notes: str | None = None
    complete_order: bool = True
