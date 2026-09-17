from enum import StrEnum


class RFQVisibility(StrEnum):
    OPEN = "open"
    INVITED = "invited"


class RFQStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RESPONDING = "responding"
    NEGOTIATING = "negotiating"
    AWARDED = "awarded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class QuotationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class ShipmentStatus(StrEnum):
    PENDING = "pending"
    PREPARING = "preparing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"


class OrderPaymentStatus(StrEnum):
    """Denormalized AR rollup on the order. Authoritative outstanding is the ledger."""

    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    REFUNDED = "refunded"


# Controlled state-transition maps (enforcement deferred)
RFQ_TRANSITIONS: dict[str, set[str]] = {
    RFQStatus.DRAFT: {RFQStatus.PUBLISHED, RFQStatus.CANCELLED},
    RFQStatus.PUBLISHED: {
        RFQStatus.RESPONDING,
        RFQStatus.AWARDED,
        RFQStatus.CANCELLED,
        RFQStatus.EXPIRED,
    },
    RFQStatus.RESPONDING: {
        RFQStatus.NEGOTIATING,
        RFQStatus.AWARDED,
        RFQStatus.CANCELLED,
        RFQStatus.EXPIRED,
    },
    RFQStatus.NEGOTIATING: {RFQStatus.AWARDED, RFQStatus.CANCELLED, RFQStatus.EXPIRED},
}

QUOTATION_TRANSITIONS: dict[str, set[str]] = {
    QuotationStatus.DRAFT: {QuotationStatus.SUBMITTED, QuotationStatus.WITHDRAWN},
    QuotationStatus.SUBMITTED: {
        QuotationStatus.NEGOTIATING,
        QuotationStatus.ACCEPTED,
        QuotationStatus.REJECTED,
        QuotationStatus.EXPIRED,
        QuotationStatus.WITHDRAWN,
    },
    QuotationStatus.NEGOTIATING: {
        QuotationStatus.ACCEPTED,
        QuotationStatus.REJECTED,
        QuotationStatus.EXPIRED,
        QuotationStatus.WITHDRAWN,
    },
}

ORDER_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.DISPUTED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED, OrderStatus.DISPUTED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.DISPUTED},
    OrderStatus.DELIVERED: {OrderStatus.COMPLETED, OrderStatus.DISPUTED},
    OrderStatus.DISPUTED: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
}

SHIPMENT_TRANSITIONS: dict[str, set[str]] = {
    ShipmentStatus.PENDING: {ShipmentStatus.PREPARING, ShipmentStatus.FAILED},
    ShipmentStatus.PREPARING: {ShipmentStatus.SHIPPED, ShipmentStatus.FAILED},
    ShipmentStatus.SHIPPED: {
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.DELIVERED,
        ShipmentStatus.FAILED,
    },
    ShipmentStatus.IN_TRANSIT: {
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.DELIVERED,
        ShipmentStatus.FAILED,
    },
    ShipmentStatus.OUT_FOR_DELIVERY: {ShipmentStatus.DELIVERED, ShipmentStatus.FAILED},
}


# Aliases used by scaffolded service modules
RFQ_STATUS_TRANSITIONS = RFQ_TRANSITIONS
ORDER_STATUS_TRANSITIONS = ORDER_TRANSITIONS
QUOTATION_STATUS_TRANSITIONS = QUOTATION_TRANSITIONS
SHIPMENT_STATUS_TRANSITIONS = SHIPMENT_TRANSITIONS
