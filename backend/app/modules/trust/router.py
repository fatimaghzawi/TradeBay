from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.response import paginated

router = APIRouter(tags=["Trust"])


@router.get("/reviews", summary="List reviews (scaffolded)")
async def list_reviews(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/disputes", summary="List disputes (scaffolded)")
async def list_disputes(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/notifications", summary="List notifications (scaffolded)")
async def list_notifications(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)
