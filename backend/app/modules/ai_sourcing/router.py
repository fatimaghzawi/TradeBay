"""AI Sourcing API placeholders — no LLM calls."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.ai_sourcing.dependencies import get_sourcing_request_service
from app.modules.ai_sourcing.service import SourcingRequestService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated, success

router = APIRouter(prefix="/ai-sourcing", tags=["AI Sourcing"])


@router.get("/requests", summary="List sourcing requests (scaffolded)")
async def list_sourcing_requests(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[SourcingRequestService, Depends(get_sourcing_request_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    from app.modules.identity.exceptions import BusinessContextRequiredError

    if not auth.business_id:
        raise BusinessContextRequiredError()
    items, total = await service.list_requests(
        PaginationParams(page=page, page_size=page_size),
        business_id=auth.business_id,
    )
    data = [
        {
            "id": str(i["_id"]),
            "status": i.get("status"),
            "original_prompt": i.get("original_prompt"),
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/requests/{request_id}", summary="Get sourcing request (scaffolded)")
async def get_sourcing_request(
    request_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return success({"id": request_id, "status": "scaffold", "items": [], "recommendations": []})
