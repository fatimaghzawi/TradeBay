"""Unit tests for procurement commercial Decimal math and transitions."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.exceptions import BadRequestError
from app.modules.procurement.commercial import compute_document_totals, compute_line
from app.modules.procurement.constants import (
    ORDER_TRANSITIONS,
    RFQ_TRANSITIONS,
    OrderStatus,
    RFQStatus,
    assert_transition,
)


def test_order_draft_can_issue_or_cancel() -> None:
    assert_transition(ORDER_TRANSITIONS, OrderStatus.DRAFT, OrderStatus.PENDING)
    assert_transition(ORDER_TRANSITIONS, OrderStatus.DRAFT, OrderStatus.CANCELLED)
    with pytest.raises(BadRequestError):
        assert_transition(ORDER_TRANSITIONS, OrderStatus.DRAFT, OrderStatus.CONFIRMED)

    line = compute_line(quantity="10", unit_price="12.50", discount="5", tax="2", shipping="1")
    assert line.subtotal == Decimal("125.00")
    assert line.line_total == Decimal("123.00")


def test_document_totals() -> None:
    lines = [
        compute_line(quantity="2", unit_price="10"),
        compute_line(quantity="1", unit_price="5", tax="0.50"),
    ]
    totals = compute_document_totals(lines, document_shipping="3")
    assert totals.subtotal == Decimal("25.00")
    assert totals.charge_total == Decimal("3.00")
    assert totals.tax_total == Decimal("0.50")
    assert totals.total == Decimal("28.50")


def test_rejects_float_money_via_decimal_str() -> None:
    # compute_line accepts str/int/Decimal — float is rejected upstream by schemas
    line = compute_line(quantity=5, unit_price=Decimal("1.10"))
    assert line.line_total == Decimal("5.50")


def test_money_rejects_blank_and_invalid() -> None:
    from app.modules.procurement.commercial import money, optional_money
    from app.modules.procurement.schemas import RFQItemIn

    with pytest.raises(ValueError):
        money("")
    with pytest.raises(ValueError):
        money("  ")
    with pytest.raises(ValueError):
        money("not-a-price")
    assert optional_money(None) is None
    assert optional_money("") is None
    assert optional_money("  ") is None
    assert optional_money("12.50") == Decimal("12.50")
    with pytest.raises(ValueError):
        optional_money("abc")

    item = RFQItemIn(product_name="Widget", quantity="10", target_unit_price="  ")
    assert item.target_unit_price is None
    with pytest.raises(Exception):
        RFQItemIn(product_name="Widget", quantity="10", target_unit_price="nope")


def test_rfq_transition_enforced() -> None:
    assert_transition(RFQ_TRANSITIONS, RFQStatus.DRAFT, RFQStatus.PUBLISHED)
    with pytest.raises(BadRequestError):
        assert_transition(RFQ_TRANSITIONS, RFQStatus.DRAFT, RFQStatus.AWARDED)


def test_order_cannot_go_back_to_pending() -> None:
    with pytest.raises(BadRequestError):
        assert_transition(ORDER_TRANSITIONS, OrderStatus.SHIPPED, OrderStatus.PENDING)


def test_rejected_quotation_can_reopen_for_bargain() -> None:
    from app.modules.procurement.constants import QUOTATION_TRANSITIONS, QuotationStatus

    assert_transition(
        QUOTATION_TRANSITIONS, QuotationStatus.REJECTED, QuotationStatus.NEGOTIATING
    )
    assert_transition(
        QUOTATION_TRANSITIONS, QuotationStatus.REJECTED, QuotationStatus.SUBMITTED
    )
    with pytest.raises(BadRequestError):
        assert_transition(
            QUOTATION_TRANSITIONS, QuotationStatus.ACCEPTED, QuotationStatus.SUBMITTED
        )
