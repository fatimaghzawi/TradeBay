from pydantic import BaseModel


class SettlementSummary(BaseModel):
    id: str
    batch_number: str
    status: str
