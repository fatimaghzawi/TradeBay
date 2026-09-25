
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.business_planner.guest import get_planner_owner_id
from app.modules.business_planner.schemas import (
    AssistantRequest,
    PatchPlanRequest,
    RegeneratePlanRequest,
    SubmitAnswersRequest,
)
from app.modules.business_planner.service import BusinessPlannerService
from app.modules.identity.dependencies import AuthContext, get_current_user, require_permission
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

planner_router = APIRouter(prefix="/business-planner", tags=["Business Planner"])
plans_router = APIRouter(prefix="/business-plans", tags=["Business Planner"])

                                                        
router = planner_router

def get_business_planner_service() -> BusinessPlannerService:
    return BusinessPlannerService()

@planner_router.post("/sessions", summary="Start a business planner discovery session")
async def create_session(
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.create_session(user_id=owner_id))

@planner_router.get("/sessions/{session_id}", summary="Get a planner discovery session")
async def get_session(
    session_id: str,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.get_session(user_id=owner_id, session_id=session_id))

@planner_router.post("/sessions/{session_id}/answers", summary="Submit discovery step answers")
async def submit_answers(
    session_id: str,
    body: SubmitAnswersRequest,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(
        await service.submit_answers(
            user_id=owner_id,
            session_id=session_id,
            step=body.step,
            answers=body.answers,
        )
    )

@planner_router.post(
    "/sessions/{session_id}/next-questions",
    summary="Get adaptive AI follow-up questions",
)
async def next_questions(
    session_id: str,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.next_questions(user_id=owner_id, session_id=session_id))

@planner_router.post(
    "/sessions/{session_id}/generate",
    summary="Analyze marketplace and generate a structured business plan",
)
async def generate_plan(
    session_id: str,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.generate_from_session(user_id=owner_id, session_id=session_id))

@plans_router.get("", summary="List my business plans")
async def list_plans(
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_plans(
        user_id=owner_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)

@plans_router.get("/{plan_id}", summary="Get business plan dashboard payload")
async def get_plan(
    plan_id: str,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.get_plan(user_id=owner_id, plan_id=plan_id))

@plans_router.patch("/{plan_id}", summary="Update plan title, milestones, or preferences")
async def patch_plan(
    plan_id: str,
    body: PatchPlanRequest,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(
        await service.patch_plan(
            user_id=owner_id,
            plan_id=plan_id,
            title=body.title,
            milestone_updates=body.milestone_updates,
            preferences=body.preferences,
        )
    )

@plans_router.post("/{plan_id}/regenerate", summary="Regenerate a new plan version")
async def regenerate_plan(
    plan_id: str,
    body: RegeneratePlanRequest,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(
        await service.regenerate(
            user_id=owner_id,
            plan_id=plan_id,
            preferences=body.preferences,
            reason=body.reason,
        )
    )

@plans_router.post("/{plan_id}/assistant", summary="Plan-aware AI assistant")
async def plan_assistant(
    plan_id: str,
    body: AssistantRequest,
    owner_id: Annotated[str, Depends(get_planner_owner_id)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(
        await service.assistant(user_id=owner_id, plan_id=plan_id, message=body.message)
    )

@plans_router.post("/{plan_id}/sourcing-draft", summary="Create AI Sourcing draft from plan")
async def sourcing_draft(
    plan_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.create_sourcing_draft(user_id=auth.user_id, plan_id=plan_id))

@plans_router.post("/{plan_id}/rfq-preview", summary="Prepare RFQ draft payload (no publish)")
async def rfq_preview(
    plan_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(await service.rfq_preview(user_id=auth.user_id, plan_id=plan_id))

@plans_router.post("/{plan_id}/convert-to-rfq", summary="Create draft RFQ from business plan")
async def convert_plan_to_rfq(
    plan_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("rfqs", "create"))],
    service: Annotated[BusinessPlannerService, Depends(get_business_planner_service)],
) -> dict[str, Any]:
    return success(
        await service.convert_to_rfq(
            user_id=auth.user_id, plan_id=plan_id, business=auth.business
        )
    )
