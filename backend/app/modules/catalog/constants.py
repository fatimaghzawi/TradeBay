"""Catalog & inventory domain constants."""

from enum import StrEnum


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductUnit(StrEnum):
    PIECE = "piece"
    BOX = "box"
    CARTON = "carton"
    KG = "kg"
    LITER = "liter"
    UNIT = "unit"


class InventoryTransactionType(StrEnum):
    """Append-only stock movement kinds (ERD). Quantity is always positive."""

    INITIAL_STOCK = "initial_stock"
    STOCK_RECEIVED = "stock_received"
    RESERVATION = "reservation"
    RESERVATION_RELEASE = "reservation_release"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"


class InventoryReferenceType(StrEnum):
    """What caused a stock movement. Manual adjustments may omit reference_id."""

    ORDER = "order"
    SHIPMENT = "shipment"
    MANUAL = "manual"
    PRODUCT = "product"


# Buyers may only see these in the public/marketplace catalog.
BUYER_VISIBLE_PRODUCT_STATUSES: frozenset[str] = frozenset({ProductStatus.ACTIVE})
