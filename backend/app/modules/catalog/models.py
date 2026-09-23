"""Catalog document shapes.

ERD §5. `inventories` is current stock; `inventory_transactions` is the history that
explains it. `product_prices` is the live shop window — agreed deal prices live on
quotation and order items, never here.
"""

from __future__ import annotations

from datetime import datetime

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money


class CategoryDocument(MongoDocument):
    name: str
    slug: str
    description: str | None = None
    parent_category_id: OptionalDocumentId = None
    is_active: bool = True
    display_order: int = 0
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductDocument(MongoDocument):
    """SKU is unique per supplier, not globally."""

    supplier_id: DocumentId
    business_account_id: DocumentId
    category_id: DocumentId
    sku: str
    name: str
    slug: str
    description: str | None = None
    unit: str = "unit"
    origin: str | None = None
    moq: int = 1
    lead_time_days: int = 0
    status: str = "draft"
    is_featured: bool = False
    created_at: datetime
    updated_at: datetime


class ProductPriceDocument(MongoDocument):
    """A wholesale quantity tier. Tiers on one product must not overlap."""

    product_id: DocumentId
    min_quantity: int
    max_quantity: int | None = None
    unit_price: Money
    currency: str = "USD"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ProductImageDocument(MongoDocument):
    product_id: DocumentId
    url: str
    alt_text: str | None = None
    is_primary: bool = False
    display_order: int = 0
    created_at: datetime
    deleted_at: datetime | None = None


class InventoryDocument(MongoDocument):
    """Current stock only, 1:1 with product. Never write history here."""

    product_id: DocumentId
    available_quantity: Money
    reserved_quantity: Money
    updated_at: datetime


class InventoryTransactionDocument(MongoDocument):
    """Append-only stock history. Written in the same transaction as the `inventories` update."""

    inventory_id: DocumentId
    product_id: DocumentId
    transaction_type: str
    quantity: Money
    reference_type: str | None = None
    reference_id: OptionalDocumentId = None
    previous_available: Money
    previous_reserved: Money
    new_available: Money
    new_reserved: Money
    reason: str | None = None
    created_by: OptionalDocumentId = None
    created_at: datetime
