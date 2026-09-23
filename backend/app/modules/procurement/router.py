"""Procurement & Fulfilment HTTP API — RFQ → quotation → PO → shipment → receive."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.procurement.schemas import (
    AwardRFQRequest,
    CreateProductRFQRequest,
    CreateRFQRequest,
    CreateShipmentRequest,
    CreateSourcingRFQRequest,
    HandshakeRFQRequest,
    DeclineInviteRequest,
    DeliveryEvidenceRequest,
    InviteSuppliersRequest,
    IssuePORequest,
    ReceiveShipmentRequest,
    RejectQuotationRequest,
    ReportIssueRequest,
    TrackingEventRequest,
    UpdateRFQRequest,
    UpsertQuotationRequest,
)
from app.modules.procurement.service import ProcurementService
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Procurement"])


def get_procurement_service() -> ProcurementService:
    return ProcurementService()


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ── Dashboard ────────────────────────────────────────────────────────────


@router.get("/procurement/dashboard", summary="Buyer/supplier procurement dashboard")
async def procurement_dashboard(
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(await service.dashboard(business=auth.business))


# ── RFQs ─────────────────────────────────────────────────────────────────


@router.post("/rfqs", summary="Create draft RFQ (legacy — prefer /rfqs/product or /rfqs/sourcing)")
async def create_rfq(
    body: CreateRFQRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.create_rfq(
            user_id=auth.user_id,
            business=auth.business,
            payload=body.model_dump(),
            ip=_ip(request),
        )
    )


@router.post("/rfqs/product", summary="Create a Product RFQ for a listed product")
async def create_product_rfq(
    body: CreateProductRFQRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.create_product_rfq(
            user_id=auth.user_id,
            business=auth.business,
            payload=body.model_dump(),
            ip=_ip(request),
        )
    )


@router.post("/rfqs/sourcing", summary="Create a Sourcing RFQ (open requirement)")
async def create_sourcing_rfq(
    body: CreateSourcingRFQRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.create_sourcing_rfq(
            user_id=auth.user_id,
            business=auth.business,
            payload=body.model_dump(),
            ip=_ip(request),
        )
    )


@router.get("/rfqs", summary="List RFQs for active business")
async def list_rfqs(
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
    rfq_type: str | None = Query(default=None),
    as_supplier: bool = Query(default=False),
) -> dict[str, Any]:
    items, total = await service.list_rfqs(
        business=auth.business,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
        rfq_type=rfq_type,
        as_supplier=as_supplier,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/rfqs/{rfq_id}", summary="Get RFQ detail")
async def get_rfq(
    rfq_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.get_rfq(user_id=auth.user_id, business=auth.business, rfq_id=rfq_id)
    )


@router.patch("/rfqs/{rfq_id}", summary="Update draft RFQ")
async def update_rfq(
    rfq_id: str,
    body: UpdateRFQRequest,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.update_rfq(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            payload=body.model_dump(exclude_unset=True),
        )
    )


@router.post("/rfqs/{rfq_id}/publish", summary="Publish RFQ")
async def publish_rfq(
    rfq_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.publish_rfq(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            ip=_ip(request),
        )
    )


@router.post(
    "/rfqs/{rfq_id}/send",
    summary="Send draft RFQ — one request per product owner",
)
async def send_rfq(
    rfq_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.send_draft_to_product_owners(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            ip=_ip(request),
        )
    )


@router.get("/rfqs/{rfq_id}/eligible-suppliers", summary="List verified suppliers for invite")
async def eligible_suppliers(
    rfq_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(await service.list_eligible_suppliers(business=auth.business, rfq_id=rfq_id))


@router.post("/rfqs/{rfq_id}/invite-suppliers", summary="Invite verified suppliers")
async def invite_suppliers(
    rfq_id: str,
    body: InviteSuppliersRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.invite_suppliers(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            supplier_business_ids=body.supplier_business_ids,
            ip=_ip(request),
        )
    )


@router.post("/rfqs/{rfq_id}/invitations/accept", summary="Supplier accepts RFQ invitation")
async def accept_invite(
    rfq_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "respond"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.respond_invite(
            user_id=auth.user_id, business=auth.business, rfq_id=rfq_id, accept=True
        )
    )


@router.post("/rfqs/{rfq_id}/invitations/decline", summary="Supplier declines RFQ invitation")
async def decline_invite(
    rfq_id: str,
    body: DeclineInviteRequest,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "respond"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.respond_invite(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            accept=False,
            reason=body.reason,
        )
    )


@router.post("/rfqs/{rfq_id}/quotations", summary="Create or update quotation (supplier)")
async def upsert_quotation(
    rfq_id: str,
    body: UpsertQuotationRequest,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "create"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
    submit: bool = Query(default=False),
) -> dict[str, Any]:
    return success(
        await service.upsert_quotation(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            payload=body.model_dump(),
            submit=submit,
        )
    )


@router.get("/rfqs/{rfq_id}/comparison", summary="Compare submitted quotations")
async def compare_quotations(
    rfq_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(await service.comparison(business=auth.business, rfq_id=rfq_id))


@router.post("/rfqs/{rfq_id}/handshake", summary="Confirm deal and prepare draft PO")
async def handshake_rfq(
    rfq_id: str,
    body: HandshakeRFQRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.handshake(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            quotation_id=body.quotation_id,
            confirm=body.confirm,
            ip=_ip(request),
        )
    )


@router.post("/rfqs/{rfq_id}/award", summary="Award RFQ to a quotation and create PO")
async def award_rfq(
    rfq_id: str,
    body: AwardRFQRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.award(
            user_id=auth.user_id,
            business=auth.business,
            rfq_id=rfq_id,
            quotation_id=body.quotation_id,
            confirm=body.confirm,
            ip=_ip(request),
        )
    )


# ── Quotations ───────────────────────────────────────────────────────────


@router.get("/quotations/{quotation_id}", summary="Get quotation detail")
async def get_quotation(
    quotation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.get_quotation(
            user_id=auth.user_id, business=auth.business, quotation_id=quotation_id
        )
    )


@router.post("/quotations/{quotation_id}/withdraw", summary="Withdraw quotation")
async def withdraw_quotation(
    quotation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.withdraw_quotation(
            user_id=auth.user_id, business=auth.business, quotation_id=quotation_id
        )
    )


@router.post("/quotations/{quotation_id}/reject", summary="Buyer declines a quotation")
async def reject_quotation(
    quotation_id: str,
    body: RejectQuotationRequest,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.reject_quotation(
            user_id=auth.user_id,
            business=auth.business,
            quotation_id=quotation_id,
            reason=body.reason,
        )
    )


# ── Purchase orders ──────────────────────────────────────────────────────


@router.get("/purchase-orders", summary="List purchase orders")
async def list_orders(
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    status: str | None = None,
) -> dict[str, Any]:
    items, total = await service.list_orders(
        business=auth.business,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/purchase-orders/{order_id}", summary="Get purchase order")
async def get_order(
    order_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.get_order(user_id=auth.user_id, business=auth.business, order_id=order_id)
    )


@router.post("/purchase-orders/{order_id}/issue", summary="Issue draft purchase order")
async def issue_order(
    order_id: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "accept"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
    body: IssuePORequest,
) -> dict[str, Any]:
    return success(
        await service.issue_order(
            user_id=auth.user_id,
            business=auth.business,
            order_id=order_id,
            payment_method=body.payment_method,
            payment_terms=body.payment_terms,
            delivery_terms=body.delivery_terms,
            ip=_ip(request),
        )
    )


@router.post("/purchase-orders/{order_id}/acknowledge", summary="Supplier acknowledges PO")
async def acknowledge_order(
    order_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "confirm"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.acknowledge_order(
            user_id=auth.user_id, business=auth.business, order_id=order_id
        )
    )


@router.post("/purchase-orders/{order_id}/shipments", summary="Create shipment for PO")
async def create_shipment(
    order_id: str,
    body: CreateShipmentRequest,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.create_shipment(
            user_id=auth.user_id,
            business=auth.business,
            order_id=order_id,
            payload=body.model_dump(),
        )
    )


# ── Shipments ────────────────────────────────────────────────────────────


@router.get("/shipments/{shipment_id}", summary="Get shipment detail")
async def get_shipment(
    shipment_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.get_shipment(
            user_id=auth.user_id, business=auth.business, shipment_id=shipment_id
        )
    )


@router.post("/shipments/{shipment_id}/tracking-events", summary="Append tracking event")
async def add_tracking(
    shipment_id: str,
    body: TrackingEventRequest,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.add_tracking_event(
            user_id=auth.user_id,
            business=auth.business,
            shipment_id=shipment_id,
            payload=body.model_dump(),
        )
    )


@router.post("/shipments/{shipment_id}/delivery-evidence", summary="Upload delivery evidence")
async def add_evidence(
    shipment_id: str,
    body: DeliveryEvidenceRequest,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.add_delivery_evidence(
            user_id=auth.user_id,
            business=auth.business,
            shipment_id=shipment_id,
            payload=body.model_dump(),
        )
    )


@router.post(
    "/shipments/{shipment_id}/delivery-evidence/upload",
    summary="Upload delivery evidence file (image/PDF)",
)
async def upload_evidence_file(
    shipment_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "update"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
    file: Annotated[UploadFile, File()],
    evidence_type: str = "pod",
    note: str | None = None,
) -> dict[str, Any]:
    from app.modules.procurement.storage import save_delivery_evidence

    url = await save_delivery_evidence(shipment_id=shipment_id, upload=file)
    return success(
        await service.add_delivery_evidence(
            user_id=auth.user_id,
            business=auth.business,
            shipment_id=shipment_id,
            payload={"evidence_type": evidence_type, "url": url, "note": note},
        )
    )


@router.get(
    "/shipments/{shipment_id}/delivery-evidence/files/{filename}",
    summary="Download delivery evidence (buyer/supplier on the order)",
)
async def download_evidence_file(
    shipment_id: str,
    filename: str,
    auth: Annotated[AuthContext, Depends(require_permission("shipments", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
):
    from fastapi.responses import FileResponse

    from app.modules.procurement.storage import resolve_evidence_path

    # Ensures the caller is buyer or supplier on this shipment's order.
    await service.get_shipment(
        user_id=auth.user_id, business=auth.business, shipment_id=shipment_id
    )
    path = resolve_evidence_path(shipment_id=shipment_id, filename=filename)
    return FileResponse(path, filename=filename)


@router.post("/shipments/{shipment_id}/receive", summary="Buyer records receiving")
async def receive_shipment(
    shipment_id: str,
    body: ReceiveShipmentRequest,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.receive_shipment(
            user_id=auth.user_id,
            business=auth.business,
            shipment_id=shipment_id,
            payload=body.model_dump(),
        )
    )


@router.post("/shipments/{shipment_id}/report-issue", summary="Open dispute from delivery issue")
async def report_shipment_issue(
    shipment_id: str,
    body: ReportIssueRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("disputes", "create"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    return success(
        await service.report_shipment_issue(
            user_id=auth.user_id,
            business=auth.business,
            shipment_id=shipment_id,
            reason=body.reason,
            description=body.description,
            ip=_ip(request),
        )
    )


@router.post(
    "/webhooks/tracking/{provider}",
    summary="Carrier tracking webhook (provider adapter)",
)
async def tracking_webhook(
    provider: str,
    body: dict[str, Any],
    request: Request,
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
) -> dict[str, Any]:
    import secrets as secrets_mod

    from app.core.config import get_settings
    from app.core.exceptions import ForbiddenError

    configured = get_settings().tracking_webhook_secret
    if configured is None or not configured.get_secret_value().strip():
        raise ForbiddenError("Tracking webhook is not configured")
    provided = request.headers.get("X-TradeBay-Webhook-Secret") or request.headers.get(
        "X-Webhook-Secret"
    )
    expected = configured.get_secret_value()
    if not provided or not secrets_mod.compare_digest(provided, expected):
        raise ForbiddenError("Invalid webhook secret")
    return success(await service.apply_tracking_webhook(provider_name=provider, payload=body))


@router.get("/purchase-orders/{order_id}/pdf", summary="Download purchase order PDF")
async def purchase_order_pdf(
    order_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("orders", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
):
    from fastapi.responses import Response

    data, filename = await service.purchase_order_pdf_bytes(
        business=auth.business, order_id=order_id
    )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/quotations/{quotation_id}/pdf", summary="Download quotation PDF")
async def quotation_pdf(
    quotation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("quotations", "read"))],
    service: Annotated[ProcurementService, Depends(get_procurement_service)],
):
    from fastapi.responses import Response

    data, filename = await service.quotation_pdf_bytes(
        user_id=auth.user_id, business=auth.business, quotation_id=quotation_id
    )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
