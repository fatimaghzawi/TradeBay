"""Communication API placeholders — no messaging implementation."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.modules.communication.dependencies import get_conversation_service, get_message_service
from app.modules.communication.service import ConversationService, MessageService
from app.modules.identity.dependencies import AuthContext, get_current_user
from app.modules.identity.exceptions import BusinessContextRequiredError
from app.shared.schemas.pagination import PaginationParams
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Communication"])


@router.get("/conversations", summary="List conversations (scaffolded)")
async def list_conversations(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    if not auth.business_id:
        raise BusinessContextRequiredError()
    items, total = await service.list_conversations(
        PaginationParams(page=page, page_size=page_size),
        business_id=auth.business_id,
    )
    data = [
        {
            "id": str(i["_id"]),
            "initiator_business_id": str(i.get("initiator_business_id", "")),
            "counterparty_business_id": str(i.get("counterparty_business_id", "")),
            "type": i.get("type"),
            "status": i.get("status"),
            "context_type": i.get("context_type"),
            "context_id": str(i["context_id"]) if i.get("context_id") else None,
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)


@router.get("/conversations/{conversation_id}", summary="Get conversation (scaffolded)")
async def get_conversation(
    conversation_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
    return success({"id": conversation_id, "status": "scaffold", "messages": []})


@router.get(
    "/conversations/{conversation_id}/messages",
    summary="List messages (scaffolded)",
)
async def list_messages(
    conversation_id: str,
    _: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[MessageService, Depends(get_message_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    items, total = await service.list_for_conversation(
        conversation_id, PaginationParams(page=page, page_size=page_size)
    )
    data = [
        {
            "id": str(i["_id"]),
            "message_type": i.get("message_type"),
            "body": i.get("body"),
        }
        for i in items
    ]
    return paginated(data, page=page, page_size=page_size, total=total)
