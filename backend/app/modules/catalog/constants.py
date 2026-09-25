
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

    INITIAL_STOCK = "initial_stock"
    STOCK_RECEIVED = "stock_received"
    RESERVATION = "reservation"
    RESERVATION_RELEASE = "reservation_release"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"

class InventoryReferenceType(StrEnum):

    ORDER = "order"
    SHIPMENT = "shipment"
    MANUAL = "manual"
    PRODUCT = "product"

                                                              
BUYER_VISIBLE_PRODUCT_STATUSES: frozenset[str] = frozenset({ProductStatus.ACTIVE})
