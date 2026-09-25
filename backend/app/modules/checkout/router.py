
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request

from app.core.exceptions import ForbiddenError
from app.modules.checkout.payments import confirm_offline_payment, handle_stripe_webhook
from app.modules.checkout.schemas import CancelRequest, ConfirmCashRequest, PlaceCheckoutRequest
from app.modules.checkout.service import CheckoutService
from app.modules.identity.constants import BusinessAccountType
from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.identity.http import client_ip
from app.modules.platform_money.supplier_ledger import SupplierLedgerService
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Checkout & Payments"])

def get_checkout_service() -> CheckoutService:
    return CheckoutService()

@router.get("/checkout/preview", summary="Server-priced checkout preview from the buyer's cart")
async def checkout_preview(
    auth: Annotated[AuthContext, Depends(require_permission("products", "read"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(await service.preview(business=auth.business))

@router.post("/checkouts", summary="Place a checkout (one order + invoice per supplier)")
async def place_checkout(
    body: PlaceCheckoutRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    return success(
        await service.place(
            user_id=auth.user_id,
            business=auth.business,
            payment_method=body.payment_method,
            idempotency_key=idempotency_key,
            expected_total=body.expected_total,
            notes=body.notes,
            ip=client_ip(request),
        )
    )

@router.get("/checkouts", summary="List checkouts (buyer: own; TradeBay: all)")
async def list_checkouts(
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
) -> dict[str, Any]:
    items, total = await service.list(
        business=auth.business, page=pagination.page, page_size=pagination.page_size, status=status
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)

@router.get("/checkouts/{checkout_id}", summary="Checkout detail with supplier orders, invoices and payment")
async def get_checkout(
    checkout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(await service.get(business=auth.business, checkout_id=checkout_id))

@router.post("/checkouts/{checkout_id}/card-payment", summary="Start or resume card payment")
async def start_card_payment(
    checkout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(await service.start_card_payment(business=auth.business, checkout_id=checkout_id))

@router.post("/checkouts/{checkout_id}/refresh-payment", summary="Re-check card payment status with the processor")
async def refresh_payment(
    checkout_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(await service.refresh_payment(business=auth.business, checkout_id=checkout_id))

@router.post("/checkouts/{checkout_id}/cancel", summary="Cancel an unpaid checkout")
async def cancel_checkout(
    checkout_id: str,
    body: CancelRequest,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "cancel"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(
        await service.cancel(
            user_id=auth.user_id, business=auth.business, checkout_id=checkout_id, reason=body.reason
        )
    )

@router.post("/purchase-orders/{order_id}/cancel", summary="Cancel or decline one unpaid supplier order")
async def cancel_order(
    order_id: str,
    body: CancelRequest,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "cancel"))],
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> dict[str, Any]:
    return success(
        await service.cancel_order(
            user_id=auth.user_id, business=auth.business, order_id=order_id, reason=body.reason
        )
    )

@router.post("/payments/{payment_id}/confirm-cash", summary="TradeBay confirms cash was received")
async def confirm_cash(
    payment_id: str,
    body: ConfirmCashRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
) -> dict[str, Any]:
    if str((auth.business or {}).get("type")) != BusinessAccountType.PLATFORM:
        raise ForbiddenError("Only TradeBay staff can confirm cash receipts")
    return success(await confirm_offline_payment(payment_id=payment_id, user_id=auth.user_id, note=body.note))

@router.post(
    "/payments/stripe/webhook",
    summary="Stripe webhook (signature-verified, idempotent by event id)",
    include_in_schema=False,
)
async def stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, Any]:
    payload = await request.body()
    return await handle_stripe_webhook(payload=payload, signature=stripe_signature)

                                                                           

@router.get("/supplier-balance", summary="Supplier: my balance derived from the ledger")
async def my_balance(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
) -> dict[str, Any]:
    return success(await SupplierLedgerService().balance(business=auth.business))

@router.get("/supplier-balance/entries", summary="Supplier: my ledger history")
async def my_ledger(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await SupplierLedgerService().entries(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)

@router.get("/admin/supplier-balances", summary="TradeBay: every supplier balance")
async def all_balances(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
) -> dict[str, Any]:
    return success(await SupplierLedgerService().all_balances(business=auth.business))

@router.get("/admin/supplier-balances/{supplier_id}/entries", summary="TradeBay: one supplier's ledger")
async def supplier_ledger(
    supplier_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    service = SupplierLedgerService()
    balance = await service.balance(business=auth.business, supplier_id=supplier_id)
    items, total = await service.entries(
        business=auth.business, supplier_id=supplier_id, page=pagination.page, page_size=pagination.page_size
    )
    payload = paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)
    payload["balance"] = balance
    return payload

@router.get("/admin/supplier-balances/{supplier_id}/overview", summary="TradeBay: one supplier's financial position")
async def supplier_financial_overview(
    supplier_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    range_key: Annotated[str, Query(alias="range")] = "30d",
) -> dict[str, Any]:
    return success(
        await SupplierLedgerService().financial_overview(
            business=auth.business, supplier_id=supplier_id, range_key=range_key
        )
    )
