from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.ai.dependencies import get_ai_provider
from app.modules.ai.provider import AIProvider
from app.modules.ai.recommendations.service import RecommendationService
from app.modules.ai.sourcing_assistant.schemas import SourcingRequest
from app.modules.ai.sourcing_assistant.service import SourcingAssistantService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.response import success

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/sourcing", summary="Non-persistent sourcing preview (not a commercial record)")
async def sourcing(
    body: SourcingRequest,
    _: Annotated[AuthContext, Depends(get_current_user)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
) -> dict[str, Any]:
    result = await SourcingAssistantService(provider).suggest(query=body.query)
    return success(result)


@router.get("/recommendations", summary="Personalized recommendations (non-authoritative)")
async def recommendations(
    _: Annotated[AuthContext, Depends(get_current_user)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
    limit: int = 10,
) -> dict[str, Any]:
    result = await RecommendationService(provider).recommend(limit=limit)
    return success(result)
