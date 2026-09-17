"""Negotiation service skeletons — no accept/counter state machine yet."""

from __future__ import annotations

from typing import Any

from app.modules.negotiation.repository import NegotiationOfferRepository, NegotiationRepository
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class NegotiationService:
    def __init__(
        self,
        negotiations: NegotiationRepository | None = None,
        offers: NegotiationOfferRepository | None = None,
    ) -> None:
        self.negotiations = negotiations or NegotiationRepository()
        self.offers = offers or NegotiationOfferRepository()

    async def list_negotiations(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        oid = parse_object_id(business_id)
        filt = {"$or": [{"buyer_business_id": oid}, {"supplier_business_id": oid}]}
        items = await self.negotiations.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.negotiations.count(filt)

    async def list_offers(
        self, negotiation_id: str, pagination: PaginationParams
    ) -> tuple[list[dict[str, Any]], int]:
        filt = {"negotiation_id": negotiation_id}
        items = await self.offers.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return items, await self.offers.count(filt)

    async def propose_offer(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("Offer propose/counter/accept is deferred")
