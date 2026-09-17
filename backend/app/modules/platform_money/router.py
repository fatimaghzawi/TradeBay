"""Platform Money API skeleton — not implemented."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.shared.http.skeleton import not_implemented

router = APIRouter(prefix="/commissions", tags=["Platform Money"])


@router.get("", summary="Platform Money skeleton")
async def domain_skeleton() -> JSONResponse:
    return not_implemented("Platform Money")
