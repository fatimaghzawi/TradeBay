from enum import StrEnum


class CommissionStatus(StrEnum):
    PENDING = "pending"
    RECOGNIZED = "recognized"
    REVERSED = "reversed"

class PayableStatus(StrEnum):
    OPEN = "open"
    PARTIALLY_SETTLED = "partially_settled"
    SETTLED = "settled"
    DISPUTED = "disputed"
                                                                            
    CANCELLED = "cancelled"

class SupplierLedgerEntryType(StrEnum):
    SALE = "sale"
    PLATFORM_FEE = "platform_fee"
    FUNDS_RELEASED = "funds_released"
    PAYOUT = "payout"
    ADJUSTMENT = "adjustment"

class SupplierLedgerDirection(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"

class SupplierBalanceBucket(StrEnum):

    PENDING = "pending"
    AVAILABLE = "available"

class PayoutStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SettlementStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PlatformLedgerStatus(StrEnum):
    POSTED = "posted"
    REVERSED = "reversed"

class FundsState(StrEnum):

    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"

class PlatformTransactionType(StrEnum):
    BUYER_PAYMENT = "buyer_payment"
    FUNDS_RELEASED = "funds_released"
    PLATFORM_FEE = "platform_fee"
    SUPPLIER_PAYOUT = "supplier_payout"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    CREDIT = "credit"

class CommissionBase(StrEnum):

    ORDER_SUBTOTAL = "order_subtotal"
    ORDER_TOTAL = "order_total"

class CommissionType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"

COMMISSION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CommissionStatus.PENDING: {CommissionStatus.RECOGNIZED, CommissionStatus.REVERSED},
    CommissionStatus.RECOGNIZED: {CommissionStatus.REVERSED},
}

PAYABLE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    PayableStatus.OPEN: {
        PayableStatus.PARTIALLY_SETTLED,
        PayableStatus.SETTLED,
        PayableStatus.DISPUTED,
        PayableStatus.CANCELLED,
    },
    PayableStatus.PARTIALLY_SETTLED: {PayableStatus.SETTLED, PayableStatus.DISPUTED},
    PayableStatus.DISPUTED: {PayableStatus.OPEN, PayableStatus.SETTLED},
}

PAYOUT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    PayoutStatus.PENDING: {PayoutStatus.PROCESSING, PayoutStatus.FAILED},
    PayoutStatus.PROCESSING: {PayoutStatus.COMPLETED, PayoutStatus.FAILED},
}

SETTLEMENT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    SettlementStatus.DRAFT: {SettlementStatus.PENDING_APPROVAL, SettlementStatus.CANCELLED},
    SettlementStatus.PENDING_APPROVAL: {SettlementStatus.APPROVED, SettlementStatus.CANCELLED},
    SettlementStatus.APPROVED: {SettlementStatus.PAID, SettlementStatus.FAILED},
}

def assert_platform_transition(
    transitions: dict[str, set[str]], current: str, target: str, *, label: str = "status"
) -> None:
    from app.core.exceptions import BadRequestError

    allowed = transitions.get(current, set())
    if target not in allowed:
        raise BadRequestError("This action isn't available for the current status")

                               
SettlementBatchStatus = SettlementStatus