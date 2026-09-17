from app.db.collections import CollectionName
from app.shared.repositories.base import AppendOnlyRepository, BaseRepository


class InvoiceRepository(BaseRepository):
    collection_name = CollectionName.CUSTOMER_INVOICES


class PaymentRepository(BaseRepository):
    collection_name = CollectionName.PAYMENTS


class CreditNoteRepository(BaseRepository):
    collection_name = CollectionName.CREDIT_NOTES


class RefundRepository(BaseRepository):
    collection_name = CollectionName.REFUNDS


class FinancialTransactionRepository(AppendOnlyRepository):
    collection_name = CollectionName.FINANCIAL_TRANSACTIONS
