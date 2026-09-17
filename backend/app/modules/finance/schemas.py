from pydantic import BaseModel


class InvoiceSummary(BaseModel):
    id: str
    invoice_number: str
    status: str
