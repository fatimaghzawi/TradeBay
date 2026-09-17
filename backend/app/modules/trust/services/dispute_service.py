from __future__ import annotations

from typing import Any

from app.modules.trust.constants import DISPUTE_STATUS_TRANSITIONS, DisputeStatus
from app.modules.trust.repository import DisputeRepository


class DisputeService:
    def __init__(self, dispute_repository: DisputeRepository) -> None:
        self._disputes = dispute_repository

    async def open_dispute(self, *, user_id: str, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def transition_status(self, dispute_id: str, target: DisputeStatus) -> dict[str, Any]:
        _ = DISPUTE_STATUS_TRANSITIONS
        raise NotImplementedError
