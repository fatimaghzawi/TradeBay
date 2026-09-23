"""AI Sourcing API — buyer requirement extraction, recommendations, draft requests."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.ai_sourcing.schemas import (
    AnalyzeSourcingRequest,
    ConfirmRequirementsRequest,
    CreateSourcingDraftRequest,
    RecommendRequest,
)
from app.modules.ai_sourcing.service import AISourcingService
from app.modules.identity.dependencies import AuthContext, require_permission
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(prefix="/ai-sourcing", tags=["AI Sourcing"])


def get_ai_sourcing_service() -> AISourcingService:
    return AISourcingService()


@router.post("/analyze", summary="Extract procurement requirements from buyer description")
async def analyze_description(
    body: AnalyzeSourcingRequest,
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "create"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.analyze(
            user_id=auth.user_id,
            business=auth.business,
            business_description=body.business_description,
        )
    )


@router.post("/requirements/confirm", summary="Confirm or edit extracted requirements")
async def confirm_requirements(
    body: ConfirmRequirementsRequest,
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "create"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.confirm_requirements(
            user_id=auth.user_id,
            business=auth.business,
            sourcing_request_id=body.sourcing_request_id,
            requirements=body.requirements,
        )
    )


@router.post("/recommendations", summary="Match confirmed requirements to TradeBay catalog")
async def generate_recommendations(
    body: RecommendRequest,
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "read"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.recommend(
            business=auth.business,
            sourcing_request_id=body.sourcing_request_id,
            limit=body.limit,
        )
    )


@router.post("/create-request", summary="Create a DRAFT sourcing request from confirmed needs")
async def create_sourcing_request(
    body: CreateSourcingDraftRequest,
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "create"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.create_draft_request(
            business=auth.business,
            sourcing_request_id=body.sourcing_request_id,
        )
    )


@router.get("/profile", summary="Get buyer procurement profile")
async def get_procurement_profile(
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "read"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(await service.get_profile(business=auth.business))


@router.get("/requests", summary="List sourcing requests for active business")
async def list_sourcing_requests(
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "read"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_requests(
        business=auth.business,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/requests/{sourcing_request_id}", summary="Get sourcing request detail")
async def get_sourcing_request(
    sourcing_request_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("sourcing", "read"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.get_request(
            business=auth.business,
            sourcing_request_id=sourcing_request_id,
        )
    )


@router.post(
    "/requests/{sourcing_request_id}/convert-to-rfq",
    summary="Create draft RFQ from sourcing request",
)
async def convert_sourcing_to_rfq(
    sourcing_request_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[AISourcingService, Depends(get_ai_sourcing_service)],
) -> dict[str, Any]:
    return success(
        await service.convert_to_rfq(
            user_id=auth.user_id,
            business=auth.business,
            sourcing_request_id=sourcing_request_id,
        )
    )
