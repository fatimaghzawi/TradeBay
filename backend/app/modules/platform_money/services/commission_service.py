from __future__ import annotations

from typing import Any

from app.modules.platform_money.constants import COMMISSION_STATUS_TRANSITIONS, CommissionStatus
from app.modules.platform_money.repository import CommissionRepository


class CommissionService:
    def __init__(self, commission_repository: CommissionRepository) -> None:
        self._commissions = commission_repository

    async def recognize_for_order(self, order_id: str) -> dict[str, Any]:
        _ = COMMISSION_STATUS_TRANSITIONS
        raise NotImplementedError

    async def transition_status(self, commission_id: str, target: CommissionStatus) -> dict[str, Any]:
        raise NotImplementedError
