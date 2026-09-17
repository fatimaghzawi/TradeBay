from __future__ import annotations

from typing import Any

from app.modules.finance.constants import PAYMENT_STATUS_TRANSITIONS, PaymentStatus
from app.modules.finance.repository import PaymentRepository


class PaymentService:
    def __init__(self, payment_repository: PaymentRepository) -> None:
        self._payments = payment_repository

    async def record_payment(self, *, invoice_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def transition_status(self, payment_id: str, target: PaymentStatus) -> dict[str, Any]:
        _ = PAYMENT_STATUS_TRANSITIONS
        raise NotImplementedError
