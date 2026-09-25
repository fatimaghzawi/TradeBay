
from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.exceptions import BadRequestError
from app.modules.platform_money.commission import compute_split, money
from app.modules.platform_money.constants import (
    PAYOUT_STATUS_TRANSITIONS,
    PayoutStatus,
    assert_platform_transition,
)
from app.modules.platform_money.router import ProviderWebhookRequest
from pydantic import ValidationError


def test_commission_split_5_percent() -> None:
    split = compute_split(order_total="1000.00", base_amount="1000.00", rate="0.05")
    assert split["commission_amount"] == Decimal("50.00")
    assert split["net_payable"] == Decimal("950.00")

def test_historical_rate_frozen_math() -> None:
                                                                                               
    split = compute_split(order_total="2000.00", base_amount="2000.00", rate="0.05")
    assert split["commission_amount"] == Decimal("100.00")
    assert split["net_payable"] == Decimal("1900.00")

def test_negative_rate_rejected() -> None:
    with pytest.raises(ValueError):
        compute_split(order_total="100", base_amount="100", rate="-0.01")

def test_payout_invalid_transition() -> None:
    with pytest.raises(BadRequestError):
        assert_platform_transition(
            PAYOUT_STATUS_TRANSITIONS, PayoutStatus.COMPLETED, PayoutStatus.PENDING
        )

def test_webhook_rejects_float_amount() -> None:
    with pytest.raises(ValidationError):
        ProviderWebhookRequest(
            provider="stripe",
            event_id="evt_1",
            event_type="buyer_payment",
            amount=10.5,  # type: ignore[arg-type]
            reference_type="payment",
            reference_id="abc",
        )

def test_money_quantize() -> None:
    assert money("1.005") == Decimal("1.01")
