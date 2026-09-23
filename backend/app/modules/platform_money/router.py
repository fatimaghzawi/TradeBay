"""Platform Money HTTP API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.platform_money.service import PlatformMoneyService
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(prefix="/platform-money", tags=["Platform Money"])
supplier_payouts_router = APIRouter(prefix="/supplier/payouts", tags=["Platform Money"])


def get_platform_money_service() -> PlatformMoneyService:
    return PlatformMoneyService()


class ProviderWebhookRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1, max_length=64)
    amount: str
    currency: str = "USD"
    reference_type: str
    reference_id: str
    order_id: str | None = None
    payment_id: str | None = None
    supplier_business_id: str | None = None
    provider_transaction_id: str | None = None
    description: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("Money must be string or int — not float")
        return v


class FailPayoutRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


@router.get("/overview", summary="Admin finance command-center overview")
async def platform_money_overview(
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(await service.admin_overview(business=auth.business))


@router.get("/transactions", summary="List platform routing ledger (admin)")
async def list_transactions(
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_transactions(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/transactions/{transaction_id}", summary="Get platform transaction")
async def get_transaction(
    transaction_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(
        await service.get_transaction(business=auth.business, transaction_id=transaction_id)
    )


@router.get("/fees", summary="List platform commission (fee) records")
async def list_fees(
    auth: Annotated[AuthContext, Depends(require_permission("commissions", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_fees(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/payouts", summary="List supplier payouts (admin sees all)")
async def list_payouts_admin(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_payouts(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/payouts/{payout_id}", summary="Get payout detail")
async def get_payout_admin(
    payout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(await service.get_payout(business=auth.business, payout_id=payout_id))


@router.post("/payouts/{payout_id}/process", summary="Process (complete) a pending payout")
async def process_payout(
    payout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(
        await service.process_payout(
            user_id=auth.user_id, business=auth.business, payout_id=payout_id
        )
    )


@router.post("/payouts/{payout_id}/fail", summary="Mark payout failed")
async def fail_payout(
    payout_id: str,
    body: FailPayoutRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(
        await service.fail_payout(
            business=auth.business, payout_id=payout_id, reason=body.reason
        )
    )


@router.post("/orders/{order_id}/release", summary="Release held funds after fulfilment")
async def release_funds(
    order_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(
        await service.release_funds_for_order(order_id=order_id, user_id=auth.user_id)
    )


@router.get("/orders/{order_id}/summary", summary="Money trail for one purchase order")
async def order_money_summary(
    order_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(await service.order_money_summary(business=auth.business, order_id=order_id))


@router.post("/webhooks/provider", summary="Idempotent payment-provider event ingestion")
async def provider_webhook(
    body: ProviderWebhookRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    # Auth required for now (no public Stripe secret validation in this graduation scope).
    return success(
        await service.ingest_provider_event(
            provider=body.provider,
            event_id=body.event_id,
            event_type=body.event_type,
            amount=body.amount,
            currency=body.currency,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
            order_id=body.order_id,
            payment_id=body.payment_id,
            supplier_business_id=body.supplier_business_id,
            provider_transaction_id=body.provider_transaction_id,
            description=body.description,
        )
    )


@supplier_payouts_router.get("", summary="Supplier: list my payouts")
async def list_my_payouts(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_payouts(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@supplier_payouts_router.get("/{payout_id}", summary="Supplier: get my payout")
async def get_my_payout(
    payout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[PlatformMoneyService, Depends(get_platform_money_service)],
) -> dict[str, Any]:
    return success(await service.get_payout(business=auth.business, payout_id=payout_id))
