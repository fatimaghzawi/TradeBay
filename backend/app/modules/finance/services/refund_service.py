from __future__ import annotations

from typing import Any

from app.modules.finance.repository import RefundRepository


class RefundService:
    def __init__(self, refund_repository: RefundRepository) -> None:
        self._refunds = refund_repository

    async def initiate_refund(self, *, payment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
