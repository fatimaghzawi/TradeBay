
from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.shared.utils.datetime import utc_now

logger = get_logger(__name__)

EventHandler = Callable[["DomainEvent"], Awaitable[None]]

@dataclass(frozen=True, slots=True)
class DomainEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utc_now)

                                                 
USER_REGISTERED = "UserRegistered"
SUPPLIER_VERIFIED = "SupplierVerified"
PRODUCT_ACTIVATED = "ProductActivated"
RFQ_PUBLISHED = "RFQPublished"
QUOTATION_ACCEPTED = "QuotationAccepted"
ORDER_CREATED = "OrderCreated"
SHIPMENT_DELIVERED = "ShipmentDelivered"
PAYMENT_COMPLETED = "PaymentCompleted"
SETTLEMENT_APPROVED = "SettlementApproved"
CONVERSATION_STARTED = "ConversationStarted"
NEGOTIATION_STARTED = "NegotiationStarted"
NEGOTIATION_AGREED = "NegotiationAgreed"
SOURCING_REQUEST_COMPLETED = "SourcingRequestCompleted"
SOURCING_CONVERTED_TO_RFQ = "SourcingConvertedToRfq"
BUSINESS_PLAN_GENERATED = "BusinessPlanGenerated"
BUSINESS_PLAN_CONVERTED_TO_SOURCING = "BusinessPlanConvertedToSourcing"

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = list(self._handlers.get(event.name, []))
        logger.info("domain_event_published", event_name=event.name, handlers=len(handlers))
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("domain_event_handler_failed", event_name=event.name)

event_bus = EventBus()
