from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class NegotiationRepository(BaseRepository):
    collection_name = CollectionName.NEGOTIATIONS


class NegotiationOfferRepository(BaseRepository):
    collection_name = CollectionName.NEGOTIATION_OFFERS


class NegotiationOfferItemRepository(BaseRepository):
    collection_name = CollectionName.NEGOTIATION_OFFER_ITEMS
