from __future__ import annotations

from typing import Any

from app.modules.finance.constants import INVOICE_STATUS_TRANSITIONS, InvoiceStatus
from app.modules.finance.repository import InvoiceRepository


class InvoiceService:
    def __init__(self, invoice_repository: InvoiceRepository) -> None:
        self._invoices = invoice_repository

    async def list_invoices(
        self,
        *,
        business_account_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_doc = {"customer_business_account_id": business_account_id}
        total = await self._invoices.count(filter_doc)
        items = await self._invoices.find_many(filter_doc, skip=skip, limit=limit)
        return items, total

    async def issue_invoice(self, invoice_id: str) -> dict[str, Any]:
        _ = INVOICE_STATUS_TRANSITIONS
        raise NotImplementedError

    async def transition_status(self, invoice_id: str, target: InvoiceStatus) -> dict[str, Any]:
        _ = INVOICE_STATUS_TRANSITIONS
        raise NotImplementedError
