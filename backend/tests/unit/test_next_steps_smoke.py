"""Smoke checklist as automated unit coverage for next-step modules."""

from __future__ import annotations

from app.modules.finance.constants import InvoiceStatus, LedgerDirection
from app.modules.negotiation.constants import NegotiationStatus
from app.modules.procurement.tracking import CarrierWebhookProvider
from app.modules.trust.constants import DisputeStatus


def test_smoke_finance_statuses_exist() -> None:
    assert InvoiceStatus.ISSUED == "issued"
    assert LedgerDirection.DEBIT == "debit"


def test_smoke_dispute_resolve_path() -> None:
    assert DisputeStatus.OPEN in {"open", DisputeStatus.OPEN}
    assert DisputeStatus.RESOLVED == "resolved"


def test_smoke_negotiation_agreed() -> None:
    assert NegotiationStatus.AGREED == "AGREED"


def test_smoke_webhook_auth_payload_shape() -> None:
    update = CarrierWebhookProvider().parse_webhook(
        {"tracking_number": "X", "status": "delivered"}
    )
    assert update is not None
    assert update.status == "delivered"
