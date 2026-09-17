"""Negotiation document shapes.

ERD §14. A negotiation anchors on the RFQ / quotation, not on a conversation —
attaching a thread is optional discussion and the commercial trail stands without it.
Quotation and Order remain the commercial source of truth; there is no Deal entity.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class NegotiationDocument(MongoDocument):
    """`conversation_id` is optional in both directions and is not unique-required."""

    rfq_id: OptionalDocumentId = None
    quotation_id: OptionalDocumentId = None
    conversation_id: OptionalDocumentId = None
    buyer_business_id: OptionalDocumentId = None
    supplier_business_id: OptionalDocumentId = None
    started_by_user_id: DocumentId
    status: str
    agreed_at: datetime | None = None
    agreed_offer_id: OptionalDocumentId = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NegotiationOfferDocument(MongoDocument):
    """Offer envelope. Line commercials live on `negotiation_offer_items`.

    Header money fields are optional rollups of those lines, not the commercial record.
    `parent_offer_id` gives the offer → counter → counter chain.
    """

    negotiation_id: DocumentId
    created_by_user_id: DocumentId
    created_by_business_id: OptionalDocumentId = None
    parent_offer_id: OptionalDocumentId = None
    quantity: OptionalMoney = None
    unit_price: OptionalMoney = None
    total_price: OptionalMoney = None
    currency: str = "USD"
    delivery_location: str | None = None
    delivery_date: datetime | None = None
    payment_terms: str | None = None
    additional_terms: str | None = None
    status: str
    expires_at: datetime | None = None
    responded_at: datetime | None = None
    created_at: datetime


class NegotiationOfferItemDocument(MongoDocument):
    """One commercial line of an offer. Maps to a specific RFQ / quotation line."""

    offer_id: DocumentId
    negotiation_id: DocumentId
    rfq_item_id: OptionalDocumentId = None
    quotation_item_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    product_name_snapshot: str | None = None
    sku_snapshot: str | None = None
    quantity: Money
    unit: str = "unit"
    unit_price: Money
    discount: Money = Decimal("0")
    line_total: OptionalMoney = None
    lead_time_days: int | None = None
    notes: str | None = None
    created_at: datetime
