from pydantic import BaseModel


class RFQSummary(BaseModel):
    id: str
    rfq_number: str
    title: str
    status: str


class OrderSummary(BaseModel):
    id: str
    order_number: str
    status: str
