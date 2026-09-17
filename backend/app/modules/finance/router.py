from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.finance.dependencies import get_invoice_service
from app.modules.finance.service import InvoiceService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.modules.identity.exceptions import BusinessContextRequiredError
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated

router = APIRouter(tags=["Finance"])


@router.get("/invoices", summary="List customer invoices")
async def list_invoices(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    if not auth.business_id:
        raise BusinessContextRequiredError()
    items, total = await service.list_invoices(
        PaginationParams(page=page, page_size=page_size),
        business_id=auth.business_id,
    )
    data = [{"id": str(i["_id"]), "invoice_number": i.get("invoice_number"), "status": i.get("status")} for i in items]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/payments", summary="List payments (scaffolded)")
async def list_payments(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/credit-notes", summary="List credit notes (scaffolded)")
async def list_credit_notes(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/refunds", summary="List refunds (scaffolded)")
async def list_refunds(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)
