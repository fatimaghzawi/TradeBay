"""AI API skeleton — not implemented."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.shared.http.skeleton import not_implemented

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("", summary="AI skeleton")
async def domain_skeleton() -> JSONResponse:
    return not_implemented("AI")
