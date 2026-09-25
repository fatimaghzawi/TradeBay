
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.settings.schemas import (
    UpdateBusinessSettingsRequest,
    UpdatePlatformSettingsRequest,
    UpdateTaxSettingsRequest,
)
from app.modules.settings.service import SettingsService
from app.shared.schemas.response import success

router = APIRouter(prefix="/admin/settings", tags=["System Settings"])

def get_settings_service() -> SettingsService:
    return SettingsService()

@router.get("", summary="Get all system settings (platform admin)")
async def get_settings(
    auth: Annotated[AuthContext, Depends(require_permission("settings", "manage"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(await service.get_all(business=auth.business))

@router.patch("/platform", summary="Update platform settings")
async def update_platform(
    body: UpdatePlatformSettingsRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settings", "manage"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(
        await service.update_platform(
            user_id=auth.user_id,
            business=auth.business,
            payload=body.model_dump(exclude_unset=True),
        )
    )

@router.patch("/tax", summary="Update tax / VAT settings")
async def update_tax(
    body: UpdateTaxSettingsRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settings", "manage"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    return success(
        await service.update_tax(
            user_id=auth.user_id,
            business=auth.business,
            payload=body.model_dump(exclude_unset=True),
        )
    )

@router.patch("/business", summary="Update business letterhead / invoice prefix")
async def update_business(
    body: UpdateBusinessSettingsRequest,
    auth: Annotated[AuthContext, Depends(require_permission("settings", "manage"))],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    if "address" in payload and payload["address"] is not None:
        payload["address"] = body.address.model_dump() if body.address else None
    return success(
        await service.update_business(
            user_id=auth.user_id,
            business=auth.business,
            payload=payload,
        )
    )
