from datetime import datetime

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: str
    business_account_id: str
    type: str
    status: str
    rfq_id: str | None = None
    created_at: datetime | None = None


class MessageSummary(BaseModel):
    id: str
    conversation_id: str
    message_type: str
    content: str | None = None
    created_at: datetime | None = None


class ConversationCreatePlaceholder(BaseModel):
    """Request shape reserved for later — not wired to a service."""

    business_account_id: str
    type: str = "NORMAL"
    rfq_id: str | None = None
