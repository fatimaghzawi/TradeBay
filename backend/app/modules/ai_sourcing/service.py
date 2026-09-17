"""AI Sourcing services — structure only. No LLM / vector search."""

from __future__ import annotations

from typing import Any

from app.modules.ai_sourcing.repository import (
    SourcingRecommendationRepository,
    SourcingRequestItemRepository,
    SourcingRequestRepository,
)
from app.shared.schemas.pagination import PaginationParams
from app.shared.utils.objectid import parse_object_id


class SourcingRequestService:
    def __init__(
        self,
        requests: SourcingRequestRepository | None = None,
        items: SourcingRequestItemRepository | None = None,
    ) -> None:
        self.requests = requests or SourcingRequestRepository()
        self.items = items or SourcingRequestItemRepository()

    async def list_requests(
        self, pagination: PaginationParams, *, business_id: str
    ) -> tuple[list[dict[str, Any]], int]:
        filt = {"buyer_business_id": parse_object_id(business_id)}
        rows = await self.requests.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return rows, await self.requests.count(filt)

    async def search_from_prompt(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("LLM sourcing search is deferred")


class SourcingRecommendationService:
    def __init__(self, repo: SourcingRecommendationRepository | None = None) -> None:
        self.repo = repo or SourcingRecommendationRepository()

    async def list_for_request(
        self, sourcing_request_id: str, pagination: PaginationParams
    ) -> tuple[list[dict[str, Any]], int]:
        filt = {"sourcing_request_id": sourcing_request_id}
        rows = await self.repo.find_many(filt, skip=pagination.skip, limit=pagination.limit)
        return rows, await self.repo.count(filt)
