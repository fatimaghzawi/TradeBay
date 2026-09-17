"""Communication document shapes.

ERD §14. Messaging is a general capability between two companies, not a negotiation
feature: a thread may have no commercial context at all, and a negotiation may have no
thread. A message is never a commercial record — offers and prices live on
`quotations`, `quotation_items` and `negotiation_offers`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.shared.types.document import MongoDocument, MongoEmbedded
from app.shared.types.ids import DocumentId, OptionalDocumentId


class ConversationDocument(MongoDocument):
    """A two-company thread.

    `last_message_at`, `last_message_preview` and `message_count` are denormalized for
    inbox sorting only; `messages` stays the source of truth and a rebuild from it alone
    must always be possible.
    """

    subject: str | None = None
    type: str
    context_type: str | None = None
    context_id: OptionalDocumentId = None
    initiator_business_id: DocumentId
    counterparty_business_id: DocumentId
    created_by_user_id: DocumentId
    status: str
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationParticipantDocument(MongoDocument):
    """Per-user thread state.

    Read position, mute and leave are per person, so they cannot live on `conversations`
    (which has no user) or on `messages` (which would need a write per reader).
    """

    conversation_id: DocumentId
    user_id: DocumentId
    business_account_id: DocumentId
    role: str
    last_read_at: datetime | None = None
    is_muted: bool = False
    joined_at: datetime | None = None
    left_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MessageAttachmentEmbedded(MongoEmbedded):
    url: str
    file_name: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_at: datetime | None = None


class MessageDocument(MongoDocument):
    """Never hard-deleted: edit sets `edited_at`, removal sets `deleted_at` and blanks body.

    SYSTEM messages are written by the platform from domain events and have no sender.
    """

    conversation_id: DocumentId
    sender_user_id: OptionalDocumentId = None
    sender_business_id: OptionalDocumentId = None
    message_type: str
    body: str | None = None
    attachments: list[MessageAttachmentEmbedded] = Field(default_factory=list)
    reply_to_message_id: OptionalDocumentId = None
    reference_type: str | None = None
    reference_id: OptionalDocumentId = None
    system_event: str | None = None
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
