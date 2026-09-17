"""Business Planner services — structure only. No AI / price calc."""

from __future__ import annotations

from typing import Any

from app.modules.business_planner.repository import (
    BusinessPlanItemRepository,
    BusinessPlanRepository,
    PriceEstimateRepository,
)
from app.shared.schemas.pagination import PaginationParams


class BusinessPlanService:
    def __init__(
        self,
        plans: BusinessPlanRepository | None = None,
        items: BusinessPlanItemRepository | None = None,
    ) -> None:
        self.plans = plans or BusinessPlanRepository()
        self.items = items or BusinessPlanItemRepository()

    async def list_plans(
        self, pagination: PaginationParams
    ) -> tuple[list[dict[str, Any]], int]:
        rows = await self.plans.find_many({}, skip=pagination.skip, limit=pagination.limit)
        return rows, await self.plans.count({})

    async def generate_plan(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("AI business plan generation is deferred")

    async def convert_to_sourcing(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("BusinessPlan → SourcingRequest conversion is deferred")


class PriceEstimateService:
    def __init__(self, repo: PriceEstimateRepository | None = None) -> None:
        self.repo = repo or PriceEstimateRepository()

    async def calculate(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("Price estimation is deferred")
