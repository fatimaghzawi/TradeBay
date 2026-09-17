"""Negotiation API placeholders."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.identity.dependencies import AuthContext, get_current_user
from app.modules.negotiation.dependencies import get_negotiation_service
from app.modules.negotiation.service import NegotiationService
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Negotiation"])


@router.get("/negotiations", summary="List negotiations (scaffolded)")
async def list_negotiations(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    from app.modules.identity.exceptions import BusinessContextRequiredError

    if not auth.business_id:
        raise BusinessContextRequiredError()
    items, total = await service.list_negotiations(
        PaginationParams(page=page, page_size=page_size),
        business_id=auth.business_id,
    )
    data = [
        {
            "id": str(i["_id"]),
            "conversation_id": str(i.get("conversation_id", "")),
            "status": i.get("status"),
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/negotiations/{negotiation_id}", summary="Get negotiation (scaffolded)")
async def get_negotiation(
    negotiation_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return success({"id": negotiation_id, "status": "scaffold", "offers": []})


@router.get(
    "/negotiations/{negotiation_id}/offers",
    summary="List negotiation offers (scaffolded)",
)
async def list_offers(
    negotiation_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    items, total = await service.list_offers(
        negotiation_id, PaginationParams(page=page, page_size=page_size)
    )
    data = [
        {
            "id": str(i["_id"]),
            "parent_offer_id": str(i["parent_offer_id"]) if i.get("parent_offer_id") else None,
            "status": i.get("status"),
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)
