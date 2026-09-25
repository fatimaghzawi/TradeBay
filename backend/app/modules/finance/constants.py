from enum import StrEnum


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"
    CREDITED = "credited"

class PaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"

class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    MANUAL = "manual"

class PaymentProvider(StrEnum):
    STRIPE = "stripe"
    CASH = "cash"
    MANUAL = "manual"

class CreditNoteStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    CANCELLED = "cancelled"

class RefundStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"

class LedgerStatus(StrEnum):

    POSTED = "posted"
    REVERSED = "reversed"

class LedgerSourceType(StrEnum):
    CUSTOMER_INVOICE = "customer_invoice"
    PAYMENT = "payment"
    CREDIT_NOTE = "credit_note"
    REFUND = "refund"

class LedgerTransactionType(StrEnum):
    INVOICE_ISSUED = "invoice_issued"
    PAYMENT_RECEIVED = "payment_received"
    CREDIT_APPLIED = "credit_applied"
    REFUND_PROCESSED = "refund_processed"
    REVERSAL = "reversal"

class LedgerDirection(StrEnum):

    DEBIT = "debit"
    CREDIT = "credit"

                                                                                               
LEDGER_POSTING_DIRECTION: dict[str, str] = {
    LedgerTransactionType.INVOICE_ISSUED: LedgerDirection.DEBIT,
    LedgerTransactionType.PAYMENT_RECEIVED: LedgerDirection.CREDIT,
    LedgerTransactionType.CREDIT_APPLIED: LedgerDirection.CREDIT,
    LedgerTransactionType.REFUND_PROCESSED: LedgerDirection.DEBIT,
}

                                                                        
INVOICE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.VOID},
    InvoiceStatus.ISSUED: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.VOID,
        InvoiceStatus.CREDITED,
    },
    InvoiceStatus.PARTIALLY_PAID: {
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.VOID,
        InvoiceStatus.CREDITED,
    },
    InvoiceStatus.OVERDUE: {InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID, InvoiceStatus.CREDITED},
}

PAYMENT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatus.PENDING: {PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.CANCELLED},
                                                                                           
    PaymentStatus.FAILED: {PaymentStatus.PENDING, PaymentStatus.COMPLETED, PaymentStatus.CANCELLED},
    PaymentStatus.COMPLETED: {PaymentStatus.REVERSED},
}

CREDIT_NOTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CreditNoteStatus.DRAFT: {CreditNoteStatus.ISSUED, CreditNoteStatus.CANCELLED},
    CreditNoteStatus.ISSUED: {CreditNoteStatus.APPLIED, CreditNoteStatus.CANCELLED},
}

REFUND_STATUS_TRANSITIONS: dict[str, set[str]] = {
    RefundStatus.REQUESTED: {RefundStatus.APPROVED, RefundStatus.REJECTED},
    RefundStatus.APPROVED: {RefundStatus.PROCESSED, RefundStatus.REJECTED},
}

def assert_finance_transition(
    transitions: dict[str, set[str]], current: str, target: str, *, label: str = "status"
) -> None:
    from app.core.exceptions import BadRequestError

    allowed = transitions.get(current, set())
    if target not in allowed:
        raise BadRequestError("This action isn't available for the current status")
