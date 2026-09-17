from __future__ import annotations

from typing import Any


class ProcurementService:
    """Orchestrates RFQ → quotation → order flows (skeleton)."""

    async def award_quotation(self, *, quotation_id: str) -> dict[str, Any]:
        raise NotImplementedError
