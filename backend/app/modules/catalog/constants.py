from enum import StrEnum


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class InventoryTransactionType(StrEnum):
    ADJUSTMENT = "adjustment"
    RESERVATION = "reservation"
    RESERVATION_RELEASE = "reservation_release"
    SALE = "sale"
    RETURN = "return"


class InventoryReferenceType(StrEnum):
    """What caused a stock movement. Manual adjustments have no reference id."""

    ORDER = "order"
    SHIPMENT = "shipment"
    MANUAL = "manual"
