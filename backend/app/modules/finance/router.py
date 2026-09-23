"""Finance API — invoices, payments, credit notes, refunds, AR ledger."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.finance.schemas import (
    CreateCreditNoteRequest,
    CreateRefundRequest,
    RecordPaymentRequest,
)
from app.modules.finance.service import FinanceService
from app.modules.identity.dependencies import AuthContext, require_permission
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Finance"])


def get_finance_service() -> FinanceService:
    return FinanceService()


# ── Invoices ───────────────────────────────────────────────────────────────


@router.get("/invoices", summary="List invoices for active business")
async def list_invoices(
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_invoices(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/invoices/{invoice_id}", summary="Get invoice detail")
async def get_invoice(
    invoice_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(await service.get_invoice(business=auth.business, invoice_id=invoice_id))


@router.post("/invoices/{invoice_id}/payments", summary="Record payment against invoice")
async def record_payment(
    invoice_id: str,
    body: RecordPaymentRequest,
    auth: Annotated[AuthContext, Depends(require_permission("payments", "create"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.record_payment(
            user_id=auth.user_id,
            business=auth.business,
            invoice_id=invoice_id,
            amount=body.amount,
            payment_method=body.payment_method,
            reference=body.reference,
            complete=body.complete,
        )
    )


@router.post(
    "/invoices/{invoice_id}/credit-notes",
    summary="Issue credit note against invoice (does not alter invoice total)",
)
async def create_credit_note(
    invoice_id: str,
    body: CreateCreditNoteRequest,
    auth: Annotated[AuthContext, Depends(require_permission("credit_notes", "create"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.create_credit_note(
            user_id=auth.user_id,
            business=auth.business,
            invoice_id=invoice_id,
            amount=body.amount,
            reason=body.reason,
            apply=body.apply,
            lines=body.lines,
        )
    )


# ── Payments ───────────────────────────────────────────────────────────────


@router.get("/payments", summary="List payments")
async def list_payments(
    auth: Annotated[AuthContext, Depends(require_permission("payments", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_payments(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/payments/{payment_id}", summary="Get payment")
async def get_payment(
    payment_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payments", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(await service.get_payment(business=auth.business, payment_id=payment_id))


@router.post("/payments/{payment_id}/complete", summary="Complete a pending payment")
async def complete_payment(
    payment_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("payments", "create"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.complete_payment(
            user_id=auth.user_id, business=auth.business, payment_id=payment_id
        )
    )


@router.post("/payments/{payment_id}/refunds", summary="Create refund against a payment")
async def create_refund(
    payment_id: str,
    body: CreateRefundRequest,
    auth: Annotated[AuthContext, Depends(require_permission("refunds", "create"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.create_refund(
            user_id=auth.user_id,
            business=auth.business,
            payment_id=payment_id,
            amount=body.amount,
            reason=body.reason,
            credit_note_id=body.credit_note_id,
            process=body.process,
        )
    )


# ── Credit notes ───────────────────────────────────────────────────────────


@router.get("/credit-notes", summary="List credit notes")
async def list_credit_notes(
    auth: Annotated[AuthContext, Depends(require_permission("credit_notes", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_credit_notes(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/credit-notes/{credit_note_id}", summary="Get credit note")
async def get_credit_note(
    credit_note_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("credit_notes", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.get_credit_note(business=auth.business, credit_note_id=credit_note_id)
    )


# ── Refunds ────────────────────────────────────────────────────────────────


@router.get("/refunds", summary="List refunds")
async def list_refunds(
    auth: Annotated[AuthContext, Depends(require_permission("refunds", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_refunds(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/refunds/{refund_id}", summary="Get refund")
async def get_refund(
    refund_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("refunds", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(await service.get_refund(business=auth.business, refund_id=refund_id))


@router.post("/refunds/{refund_id}/process", summary="Approve and process a requested refund")
async def process_refund(
    refund_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("refunds", "create"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.process_refund(
            user_id=auth.user_id, business=auth.business, refund_id=refund_id
        )
    )


# ── Balance & history (derived — never a stored balance field) ─────────────


@router.get("/finance/ar-balance", summary="Buyer accounts-receivable outstanding")
async def ar_balance(
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    buyer_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return success(await service.ar_balance(business=auth.business, buyer_id=buyer_id))


@router.get(
    "/finance/customers/{buyer_id}/balance",
    summary="Derived customer outstanding balance",
)
async def customer_balance(
    buyer_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(await service.ar_balance(business=auth.business, buyer_id=buyer_id))


@router.get(
    "/finance/customers/{buyer_id}/transactions",
    summary="Financial transaction history explaining the balance",
)
async def customer_transactions(
    buyer_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_transactions(
        business=auth.business,
        buyer_id=buyer_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/finance/transactions", summary="Ledger history for the active buyer business")
async def my_transactions(
    auth: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_transactions(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


# ── Platform money payables (existing — not Customer Finance core) ─────────


@router.get("/payables", summary="List supplier payables")
async def list_payables(
    auth: Annotated[AuthContext, Depends(require_permission("payables", "read"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_payables(
        business=auth.business, page=pagination.page, page_size=pagination.page_size
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("/payables/{payable_id}/settle", summary="Settle supplier payable (platform)")
async def settle_payable(
    payable_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("settlements", "approve"))],
    service: Annotated[FinanceService, Depends(get_finance_service)],
) -> dict[str, Any]:
    return success(
        await service.settle_payable(
            user_id=auth.user_id, business=auth.business, payable_id=payable_id
        )
    )
