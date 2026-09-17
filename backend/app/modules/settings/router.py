from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.settings.service import SettingsService
from app.shared.schemas.response import success

router = APIRouter(prefix="/settings", tags=["Settings"])


def get_settings_service() -> SettingsService:
    return SettingsService()


@router.get("/platform", summary="Platform settings singleton")
async def get_platform_settings(
    _: Annotated[AuthContext, Depends(require_permission("settings", "manage"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(await service.get_platform_settings())


@router.get("/tax", summary="Active VAT rate")
async def get_active_tax(
    _: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(await service.get_active_tax())


@router.get("/letterhead", summary="Platform invoice letterhead")
async def get_letterhead(
    _: Annotated[AuthContext, Depends(require_permission("invoices", "read"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(await service.get_letterhead())
