from __future__ import annotations

from typing import Any

from app.modules.platform_money.repository import SupplierPayableRepository


class SupplierPayableService:
    def __init__(self, payable_repository: SupplierPayableRepository) -> None:
        self._payables = payable_repository

    async def accrue_from_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def schedule_payout(self, payable_id: str) -> dict[str, Any]:
        raise NotImplementedError
