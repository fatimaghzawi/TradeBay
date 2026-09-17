from __future__ import annotations

from typing import Any

from app.modules.platform_money.constants import (
    SETTLEMENT_STATUS_TRANSITIONS,
    SettlementBatchStatus,
)
from app.modules.platform_money.repository import SettlementRepository


class SettlementService:
    def __init__(self, settlement_repository: SettlementRepository) -> None:
        self._settlements = settlement_repository

    async def create_batch(self) -> dict[str, Any]:
        raise NotImplementedError

    async def run_batch(self, batch_id: str) -> dict[str, Any]:
        _ = SETTLEMENT_STATUS_TRANSITIONS
        raise NotImplementedError

    async def transition_status(self, batch_id: str, target: SettlementBatchStatus) -> dict[str, Any]:
        raise NotImplementedError
