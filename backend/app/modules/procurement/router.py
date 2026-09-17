"""Procurement API skeleton — not implemented."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.shared.http.skeleton import not_implemented

router = APIRouter(prefix="/rfqs", tags=["Procurement"])


@router.get("", summary="Procurement skeleton")
async def domain_skeleton() -> JSONResponse:
    return not_implemented("Procurement")
