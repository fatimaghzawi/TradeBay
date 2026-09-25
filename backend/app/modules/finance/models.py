
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.shared.types.document import MongoDocument, MongoEmbedded
from app.shared.types.ids import DocumentId, OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class InvoiceLineEmbedded(MongoEmbedded):

    order_item_id: OptionalDocumentId = None
    product_id: OptionalDocumentId = None
    description: str
    quantity: Money
    unit: str = "unit"
    unit_price: Money
    discount_snapshot: Money = Decimal("0")
    tax_snapshot: Money = Decimal("0")
    line_total: Money

class CustomerInvoiceDocument(MongoDocument):

    invoice_number: str
    order_id: DocumentId
    buyer_business_id: DocumentId
    status: str
    currency: str = "USD"
    issued_at: datetime | None = None
    due_at: datetime | None = None
    tax_rate: OptionalMoney = None
    tax_name_snapshot: str | None = None
    lines: list[InvoiceLineEmbedded] = Field(default_factory=list)
    subtotal: Money
    discount_total: Money
    charge_total: Money
    tax_total: Money
    total: Money
    created_at: datetime
    updated_at: datetime

class PaymentAllocationEmbedded(MongoEmbedded):

    invoice_id: DocumentId
    allocated_amount: Money
    allocated_at: datetime

class PaymentDocument(MongoDocument):

    payment_reference: str
    idempotency_key: str | None = None
    payer_business_id: DocumentId
    amount: Money
    currency: str = "USD"
    payment_method: str | None = None
    status: str
    provider: str | None = None
    provider_transaction_id: str | None = None
    provider_event_id: str | None = None
    allocations: list[PaymentAllocationEmbedded] = Field(default_factory=list)
    receipt_number: str | None = None
    receipt_document_url: str | None = None
    receipt_issued_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

class CreditNoteLineEmbedded(MongoEmbedded):
    description: str
    quantity: OptionalMoney = None
    unit_price: OptionalMoney = None
    line_total: Money

class CreditNoteDocument(MongoDocument):

    credit_note_number: str
    invoice_id: DocumentId
    buyer_business_id: DocumentId
    order_id: OptionalDocumentId = None
    reason: str
    amount: Money
    currency: str = "USD"
    status: str
    lines: list[CreditNoteLineEmbedded] = Field(default_factory=list)
    issued_at: datetime | None = None
    applied_at: datetime | None = None
    created_by: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime

class RefundDocument(MongoDocument):

    refund_number: str
    payment_id: DocumentId
    credit_note_id: OptionalDocumentId = None
    invoice_id: OptionalDocumentId = None
    buyer_business_id: DocumentId
    order_id: OptionalDocumentId = None
    amount: Money
    currency: str = "USD"
    reason: str | None = None
    status: str
    refund_reference: str | None = None
    processed_at: datetime | None = None
    created_by: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime

class FinancialTransactionDocument(MongoDocument):

    transaction_number: str
    business_account_id: DocumentId
    order_id: OptionalDocumentId = None
    invoice_id: OptionalDocumentId = None
    source_type: str
    source_id: DocumentId
    transaction_type: str
    direction: str
    amount: Money
    currency: str = "USD"
    status: str
    reverses_transaction_id: OptionalDocumentId = None
    description: str | None = None
    posted_at: datetime
    created_by: OptionalDocumentId = None
    created_at: datetime
