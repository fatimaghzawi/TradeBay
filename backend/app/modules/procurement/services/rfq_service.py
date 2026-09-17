from __future__ import annotations

from typing import Any

from app.modules.procurement.constants import RFQ_STATUS_TRANSITIONS, RFQStatus
from app.modules.procurement.repository import RFQRepository


class RFQService:
    def __init__(self, rfq_repository: RFQRepository) -> None:
        self._rfqs = rfq_repository

    async def list_rfqs(
        self,
        *,
        business_account_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_doc = {"buyer_business_account_id": business_account_id}
        total = await self._rfqs.count(filter_doc)
        items = await self._rfqs.find_many(filter_doc, skip=skip, limit=limit)
        return items, total

    async def transition_status(self, rfq_id: str, target: RFQStatus) -> dict[str, Any]:
        _ = RFQ_STATUS_TRANSITIONS
        raise NotImplementedError
