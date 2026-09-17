from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class NegotiationSummary(BaseModel):
    id: str
    conversation_id: str
    status: str
    rfq_id: str | None = None
    quotation_id: str | None = None


class NegotiationOfferSummary(BaseModel):
    id: str
    negotiation_id: str
    parent_offer_id: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    currency: str | None = None
    status: str
    created_at: datetime | None = None
