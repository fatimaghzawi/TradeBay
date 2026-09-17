"""Replaceable email port. Identity never talks to a vendor SDK directly."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)

_SECRET_CONTEXT_KEYS = frozenset({"token", "otp", "password", "refresh_token", "access_token"})


class EmailSender(Protocol):
    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None: ...


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if key not in _SECRET_CONTEXT_KEYS}


class LogEmailSender:
    """Development sender. Never logs secrets or raw tokens."""

    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None:
        logger.info(
            "email_queued",
            to=to,
            template=template,
            context_keys=sorted(_safe_context(context).keys()),
        )


class MemoryEmailSender:
    """Test inbox. Tokens are stored in memory only — never returned by HTTP APIs."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None:
        self.messages.append({"to": to, "template": template, "context": dict(context)})
        logger.info(
            "email_queued",
            to=to,
            template=template,
            context_keys=sorted(_safe_context(context).keys()),
        )

    def last_token(self, *, to: str, template: str) -> str | None:
        for message in reversed(self.messages):
            if message["to"] == to and message["template"] == template:
                token = message["context"].get("token")
                return str(token) if token else None
        return None

    def clear(self) -> None:
        self.messages.clear()


_sender: EmailSender = LogEmailSender()


def get_email_sender() -> EmailSender:
    return _sender


def set_email_sender(sender: EmailSender) -> None:
    global _sender
    _sender = sender
