from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import AuthContext, get_current_user
from app.shared.schemas.response import paginated

router = APIRouter(tags=["Platform Money"])


@router.get("/commissions", summary="List commission records (scaffolded)")
async def list_commissions(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/payables", summary="List supplier payables (scaffolded)")
async def list_payables(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)


@router.get("/settlements", summary="List settlement batches (scaffolded)")
async def list_settlements(_: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    return paginated([], total=0)
