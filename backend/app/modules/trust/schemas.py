from pydantic import BaseModel


class NotificationSummary(BaseModel):
    id: str
    title: str
    is_read: bool
