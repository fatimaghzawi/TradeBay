"""AR services. Do not mix with order or platform-money logic."""

from __future__ import annotations

from typing import Any

from app.modules.finance.repository import (
    CreditNoteRepository,
    InvoiceRepository,
    PaymentRepository,
    RefundRepository,
)
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class InvoiceService:
    def __init__(self, repo: InvoiceRepository | None = None) -> None:
        self.repo = repo or InvoiceRepository()

    async def list_invoices(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        filt = {"buyer_business_id": parse_object_id(business_id)}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.repo.count(filt)


class PaymentService:
    """Payment state and allocation — DEFERRED."""

    def __init__(self, repo: PaymentRepository | None = None) -> None:
        self.repo = repo or PaymentRepository()


class CreditNoteService:
    def __init__(self, repo: CreditNoteRepository | None = None) -> None:
        self.repo = repo or CreditNoteRepository()


class RefundService:
    def __init__(self, repo: RefundRepository | None = None) -> None:
        self.repo = repo or RefundRepository()
