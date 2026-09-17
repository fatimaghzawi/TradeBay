from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class BusinessPlanRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLANS


class BusinessPlanItemRepository(BaseRepository):
    collection_name = CollectionName.BUSINESS_PLAN_ITEMS


class PriceEstimateRepository(BaseRepository):
    collection_name = CollectionName.PRICE_ESTIMATES
