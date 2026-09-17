from __future__ import annotations

from typing import Any

from app.modules.procurement.constants import QUOTATION_STATUS_TRANSITIONS
from app.modules.procurement.repository import QuotationRepository


class QuotationService:
    def __init__(self, quotation_repository: QuotationRepository) -> None:
        self._quotations = quotation_repository

    async def submit_quotation(self, rfq_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _ = QUOTATION_STATUS_TRANSITIONS
        raise NotImplementedError
