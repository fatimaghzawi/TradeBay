"""Procurement service boundaries. Full workflow DEFERRED."""

from __future__ import annotations

from typing import Any

from app.modules.procurement.repository import (
    OrderRepository,
    QuotationRepository,
    RFQRepository,
    ShipmentRepository,
)
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class RFQService:
    def __init__(self, repo: RFQRepository | None = None) -> None:
        self.repo = repo or RFQRepository()

    async def list_rfqs(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        oid = parse_object_id(business_id)
        filt = {
            "$or": [
                {"buyer_business_id": oid},
                {"supplier_invites.supplier_business_id": oid},
                {"visibility": "open", "status": {"$in": ["published", "responding", "negotiating"]}},
            ]
        }
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.repo.count(filt)


class QuotationService:
    def __init__(self, repo: QuotationRepository | None = None) -> None:
        self.repo = repo or QuotationRepository()


class NegotiationService:
    """DEPRECATED boundary inside procurement.

    Offer history and negotiation lifecycle belong in `app.modules.negotiation`.
    Procurement retains Quotation/Order as commercial source of truth.
    """

    async def propose_revision(self, *_a: Any, **_k: Any) -> None:
        raise NotImplementedError(
            "Use negotiation domain; quotation negotiation workflow deferred"
        )


class ProcurementService:
    """Cross-cutting procurement orchestration — DEFERRED."""

    pass


class OrderService:
    def __init__(self, repo: OrderRepository | None = None) -> None:
        self.repo = repo or OrderRepository()

    async def list_orders(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        oid = parse_object_id(business_id)
        filt = {"$or": [{"buyer_business_id": oid}, {"supplier_business_id": oid}]}
        items = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.repo.count(filt)


class ShipmentService:
    def __init__(self, repo: ShipmentRepository | None = None) -> None:
        self.repo = repo or ShipmentRepository()
