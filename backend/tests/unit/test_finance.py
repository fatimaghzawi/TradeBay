
from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.exceptions import BadRequestError
from app.modules.finance.balance import invoice_position, ledger_outstanding, money
from app.modules.finance.constants import (
    INVOICE_STATUS_TRANSITIONS,
    PAYMENT_STATUS_TRANSITIONS,
    REFUND_STATUS_TRANSITIONS,
    InvoiceStatus,
    PaymentStatus,
    RefundStatus,
    assert_finance_transition,
)
from app.modules.finance.schemas import CreateCreditNoteRequest, RecordPaymentRequest
from pydantic import ValidationError


def test_invoice_position_preserves_total_when_credited() -> None:
    pos = invoice_position(total="2000.00", amount_paid="0", amount_credited="300.00")
    assert pos["total"] == Decimal("2000.00")
    assert pos["amount_due"] == Decimal("1700.00")
    assert pos["outstanding"] == Decimal("1700.00")
    assert pos["customer_credit"] == Decimal("0.00")

def test_partial_then_full_payment() -> None:
    after_first = invoice_position(total="2155.00", amount_paid="1000.00", amount_credited="0")
    assert after_first["outstanding"] == Decimal("1155.00")
    after_full = invoice_position(total="2155.00", amount_paid="2155.00", amount_credited="0")
    assert after_full["outstanding"] == Decimal("0.00")

def test_credit_after_full_payment_creates_customer_credit() -> None:
    pos = invoice_position(total="2000.00", amount_paid="2000.00", amount_credited="300.00")
    assert pos["total"] == Decimal("2000.00")
    assert pos["outstanding"] == Decimal("0.00")
    assert pos["customer_credit"] == Decimal("300.00")

def test_ledger_outstanding_from_events() -> None:
                                                    
    assert ledger_outstanding(debits="2000", credits="800") == Decimal("1200.00")

def test_money_rejects_implicit_float_via_schema() -> None:
    with pytest.raises(ValidationError):
        RecordPaymentRequest(amount=12.5)  # type: ignore[arg-type]

def test_credit_note_requires_reason() -> None:
    with pytest.raises(ValidationError):
        CreateCreditNoteRequest(amount="10.00", reason="")

def test_payment_pending_does_not_reduce_in_position_math() -> None:
                                                                             
    pos = invoice_position(total="100.00", amount_paid="0", amount_credited="0")
    assert pos["outstanding"] == Decimal("100.00")

def test_payment_status_transitions() -> None:
    assert_finance_transition(
        PAYMENT_STATUS_TRANSITIONS, PaymentStatus.PENDING, PaymentStatus.COMPLETED
    )
                                                                                         
    assert_finance_transition(
        PAYMENT_STATUS_TRANSITIONS, PaymentStatus.FAILED, PaymentStatus.COMPLETED
    )
    with pytest.raises(BadRequestError):
        assert_finance_transition(
            PAYMENT_STATUS_TRANSITIONS, PaymentStatus.COMPLETED, PaymentStatus.PENDING
        )
    with pytest.raises(BadRequestError):
        assert_finance_transition(
            PAYMENT_STATUS_TRANSITIONS, PaymentStatus.CANCELLED, PaymentStatus.COMPLETED
        )

def test_refund_cannot_skip_to_processed_from_requested_without_approve() -> None:
    with pytest.raises(BadRequestError):
        assert_finance_transition(
            REFUND_STATUS_TRANSITIONS, RefundStatus.REQUESTED, RefundStatus.PROCESSED
        )

def test_invoice_issued_can_become_paid() -> None:
    assert InvoiceStatus.PAID in INVOICE_STATUS_TRANSITIONS[InvoiceStatus.ISSUED]

def test_money_quantize() -> None:
    assert money("10.005") == Decimal("10.01")
    assert money(Decimal("1")) == Decimal("1.00")
