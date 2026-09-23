"""Communication HTTP API — BRD §8.7 poll inbox and messages (v1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.communication.constants import MessageType
from app.modules.communication.service import CommunicationService
from app.modules.identity.dependencies import AuthContext, require_permission
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(prefix="/conversations", tags=["Communication"])


def get_communication_service() -> CommunicationService:
    return CommunicationService()


class OpenConversationRequest(BaseModel):
    counterparty_business_id: str = Field(min_length=24, max_length=24)
    type: str = "DIRECT"
    context_type: str | None = None
    context_id: str | None = None
    subject: str | None = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    body: str | None = Field(default=None, max_length=8000)
    message_type: str = MessageType.TEXT
    reply_to_message_id: str | None = Field(default=None, min_length=24, max_length=24)
    reference_type: str | None = None
    reference_id: str | None = Field(default=None, min_length=24, max_length=24)


class EditMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


@router.get("", summary="List conversations for the active business")
async def list_conversations(
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "read"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict[str, Any]:
    items, total = await service.list_inbox(
        user_id=auth.user_id,
        business=auth.business,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/unread-count", summary="Unread message count for the navbar")
async def unread_conversation_count(
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "read"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        {
            "count": await service.unread_inbox_count(
                user_id=auth.user_id,
                business=auth.business,
            )
        }
    )


@router.post("", summary="Open or resume a two-company conversation")
async def open_conversation(
    body: OpenConversationRequest,
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "create"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.open_or_get(
            user_id=auth.user_id,
            business=auth.business,
            counterparty_business_id=body.counterparty_business_id,
            type_=body.type,
            context_type=body.context_type,
            context_id=body.context_id,
            subject=body.subject,
        )
    )


@router.get("/{conversation_id}", summary="Get conversation detail")
async def get_conversation(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "read"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.get(
            user_id=auth.user_id,
            business=auth.business,
            conversation_id=conversation_id,
            mark_read=True,
        )
    )


@router.post("/{conversation_id}/read", summary="Mark conversation read (FR-MSG-06)")
async def mark_conversation_read(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "read"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.mark_read(
            user_id=auth.user_id,
            business=auth.business,
            conversation_id=conversation_id,
        )
    )


@router.get("/{conversation_id}/messages", summary="List messages (poll)")
async def list_messages(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("conversations", "read"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    after: Annotated[str | None, Query(description="ISO timestamp cursor for incremental poll")] = None,
) -> dict[str, Any]:
    items, total = await service.list_messages(
        user_id=auth.user_id,
        business=auth.business,
        conversation_id=conversation_id,
        page=pagination.page,
        page_size=pagination.page_size,
        after=after,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("/{conversation_id}/messages", summary="Send a message")
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    auth: Annotated[AuthContext, Depends(require_permission("messages", "create"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.send_message(
            user_id=auth.user_id,
            business=auth.business,
            conversation_id=conversation_id,
            body=body.body,
            message_type=body.message_type,
            reply_to_message_id=body.reply_to_message_id,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        )
    )


@router.patch("/{conversation_id}/messages/{message_id}", summary="Edit own text message")
async def edit_message(
    conversation_id: str,
    message_id: str,
    body: EditMessageRequest,
    auth: Annotated[AuthContext, Depends(require_permission("messages", "create"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.edit_message(
            user_id=auth.user_id,
            business=auth.business,
            conversation_id=conversation_id,
            message_id=message_id,
            body=body.body,
        )
    )


@router.delete("/{conversation_id}/messages/{message_id}", summary="Soft-delete own message")
async def delete_message(
    conversation_id: str,
    message_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("messages", "create"))],
    service: Annotated[CommunicationService, Depends(get_communication_service)],
) -> dict[str, Any]:
    return success(
        await service.soft_delete_message(
            user_id=auth.user_id,
            business=auth.business,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    )
