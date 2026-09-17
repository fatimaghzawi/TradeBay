from app.db.collections import CollectionName
from app.shared.repositories.base import AppendOnlyRepository, BaseRepository


class ProductRepository(BaseRepository):
    collection_name = CollectionName.PRODUCTS


class CategoryRepository(BaseRepository):
    collection_name = CollectionName.CATEGORIES


class ProductPriceRepository(BaseRepository):
    collection_name = CollectionName.PRODUCT_PRICES


class ProductImageRepository(BaseRepository):
    collection_name = CollectionName.PRODUCT_IMAGES


class InventoryRepository(BaseRepository):
    collection_name = CollectionName.INVENTORIES


class InventoryTransactionRepository(AppendOnlyRepository):
    collection_name = CollectionName.INVENTORY_TRANSACTIONS
