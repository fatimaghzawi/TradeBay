from app.modules.finance.service import InvoiceService


def get_invoice_service() -> InvoiceService:
    return InvoiceService()
