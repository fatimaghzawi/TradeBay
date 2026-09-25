from enum import StrEnum


class CheckoutStatus(StrEnum):

                                                                                                
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    CANCELLED = "cancelled"

CHECKOUT_TRANSITIONS: dict[str, set[str]] = {
    CheckoutStatus.AWAITING_PAYMENT: {CheckoutStatus.PAID, CheckoutStatus.CANCELLED},
    CheckoutStatus.PAID: set(),
    CheckoutStatus.CANCELLED: set(),
}

CHECKOUT_PREFIX = "CHK"
ORDER_PREFIX = "PO"
PAYMENT_PREFIX = "PAY"
RECEIPT_PREFIX = "RCP"

MAX_LINE_QUANTITY = 1_000_000
MAX_CHECKOUT_LINES = 200
