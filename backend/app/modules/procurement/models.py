"""Procurement document shapes — the commercial spine.

ERD §6. `orders` *is* the Purchase Order; there is no second order collection. Once a
quotation is accepted the commercial terms are copied onto `order_items` and frozen
there, so later catalog edits can never rewrite an agreed price.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.shared.types.address import AddressEmbedded
from app.shared.types.document import MongoDocument, MongoEmbedded
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class SupplierInviteEmbedded(MongoEmbedded):
    """A supplier the buyer asked directly, as opposed to an openly published RFQ."""

    supplier_business_id: DocumentId
    invited_by_user_id: OptionalDocumentId = None
    invited_at: datetime
    viewed_at: datetime | None = None
    responded_at: datetime | None = None
    declined_at: datetime | None = None
    decline_reason: str | None = None
    status: str = "invited"


class RFQDocument(MongoDocument):
    rfq_number: str
    buyer_business_id: DocumentId
    created_by_user_id: DocumentId
    rfq_type: str = "sourcing"
    title: str
    description: str | None = None
    destination: AddressEmbedded | None = None
    required_by: datetime | None = None
    response_deadline: datetime | None = None
    currency: str = "USD"
    notes: str | None = None
    status: str
    visibility: str = "open"
    # Product RFQ only — supplier is derived from product ownership, never trusted from client.
    product_id: OptionalDocumentId = None
    supplier_business_id: OptionalDocumentId = None
    supplier_invites: list[SupplierInviteEmbedded] = Field(default_factory=list)
    sourcing_request_id: OptionalDocumentId = None
    business_plan_id: OptionalDocumentId = None
    awarded_quotation_id: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime


class RFQItemDocument(MongoDocument):
    """`product_id` is optional — a buyer may ask for something nobody has listed yet."""

    rfq_id: DocumentId
    product_id: OptionalDocumentId = None
    category_id: OptionalDocumentId = None
    product_name: str
    sku: str | None = None
    quantity: Money
    unit: str = "unit"
    catalog_unit_price: OptionalMoney = None
    target_unit_price: OptionalMoney = None
    primary_image_url: str | None = None
    requirements: str | None = None
    notes: str | None = None
    sort_order: int = 0


class QuotationDocument(MongoDocument):
    """One document per supplier per RFQ. Line history is `quotation_items.version`."""

    quotation_number: str
    rfq_id: DocumentId
    supplier_id: DocumentId
    buyer_business_id: DocumentId
    created_by_user_id: OptionalDocumentId = None
    status: str
    valid_until: datetime | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None
    currency: str = "USD"
    subtotal: Money
    discount_total: Money
    charge_total: Money
    tax_total: Money
    total: Money
    notes: str | None = None
    current_version: int = 1
    submitted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class QuotationItemDocument(MongoDocument):
    """One line of one quotation version. Unique on (quotation_id, rfq_item_id, version)."""

    quotation_id: DocumentId
    rfq_item_id: DocumentId
    version: int = 1
    product_id: OptionalDocumentId = None
    product_name_snapshot: str | None = None
    sku_snapshot: str | None = None
    quantity: Money
    unit: str = "unit"
    unit_price: Money
    moq: int | None = None
    lead_time_days: int | None = None
    discount: Money = Decimal("0")
    tax: Money = Decimal("0")
    shipping_allocation: Money = Decimal("0")
    line_total: Money
    notes: str | None = None


class OrderStatusHistoryEmbedded(MongoEmbedded):
    status: str
    changed_by_user_id: OptionalDocumentId = None
    note: str | None = None
    changed_at: datetime


class OrderDocument(MongoDocument):
    """The Purchase Order. Invoices, shipments, commission and disputes all hang off this row."""

    order_number: str
    buyer_business_id: DocumentId
    supplier_business_id: DocumentId
    rfq_id: DocumentId
    quotation_id: DocumentId
    status: str
    currency: str = "USD"
    subtotal: Money
    discount_total: Money
    charge_total: Money
    tax_total: Money
    total: Money
    tax_rate_snapshot: OptionalMoney = None
    tax_name_snapshot: str | None = None
    shipping_address: AddressEmbedded | None = None
    billing_address: AddressEmbedded | None = None
    payment_terms: str | None = None
    payment_method: str | None = None
    delivery_terms: str | None = None
    payment_status: str = "unpaid"
    status_history: list[OrderStatusHistoryEmbedded] = Field(default_factory=list)
    rejection_reason: str | None = None
    confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OrderItemDocument(MongoDocument):
    """Frozen commercial line. The `_snapshot` fields are deliberate copies, not joins."""

    order_id: DocumentId
    quotation_item_id: OptionalDocumentId = None
    rfq_item_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    product_name_snapshot: str
    sku_snapshot: str | None = None
    quantity: Money
    unit: str = "unit"
    unit_price: Money
    discount_snapshot: Money = Decimal("0")
    tax_snapshot: Money = Decimal("0")
    subtotal: Money
    line_total: Money
    shipped_quantity: Money = Decimal("0")
    received_quantity: Money = Decimal("0")
    damaged_quantity: Money = Decimal("0")
    missing_quantity: Money = Decimal("0")
    rejected_quantity: Money = Decimal("0")


class TrackingEventEmbedded(MongoEmbedded):
    status: str
    description: str | None = None
    location: str | None = None
    source: str = "manual"
    occurred_at: datetime
    metadata: dict | None = None


class DeliveryEvidenceEmbedded(MongoEmbedded):
    evidence_type: str
    url: str
    note: str | None = None
    uploaded_by_user_id: OptionalDocumentId = None
    captured_at: datetime | None = None


class ReceivingLineEmbedded(MongoEmbedded):
    order_item_id: DocumentId
    received_quantity: Money = Decimal("0")
    damaged_quantity: Money = Decimal("0")
    missing_quantity: Money = Decimal("0")
    rejected_quantity: Money = Decimal("0")
    notes: str | None = None


class ShipmentDocument(MongoDocument):
    """Fulfilment after the PO, not a second order. One order may have several shipments."""

    shipment_number: str
    order_id: DocumentId
    supplier_business_id: OptionalDocumentId = None
    buyer_business_id: OptionalDocumentId = None
    status: str
    carrier_name: str | None = None
    tracking_number: str | None = None
    origin: str | None = None
    shipping_address: AddressEmbedded | None = None
    estimated_delivery_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    shipping_notes: str | None = None
    tracking_events: list[TrackingEventEmbedded] = Field(default_factory=list)
    delivery_evidence: list[DeliveryEvidenceEmbedded] = Field(default_factory=list)
    receiving: list[ReceivingLineEmbedded] = Field(default_factory=list)
    received_at: datetime | None = None
    receiving_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ShipmentItemDocument(MongoDocument):
    """Which PO lines (and quantities) are in this shipment."""

    shipment_id: DocumentId
    order_id: DocumentId
    order_item_id: DocumentId
    product_id: OptionalDocumentId = None
    product_name_snapshot: str
    sku_snapshot: str | None = None
    quantity: Money
    unit: str = "unit"
    created_at: datetime
