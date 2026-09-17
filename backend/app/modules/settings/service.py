"""Settings application service — reads configuration; snapshots live on documents."""

from __future__ import annotations

from typing import Any

from app.modules.settings.constants import SINGLETON_KEY
from app.modules.settings.repository import (
    BusinessSettingsRepository,
    PlatformSettingsRepository,
    TaxSettingsRepository,
)


class SettingsService:
    def __init__(
        self,
        platform: PlatformSettingsRepository | None = None,
        tax: TaxSettingsRepository | None = None,
        letterhead: BusinessSettingsRepository | None = None,
    ) -> None:
        self.platform = platform or PlatformSettingsRepository()
        self.tax = tax or TaxSettingsRepository()
        self.letterhead = letterhead or BusinessSettingsRepository()

    async def get_platform_settings(self) -> dict[str, Any] | None:
        return await self.platform.find_one({"key": SINGLETON_KEY})

    async def get_active_tax(self) -> dict[str, Any] | None:
        return await self.tax.find_one({"is_active": True})

    async def get_letterhead(self) -> dict[str, Any] | None:
        return await self.letterhead.find_one({"key": SINGLETON_KEY})
