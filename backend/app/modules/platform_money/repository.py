from app.db.collections import CollectionName
from app.shared.repositories.base import AppendOnlyRepository, BaseRepository


class CommissionRepository(BaseRepository):
    collection_name = CollectionName.COMMISSION_RECORDS


class PayableRepository(BaseRepository):
    collection_name = CollectionName.SUPPLIER_PAYABLES


SupplierPayableRepository = PayableRepository


class SupplierPayoutRepository(BaseRepository):
    collection_name = CollectionName.SUPPLIER_PAYOUTS


class SettlementRepository(BaseRepository):
    collection_name = CollectionName.SETTLEMENT_BATCHES


class PlatformTransactionRepository(AppendOnlyRepository):
    collection_name = CollectionName.PLATFORM_TRANSACTIONS
