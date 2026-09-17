from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class DisputeRepository(BaseRepository):
    collection_name = CollectionName.DISPUTES


class NotificationRepository(BaseRepository):
    collection_name = CollectionName.NOTIFICATIONS


class ReviewRepository(BaseRepository):
    collection_name = CollectionName.REVIEWS
