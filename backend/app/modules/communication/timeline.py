"""Post BRD FR-MSG-09 system timeline events into contextual conversations."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.communication.service import CommunicationService

logger = get_logger(__name__)


async def post_thread_system_event(
    *,
    context_type: str,
    context_id: str | Any,
    system_event: str,
    body: str,
    initiator_business_id: str | Any | None = None,
    counterparty_business_id: str | Any | None = None,
    subject: str | None = None,
) -> None:
    """Best-effort: never fail the commercial action if messaging is unavailable."""
    try:
        await CommunicationService().post_system_event(
            context_type=context_type,
            context_id=str(context_id),
            system_event=system_event,
            body=body,
            initiator_business_id=str(initiator_business_id) if initiator_business_id else None,
            counterparty_business_id=str(counterparty_business_id)
            if counterparty_business_id
            else None,
            subject=subject,
        )
    except Exception as exc:
        logger.warning("thread_system_event_failed", event=system_event, error=str(exc))
