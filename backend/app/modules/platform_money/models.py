"""Platform money document shapes.

ERD §8. Customer finance asks what the buyer owes; this module asks where the cash went
once it moved through TradeBay. `platform_transactions` is the append-only routing
ledger — held, released, paid and refunded positions are summed from it, never stored.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.shared.types.document import MongoDocument
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money


class CommissionRecordDocument(MongoDocument):
    """The PlatformFee. Rate and base are copied from settings at order confirm and frozen."""

    order_id: DocumentId
    supplier_business_id: DocumentId
    payment_id: OptionalDocumentId = None
    base_amount: Money
    rate: Money
    commission_base: str
    commission_amount: Money
    currency: str = "USD"
    status: str
    recognized_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SupplierPayableDocument(MongoDocument):
    """What TradeBay owes the supplier. This is the AP document — there is no `supplier_bills`."""

    payable_number: str
    supplier_business_id: DocumentId
    order_id: DocumentId
    commission_record_id: OptionalDocumentId = None
    gross_amount: Money
    commission_amount: Money
    adjustment_amount: Money = Decimal("0")
    net_payable_amount: Money
    currency: str = "USD"
    status: str
    created_at: datetime
    updated_at: datetime


class SupplierPayoutDocument(MongoDocument):
    """What TradeBay actually sent. A payable is settled only once its payout completes."""

    payout_number: str
    settlement_batch_id: OptionalDocumentId = None
    supplier_business_id: DocumentId
    supplier_payable_id: DocumentId
    gross_amount: Money
    platform_fee_amount: Money
    adjustment_amount: Money = Decimal("0")
    net_amount: Money
    currency: str = "USD"
    status: str
    provider: str | None = None
    provider_transaction_id: str | None = None
    provider_event_id: str | None = None
    idempotency_key: str | None = None
    failure_reason: str | None = None
    processing_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SettlementBatchDocument(MongoDocument):
    """Admin grouping of payouts for one approval. A convenience, not a money concept."""

    batch_number: str
    status: str
    settlement_date: datetime | None = None
    total_gross_amount: Money
    total_commission: Money
    total_adjustments: Money = Decimal("0")
    total_net_amount: Money
    approved_by: OptionalDocumentId = None
    approved_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PlatformTransactionDocument(MongoDocument):
    """Append-only routing ledger.

    `funds_state` is TradeBay's internal money lifecycle, not legal escrow — the payment
    provider holds the regulated funds. `idempotency_key` is `{source}:{event_id}:{type}`
    so one provider event can post several row types without colliding with itself.
    """

    transaction_number: str
    type: str
    amount: Money
    currency: str = "USD"
    funds_state: str
    reference_type: str
    reference_id: DocumentId
    order_id: OptionalDocumentId = None
    payment_id: OptionalDocumentId = None
    supplier_business_id: OptionalDocumentId = None
    status: str
    idempotency_key: str | None = None
    provider: str | None = None
    provider_transaction_id: str | None = None
    provider_event_id: str | None = None
    reverses_transaction_id: OptionalDocumentId = None
    description: str | None = None
    posted_at: datetime
    created_at: datetime
