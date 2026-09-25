
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.modules.identity.dependencies import AuthContext, require_permission
from app.modules.trust.notifications import NotificationService
from app.shared.schemas.pagination import PaginationParams, get_pagination
from app.shared.schemas.response import paginated, success

router = APIRouter(tags=["Notifications"])

def get_notification_service() -> NotificationService:
    return NotificationService()

@router.get("/notifications", summary="List my in-app notifications")
async def list_notifications(
    auth: Annotated[AuthContext, Depends(require_permission("notifications", "read"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    unread_only: bool = False,
) -> dict[str, Any]:
    items, total = await service.list_for_user(
        user_id=auth.user_id,
        unread_only=unread_only,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return paginated(items, page=pagination.page, page_size=pagination.page_size, total=total)

@router.get("/notifications/unread-count", summary="Unread notification count")
async def unread_notification_count(
    auth: Annotated[AuthContext, Depends(require_permission("notifications", "read"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict[str, Any]:
    return success({"count": await service.unread_count(user_id=auth.user_id)})

@router.post("/notifications/{notification_id}/read", summary="Mark one notification read")
async def mark_notification_read(
    notification_id: str,
    auth: Annotated[AuthContext, Depends(require_permission("notifications", "read"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict[str, Any]:
    return success(
        await service.mark_read(user_id=auth.user_id, notification_id=notification_id)
    )

@router.post("/notifications/read-all", summary="Mark all my notifications read")
async def mark_all_notifications_read(
    auth: Annotated[AuthContext, Depends(require_permission("notifications", "read"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict[str, Any]:
    return success(await service.mark_all_read(user_id=auth.user_id))
