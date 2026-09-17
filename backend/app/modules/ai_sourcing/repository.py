from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class SourcingRequestRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_REQUESTS


class SourcingRequestItemRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_REQUEST_ITEMS


class SourcingRecommendationRepository(BaseRepository):
    collection_name = CollectionName.SOURCING_RECOMMENDATIONS
