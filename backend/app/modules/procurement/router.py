from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.identity.dependencies import AuthContext, get_current_user
from app.modules.identity.exceptions import BusinessContextRequiredError
from app.modules.procurement.dependencies import get_order_service, get_rfq_service
from app.modules.procurement.service import OrderService, RFQService
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated

router = APIRouter(tags=["Procurement"])


def _require_business_id(auth: AuthContext) -> str:
    if not auth.business_id:
        raise BusinessContextRequiredError()
    return auth.business_id


@router.get("/rfqs", summary="List RFQs")
async def list_rfqs(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[RFQService, Depends(get_rfq_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    items, total = await service.list_rfqs(
        PaginationParams(page=page, page_size=page_size),
        business_id=_require_business_id(auth),
    )
    data = [
        {"id": str(i["_id"]), "rfq_number": i.get("rfq_number"), "title": i.get("title"), "status": i.get("status")}
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/quotations", summary="List quotations (scaffolded)")
async def list_quotations(auth: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    _require_business_id(auth)
    return paginated([], total=0)


@router.get("/orders", summary="List orders")
async def list_orders(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    items, total = await service.list_orders(
        PaginationParams(page=page, page_size=page_size),
        business_id=_require_business_id(auth),
    )
    data = [{"id": str(i["_id"]), "order_number": i.get("order_number"), "status": i.get("status")} for i in items]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/shipments", summary="List shipments (scaffolded)")
async def list_shipments(auth: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    _require_business_id(auth)
    return paginated([], total=0)
