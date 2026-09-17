from app.db.collections import CollectionName
from app.shared.repositories.base import BaseRepository


class RFQRepository(BaseRepository):
    collection_name = CollectionName.RFQS


class RFQItemRepository(BaseRepository):
    collection_name = CollectionName.RFQ_ITEMS


class QuotationRepository(BaseRepository):
    collection_name = CollectionName.QUOTATIONS


class QuotationItemRepository(BaseRepository):
    collection_name = CollectionName.QUOTATION_ITEMS


class OrderRepository(BaseRepository):
    collection_name = CollectionName.ORDERS


class OrderItemRepository(BaseRepository):
    collection_name = CollectionName.ORDER_ITEMS


class ShipmentRepository(BaseRepository):
    collection_name = CollectionName.SHIPMENTS
