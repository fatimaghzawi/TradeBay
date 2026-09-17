"""Replaceable email port. Identity never talks to a vendor SDK in domain services.

Default production path: Elastic Email transactional API (same as WorkNest).
Tests use MemoryEmailSender. Local runs without a key use LogEmailSender.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SECRET_CONTEXT_KEYS = frozenset({"token", "otp", "password", "refresh_token", "access_token"})
_ELASTIC_URL = "https://api.elasticemail.com/v4/emails/transactional"


class EmailSender(Protocol):
    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None: ...


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if key not in _SECRET_CONTEXT_KEYS}


def _parse_from_address(from_header: str) -> tuple[str | None, str]:
    stripped = from_header.strip()
    if "<" in stripped and stripped.endswith(">"):
        name, _, rest = stripped.partition("<")
        return name.strip() or None, rest[:-1].strip()
    return None, stripped


def _frontend_link(settings: Settings, path: str, token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}{path}?token={quote(token, safe='')}"


def _wrap_html(*, title: str, body: str, app_name: str) -> str:
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Segoe UI,Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:12px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 8px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">{escape(app_name)}</p>
          <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;">{escape(title)}</h1>
          {body}
          <p style="margin:28px 0 0;font-size:12px;color:#94a3b8;">© {year} {escape(app_name)}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _button(url: str, label: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;">
  <tr><td style="background:#0f766e;border-radius:8px;">
    <a href="{escape(url)}" style="display:inline-block;padding:12px 22px;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;">{escape(label)}</a>
  </td></tr>
</table>
<p style="margin:0;font-size:12px;color:#64748b;word-break:break-all;">Or paste this link:<br /><a href="{escape(url)}" style="color:#0f766e;">{escape(url)}</a></p>"""


def render_message(*, template: str, context: dict[str, Any], settings: Settings) -> tuple[str, str, str]:
    """Return (subject, html, text)."""
    app_name = settings.app_name
    token = str(context.get("token") or "")
    if template == "email_verification":
        url = _frontend_link(settings, "/verify-email", token)
        subject = f"Verify your {app_name} email"
        html = _wrap_html(
            title="Verify your email",
            app_name=app_name,
            body=(
                f"<p style='margin:0 0 12px;line-height:1.6;'>Welcome to {escape(app_name)}. "
                "Confirm your email to unlock commercial actions.</p>"
                f"{_button(url, 'Verify email')}"
                "<p style='margin:16px 0 0;font-size:13px;color:#64748b;'>This link expires and can only be used once.</p>"
            ),
        )
        text = f"Verify your {app_name} email:\n{url}\n"
        return subject, html, text

    if template == "password_reset":
        url = _frontend_link(settings, "/reset-password", token)
        subject = f"Reset your {app_name} password"
        html = _wrap_html(
            title="Reset your password",
            app_name=app_name,
            body=(
                f"<p style='margin:0 0 12px;line-height:1.6;'>We received a request to reset your {escape(app_name)} password.</p>"
                f"{_button(url, 'Choose a new password')}"
                "<p style='margin:16px 0 0;font-size:13px;color:#64748b;'>If you did not request this, you can ignore this email.</p>"
            ),
        )
        text = f"Reset your {app_name} password:\n{url}\n"
        return subject, html, text

    if template == "invitation":
        url = _frontend_link(settings, "/accept-invitation", token)
        business = escape(str(context.get("business_name") or "a TradeBay business"))
        role = escape(str(context.get("role_name") or "a role"))
        subject = f"You're invited to {app_name}"
        html = _wrap_html(
            title="Business invitation",
            app_name=app_name,
            body=(
                f"<p style='margin:0 0 12px;line-height:1.6;'>You have been invited to join <strong>{business}</strong> "
                f"as <strong>{role}</strong>.</p>"
                f"{_button(url, 'Accept invitation')}"
                "<p style='margin:16px 0 0;font-size:13px;color:#64748b;'>Sign in with this email address before accepting.</p>"
            ),
        )
        text = f"You are invited to join {context.get('business_name')} as {context.get('role_name')}.\n{url}\n"
        return subject, html, text

    subject = f"{app_name} notification"
    html = _wrap_html(title=subject, app_name=app_name, body="<p>You have a new TradeBay notification.</p>")
    return subject, html, subject


class LogEmailSender:
    """Development sender when no provider is configured. Never logs secrets."""

    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None:
        logger.info(
            "email_queued",
            to=to,
            template=template,
            provider="log",
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
            provider="memory",
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


class ElasticEmailSender:
    """WorkNest-compatible Elastic Email v4 transactional API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def send(self, *, to: str, template: str, context: dict[str, Any]) -> None:
        api_key = self.settings.elasticemail_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise RuntimeError("ELASTICEMAIL_API_KEY is not configured")

        subject, html, text = render_message(template=template, context=context, settings=self.settings)
        from_name, from_email = _parse_from_address(self.settings.email_from)
        from_header = f"{from_name} <{from_email}>" if from_name else from_email

        payload = {
            "Recipients": {"To": [to]},
            "Content": {
                "From": from_header,
                "Subject": subject,
                "Body": [
                    {"ContentType": "HTML", "Charset": "utf-8", "Content": html},
                    {"ContentType": "PlainText", "Charset": "utf-8", "Content": text},
                ],
            },
        }

        timeout = httpx.Timeout(self.settings.email_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _ELASTIC_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-ElasticEmail-ApiKey": api_key.get_secret_value(),
                },
                json=payload,
            )

        if response.status_code >= 400:
            logger.error(
                "elastic_email_failed",
                status=response.status_code,
                to=to,
                template=template,
            )
            raise RuntimeError(f"Elastic Email API error ({response.status_code})")

        message_id = "unknown"
        try:
            body = response.json()
            message_id = str(body.get("TransactionID") or body.get("MessageID") or "unknown")
        except Exception:
            pass

        logger.info(
            "email_sent",
            provider="elasticemail",
            to=to,
            template=template,
            message_id=message_id,
            context_keys=sorted(_safe_context(context).keys()),
        )


_sender: EmailSender = LogEmailSender()


def get_email_sender() -> EmailSender:
    return _sender


def set_email_sender(sender: EmailSender) -> None:
    global _sender
    _sender = sender


def configure_email_sender(settings: Settings | None = None) -> EmailSender:
    """Pick the outbound provider from settings. Tests override via set_email_sender."""
    settings = settings or get_settings()
    if settings.is_test:
        sender: EmailSender = LogEmailSender()
    elif settings.elasticemail_api_key and settings.elasticemail_api_key.get_secret_value().strip():
        sender = ElasticEmailSender(settings)
        logger.info("email_provider_configured", provider="elasticemail", from_address=settings.email_from)
    else:
        sender = LogEmailSender()
        logger.info("email_provider_configured", provider="log")
    set_email_sender(sender)
    return sender
