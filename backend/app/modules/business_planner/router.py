"""Business Planner API placeholders — no AI generation."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.business_planner.dependencies import get_business_plan_service
from app.modules.business_planner.service import BusinessPlanService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated, success

router = APIRouter(prefix="/business-plans", tags=["Business Planner"])


@router.get("", summary="List business plans (scaffolded)")
async def list_business_plans(
    _: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessPlanService, Depends(get_business_plan_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    items, total = await service.list_plans(PaginationParams(page=page, page_size=page_size))
    data = [
        {
            "id": str(i["_id"]),
            "business_type": i.get("business_type"),
            "status": i.get("status"),
            "business_name": i.get("business_name"),
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/{plan_id}", summary="Get business plan (scaffolded)")
async def get_business_plan(
    plan_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return success({"id": plan_id, "status": "scaffold", "items": [], "price_estimates": []})
