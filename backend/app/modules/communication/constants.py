from enum import StrEnum


class ConversationType(StrEnum):
    """Messaging is general-purpose. A commercial context is optional, never required."""

    DIRECT = "DIRECT"
    RFQ = "RFQ"
    QUOTATION = "QUOTATION"
    NEGOTIATION = "NEGOTIATION"
    ORDER = "ORDER"
    DISPUTE = "DISPUTE"
    PRODUCT_INQUIRY = "PRODUCT_INQUIRY"
    SUPPORT = "SUPPORT"


class ConversationContextType(StrEnum):
    """Null for DIRECT and SUPPORT threads, which carry no commercial document."""

    RFQ = "rfq"
    QUOTATION = "quotation"
    NEGOTIATION = "negotiation"
    ORDER = "order"
    DISPUTE = "dispute"
    PRODUCT = "product"


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class ParticipantRole(StrEnum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    OBSERVER = "OBSERVER"


class MessageType(StrEnum):
    TEXT = "TEXT"
    ATTACHMENT = "ATTACHMENT"
    REFERENCE = "REFERENCE"
    SYSTEM = "SYSTEM"


class MessageReferenceType(StrEnum):
    """A REFERENCE message deep-links a commercial document. It never carries its terms."""

    QUOTATION = "quotation"
    QUOTATION_VERSION = "quotation_version"
    NEGOTIATION_OFFER = "negotiation_offer"
    ORDER = "order"
    CUSTOMER_INVOICE = "customer_invoice"
    SHIPMENT = "shipment"
    PRODUCT = "product"


class SystemEvent(StrEnum):
    """Platform-authored timeline entries. No sender, never edited or deleted."""

    QUOTE_RECEIVED = "QUOTE_RECEIVED"
    QUOTE_ACCEPTED = "QUOTE_ACCEPTED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    SHIPMENT_UPDATED = "SHIPMENT_UPDATED"
    INVOICE_ISSUED = "INVOICE_ISSUED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    DISPUTE_OPENED = "DISPUTE_OPENED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"


# DIRECT and SUPPORT do not require a commercial document to open a thread.
# Context on those types is optional metadata (latest RFQ/order), never a new chat.
CONTEXTLESS_CONVERSATION_TYPES: frozenset[str] = frozenset(
    {ConversationType.DIRECT, ConversationType.SUPPORT}
)
