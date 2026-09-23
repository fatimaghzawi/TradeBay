"""Negotiation API — open, propose offers, accept into quotation revision."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.negotiation.service import NegotiationService
from app.shared.schemas.response import success

router = APIRouter(prefix="/negotiations", tags=["Negotiation"])


def get_negotiation_service() -> NegotiationService:
    return NegotiationService()


class OpenNegotiationRequest(BaseModel):
    rfq_id: str
    quotation_id: str


class OfferLineIn(BaseModel):
    rfq_item_id: str
    quantity: str
    unit_price: str
    discount: str = "0"
    product_name: str | None = None
    sku: str | None = None
    unit: str = "unit"
    lead_time_days: int | None = None
    notes: str | None = None

    @field_validator("quantity", "unit_price", "discount", mode="before")
    @classmethod
    def _no_float(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("Money must be string or int — not float")
        return v


class ProposeOfferRequest(BaseModel):
    payment_terms: str | None = None
    parent_offer_id: str | None = None
    lines: list[OfferLineIn] = Field(min_length=1)


@router.post("", summary="Open negotiation on an RFQ quotation")
async def open_negotiation(
    body: OpenNegotiationRequest,
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "create"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> dict[str, Any]:
    return success(
        await service.open(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=body.rfq_id,
            quotation_id=body.quotation_id,
        )
    )


@router.get("", summary="List negotiations for an RFQ")
async def list_negotiations(
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "read"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
    rfq_id: Annotated[str, Query(min_length=24, max_length=24)],
) -> dict[str, Any]:
    return success(await service.list_for_rfq(business=auth.business, rfq_id=rfq_id))


@router.get("/{negotiation_id}", summary="Get negotiation with offer history")
async def get_negotiation(
    negotiation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "read"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> dict[str, Any]:
    return success(await service.get(negotiation_id=negotiation_id, business=auth.business))


@router.post("/{negotiation_id}/offers", summary="Propose or counter an offer")
async def propose_offer(
    negotiation_id: str,
    body: ProposeOfferRequest,
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "manage"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> dict[str, Any]:
    return success(
        await service.propose_offer(
            user_id=auth.user_id,
            business=auth.business,
            negotiation_id=negotiation_id,
            lines=[ln.model_dump() for ln in body.lines],
            payment_terms=body.payment_terms,
            parent_offer_id=body.parent_offer_id,
        )
    )


@router.post("/{negotiation_id}/offers/{offer_id}/accept", summary="Accept offer → revise quotation")
async def accept_offer(
    negotiation_id: str,
    offer_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "manage"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> dict[str, Any]:
    return success(
        await service.accept_offer(
            user_id=auth.user_id,
            business=auth.business,
            negotiation_id=negotiation_id,
            offer_id=offer_id,
        )
    )


@router.post("/{negotiation_id}/offers/{offer_id}/reject", summary="Reject a proposed offer")
async def reject_offer(
    negotiation_id: str,
    offer_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("negotiations", "manage"))],
    service: Annotated[NegotiationService, Depends(get_negotiation_service)],
) -> dict[str, Any]:
    return success(
        await service.reject_offer(
            user_id=auth.user_id,
            business=auth.business,
            negotiation_id=negotiation_id,
            offer_id=offer_id,
        )
    )
