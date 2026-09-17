from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class PlatformSettingsRepository(BaseRepository):
    collection_name = CollectionName.PLATFORM_SETTINGS


class TaxSettingsRepository(BaseRepository):
    collection_name = CollectionName.TAX_SETTINGS


class BusinessSettingsRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_SETTINGS
