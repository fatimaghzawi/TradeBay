"""Replaceable email port. Identity never talks to a vendor SDK in domain services.

Default production path: Elastic Email transactional API (same as WorkNest).
Tests use MemoryEmailSender. Local runs without a key use LogEmailSender.
"""

from __future__ import annotations

import time
from datetime import datetime
from html import escape
from typing import Any, Protocol
from urllib.parse import quote, urlparse

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SECRET_CONTEXT_KEYS = frozenset({"token", "otp", "password", "refresh_token", "access_token"})
_ELASTIC_URL = "https://api.elasticemail.com/v4/emails/transactional"
_quota_blocked_until: float = 0.0
_QUOTA_COOLDOWN_SECONDS = 30 * 60


class EmailQuotaExhaustedError(RuntimeError):
    """Elastic Email (or similar) refused send because the plan has no credits."""


def elastic_quota_exhausted(status_code: int, body: str) -> bool:
    if status_code != 400:
        return False
    text = (body or "").lower()
    return any(
        token in text
        for token in (
            "no_credits",
            "daily email credits",
            "free daily email",
            "not enough credits",
        )
    )

# TradeBay brand (aligned with auth / landing UI)
_CREAM = "#faf8f4"
_GREEN = "#0d3b2a"
_GREEN_MID = "#1a6b4f"
_ORANGE = "#e86f2a"
_ORANGE_DEEP = "#c45b2a"
_TEXT = "#15241d"
_MUTED = "#5a6a62"
_BORDER = "#d9e2dc"
_WHITE = "#ffffff"


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


def _frontend_link(settings: Settings, path: str, token: str = "", **query: str) -> str:
    base = settings.frontend_url.rstrip("/")
    params: list[str] = []
    if token:
        params.append(f"token={quote(token, safe='')}")
    for key, value in query.items():
        if value:
            params.append(f"{quote(key, safe='')}={quote(value, safe='')}")
    qs = f"?{'&'.join(params)}" if params else ""
    return f"{base}{path}{qs}"


def _is_insecure_app_url(url: str) -> bool:
    """Gmail Safe Browsing flags localhost and plain-http links as phishing."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return True
    return parsed.scheme.lower() != "https"


def _cta_html(url: str, label: str, *, tone: str = "orange", omit_insecure_links: bool = False) -> str:
    if omit_insecure_links and _is_insecure_app_url(url):
        return (
            f"<p style='margin:20px 0 0;font-size:14px;line-height:1.6;color:{_MUTED};'>"
            f"Open <strong style='color:{_TEXT};'>TradeBay</strong> in your browser to continue.</p>"
        )
    return _button(url, label, tone=tone)


def _invite_cta_html(url: str, *, omit_insecure_links: bool = False) -> str:
    """Invites need the token. Local/http URLs are shown as copy-paste, not <a href>."""
    if omit_insecure_links and _is_insecure_app_url(url):
        escaped = escape(url)
        return (
            f"<p style='margin:20px 0 8px;font-size:14px;line-height:1.6;color:{_MUTED};'>"
            f"Copy this address into your browser to accept:</p>"
            f"<p style='margin:0;padding:12px 14px;background:{_CREAM};border:1px solid {_BORDER};"
            f"border-radius:12px;font-size:13px;line-height:1.5;color:{_TEXT};word-break:break-all;'>"
            f"{escaped}</p>"
        )
    return _button(url, "Accept invitation", tone="green")


def _wordmark() -> str:
    return (
        f'<p style="margin:0;font-size:30px;line-height:1;font-weight:800;letter-spacing:-0.04em;'
        f'color:{_GREEN};font-family:Georgia,\'Times New Roman\',serif;">'
        f'Trade<span style="color:{_ORANGE};">Bay</span></p>'
    )


def _brand_header(settings: Settings, *, embedded_logo: bool = False) -> str:
    """Always use a styled wordmark — never attach/embed logo images (clients treat them as files)."""
    del settings, embedded_logo
    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;">
        <tr>
          <td>
            {_wordmark()}
            <p style="margin:10px 0 0;font-size:11px;letter-spacing:0.28em;text-transform:uppercase;
              color:{_MUTED};font-weight:600;">Source · Connect · Grow</p>
          </td>
        </tr>
      </table>
    """


def _petal_bar() -> str:
    """Decorative leaf strip echoing auth wave accents."""
    return f"""
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
          <td style="width:28px;height:10px;border-radius:999px;background:{_GREEN};"></td>
          <td style="width:8px;"></td>
          <td style="width:22px;height:10px;border-radius:999px;background:{_ORANGE};"></td>
          <td style="width:8px;"></td>
          <td style="width:16px;height:10px;border-radius:999px;background:{_ORANGE_DEEP};opacity:0.85;"></td>
        </tr>
      </table>
    """


def _wrap_html(
    *,
    title: str,
    body: str,
    settings: Settings,
    eyebrow: str | None = None,
    embedded_logo: bool = False,
) -> str:
    year = datetime.now().year
    app_name = settings.app_name
    eyebrow_html = ""
    if eyebrow:
        eyebrow_html = (
            f'<p style="margin:0 0 8px;font-size:12px;letter-spacing:0.18em;text-transform:uppercase;'
            f'color:{_ORANGE};font-weight:700;">{escape(eyebrow)}</p>'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:{_CREAM};font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:{_TEXT};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_CREAM};padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:{_WHITE};border-radius:24px;
        border:1px solid {_BORDER};overflow:hidden;box-shadow:0 18px 50px rgba(13,59,42,0.08);">
        <tr>
          <td style="background:{_GREEN};padding:22px 28px 18px;">
            <p style="margin:0;font-size:26px;line-height:1;font-weight:800;letter-spacing:-0.04em;
              color:{_WHITE};font-family:Georgia,'Times New Roman',serif;">
              Trade<span style="color:{_ORANGE};">Bay</span>
            </p>
            <p style="margin:8px 0 0;font-size:11px;letter-spacing:0.24em;text-transform:uppercase;
              color:rgba(255,255,255,0.72);font-weight:600;">Source · Connect · Grow</p>
          </td>
        </tr>
        <tr>
          <td style="height:5px;background:linear-gradient(90deg,{_ORANGE} 0%,{_ORANGE_DEEP} 55%,{_GREEN_MID} 100%);
            background-color:{_ORANGE};font-size:0;line-height:0;">&nbsp;</td>
        </tr>
        <tr>
          <td style="padding:28px 32px 10px;">
            {_petal_bar()}
            {eyebrow_html}
            <h1 style="margin:0 0 14px;font-size:24px;line-height:1.3;font-weight:700;color:{_TEXT};
              letter-spacing:-0.02em;">{escape(title)}</h1>
            {body}
          </td>
        </tr>
        <tr>
          <td style="padding:8px 32px 28px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
              style="border-top:1px solid {_BORDER};padding-top:18px;">
              <tr>
                <td style="font-size:12px;line-height:1.65;color:{_MUTED};">
                  Built for Lebanese businesses — source, connect, and grow on {escape(app_name)}.
                  <br />© {year} {escape(app_name)} · Lebanon
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _button(url: str, label: str, *, tone: str = "orange") -> str:
    bg = _ORANGE if tone == "orange" else _GREEN
    hover_note = ""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px 0 12px;">
  <tr>
    <td style="background:{bg};border-radius:12px;">
      <a href="{escape(url)}" style="display:inline-block;padding:14px 26px;color:{_WHITE};text-decoration:none;
        font-weight:700;font-size:14px;letter-spacing:0.01em;">{escape(label)} →</a>
    </td>
  </tr>
</table>
{hover_note}
<p style="margin:0;font-size:12px;line-height:1.55;color:{_MUTED};word-break:break-all;">
  Or open this link:<br />
  <a href="{escape(url)}" style="color:{_GREEN_MID};text-decoration:underline;">{escape(url)}</a>
</p>"""


def _otp_block(otp: str) -> str:
    digits = "".join(ch for ch in otp if ch.isdigit()) or otp
    cells = []
    for ch in digits:
        cells.append(
            f"""<td style="width:44px;height:52px;border:1.5px solid {_BORDER};border-radius:12px;
              background:{_CREAM};text-align:center;vertical-align:middle;
              font-size:24px;font-weight:700;color:{_GREEN};letter-spacing:0;">{escape(ch)}</td>"""
        )
        cells.append('<td style="width:8px;font-size:0;">&nbsp;</td>')
    if cells:
        cells.pop()  # trailing spacer
    row = "".join(cells)
    return f"""
<p style="margin:0;text-align:center;font-size:11px;letter-spacing:0.22em;text-transform:uppercase;
  color:{_MUTED};font-weight:700;">Your code</p>
<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:12px auto 8px;">
  <tr>{row}</tr>
</table>
<p style="margin:0;text-align:center;font-size:13px;letter-spacing:0.28em;font-weight:700;color:{_GREEN};">
  {escape(digits)}
</p>
"""


def render_message(
    *,
    template: str,
    context: dict[str, Any],
    settings: Settings,
    embedded_logo: bool = False,
    omit_insecure_links: bool = False,
) -> tuple[str, str, str]:
    """Return (subject, html, text)."""
    app_name = settings.app_name
    token = str(context.get("token") or "")
    otp = str(context.get("otp") or token)

    if template == "email_verification":
        subject = f"Your {app_name} verification code"
        html = _wrap_html(
            title="Verify your email",
            eyebrow="Almost there",
            settings=settings,
            embedded_logo=embedded_logo,
            body=(
                f"<p style='margin:0 0 8px;font-size:15px;line-height:1.65;color:{_MUTED};'>"
                f"Welcome to <strong style='color:{_TEXT};'>{escape(app_name)}</strong>. "
                "Enter this one-time code in the app to verify your email and unlock sourcing, "
                "procurement, and payments.</p>"
                f"{_otp_block(otp)}"
                f"<p style='margin:0;text-align:center;font-size:13px;line-height:1.55;color:{_MUTED};'>"
                f"This code expires in <strong style='color:{_GREEN};'>15 minutes</strong> "
                "and can only be used once. Never share it with anyone.</p>"
            ),
        )
        text = (
            f"Your {app_name} verification code is: {otp}\n\n"
            "Enter it in the app to verify your email.\n"
            "It expires in 15 minutes and can only be used once.\n"
        )
        return subject, html, text

    if template == "password_reset":
        subject = f"Your {app_name} password reset code"
        html = _wrap_html(
            title="Reset your password",
            eyebrow="Account security",
            settings=settings,
            embedded_logo=embedded_logo,
            body=(
                f"<p style='margin:0 0 8px;font-size:15px;line-height:1.65;color:{_MUTED};'>"
                f"We received a request to reset your <strong style='color:{_TEXT};'>{escape(app_name)}</strong> "
                "password. Enter this one-time code in the app, then choose a new password.</p>"
                f"{_otp_block(otp)}"
                f"<p style='margin:0;text-align:center;font-size:13px;line-height:1.55;color:{_MUTED};'>"
                f"This code expires in <strong style='color:{_ORANGE};'>15 minutes</strong> "
                "and can only be used once. Never share it with anyone.</p>"
                f"<p style='margin:20px 0 0;font-size:13px;line-height:1.55;color:{_MUTED};'>"
                "If you did not request this, you can safely ignore this email. "
                "Your password will stay the same.</p>"
            ),
        )
        text = (
            f"Your {app_name} password reset code is: {otp}\n\n"
            "Enter it in the app to choose a new password.\n"
            "It expires in 15 minutes and can only be used once.\n"
            "If you did not request this, ignore this email.\n"
        )
        return subject, html, text

    if template == "invitation":
        url = _frontend_link(settings, "/accept-invitation", token)
        business = escape(str(context.get("business_name") or "a TradeBay business"))
        role = escape(str(context.get("role_name") or "a role"))
        inviter = escape(str(context.get("inviter_name") or "A teammate"))
        company_email = escape(str(context.get("company_email") or ""))
        subject = f"You're invited to join {context.get('business_name') or app_name}"
        login_note = (
            f"<p style='margin:16px 0 8px;font-size:13px;line-height:1.55;color:{_MUTED};'>"
            f"Create your account and sign in with <strong style='color:{_TEXT};'>{company_email}</strong>. "
            f"This invitation expires in 7 days."
            f"</p>"
            if company_email
            else (
                f"<p style='margin:16px 0 0;font-size:13px;line-height:1.55;color:{_MUTED};'>"
                "This invitation expires in 7 days.</p>"
            )
        )
        html = _wrap_html(
            title="You're invited!",
            eyebrow="Team invitation",
            settings=settings,
            embedded_logo=embedded_logo,
            body=(
                f"<p style='margin:0 0 8px;font-size:15px;line-height:1.65;color:{_MUTED};'>"
                f"<strong style='color:{_TEXT};'>{inviter}</strong> has invited you to join "
                f"<strong style='color:{_TEXT};'>{business}</strong> on {escape(app_name)}.</p>"
                f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
                f"style='margin:20px 0;border-collapse:separate;border-spacing:0 10px;'>"
                f"<tr><td style='padding:14px 16px;background:{_CREAM};border:1px solid {_BORDER};"
                f"border-radius:12px;width:50%;vertical-align:top;'>"
                f"<span style='display:block;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;"
                f"color:{_MUTED};font-weight:700;margin-bottom:6px;'>Role</span>"
                f"<strong style='color:{_GREEN};font-size:15px;'>{role}</strong>"
                f"</td><td style='width:10px;'></td>"
                f"<td style='padding:14px 16px;background:{_CREAM};border:1px solid {_BORDER};"
                f"border-radius:12px;width:50%;vertical-align:top;'>"
                f"<span style='display:block;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;"
                f"color:{_MUTED};font-weight:700;margin-bottom:6px;'>Company login</span>"
                f"<strong style='color:{_TEXT};font-size:15px;'>"
                f"{company_email or business}</strong>"
                f"</td></tr></table>"
                f"{_invite_cta_html(url, omit_insecure_links=omit_insecure_links)}"
                f"{login_note}"
            ),
        )
        invite_link = f"{url}\n"
        text = (
            f"{context.get('inviter_name') or 'A teammate'} invited you to join "
            f"{context.get('business_name')} as {context.get('role_name')}.\n"
            f"Sign in with {context.get('company_email') or 'your company login'} to create your account.\n"
            f"{invite_link}"
            "This invitation expires in 7 days.\n"
        )
        return subject, html, text

    if template == "business_event":
        business = str(context.get("business_name") or "").strip()
        event_title = str(context.get("title") or f"{app_name} update")
        event_message = str(context.get("message") or "").strip()
        first_name = str(context.get("first_name") or "").strip()
        cta_path = str(context.get("cta_path") or "/notifications")
        if not cta_path.startswith("/"):
            cta_path = f"/{cta_path}"
        url = _frontend_link(settings, cta_path)
        greeting = f"Hi {escape(first_name)}," if first_name else "Hello,"
        membership_html = (
            f"<p style='margin:16px 0 0;font-size:13px;line-height:1.55;color:{_MUTED};'>"
            f"This update is for <strong style='color:{_GREEN};'>{escape(business)}</strong>.</p>"
            if business
            else ""
        )
        body_copy = (
            f"<p style='margin:0 0 12px;font-size:15px;line-height:1.65;color:{_MUTED};'>"
            f"{escape(event_message)}</p>"
            if event_message
            else ""
        )
        subject = f"{business + ' · ' if business else ''}{event_title}"
        html = _wrap_html(
            title=event_title,
            eyebrow=business or "TradeBay update",
            settings=settings,
            embedded_logo=embedded_logo,
            body=(
                f"<p style='margin:0 0 12px;font-size:15px;line-height:1.65;color:{_MUTED};'>"
                f"{greeting}</p>"
                f"{body_copy}"
                f"{_cta_html(url, 'Open in TradeBay', tone='green', omit_insecure_links=omit_insecure_links)}"
                f"{membership_html}"
            ),
        )
        membership_text = (
            f"This update is for {business}.\n"
            if business
            else ""
        )
        event_link = "" if (omit_insecure_links and _is_insecure_app_url(url)) else f"{url}\n"
        text = (
            f"{event_title}\n\n"
            f"{('Hi ' + first_name + ',') if first_name else 'Hello,'}\n\n"
            f"{event_message + chr(10) + chr(10) if event_message else ''}"
            f"{membership_text}\n"
            f"{event_link}"
        )
        return subject, html, text

    subject = f"{app_name} notification"
    html = _wrap_html(
        title=subject,
        settings=settings,
        embedded_logo=embedded_logo,
        body=f"<p style='margin:0;font-size:15px;line-height:1.65;color:{_MUTED};'>"
        f"You have a new {escape(app_name)} notification.</p>",
    )
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
        global _quota_blocked_until
        if time.monotonic() < _quota_blocked_until:
            raise EmailQuotaExhaustedError("Elastic Email credits exhausted (cooldown)")
        api_key = self.settings.elasticemail_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise RuntimeError("ELASTICEMAIL_API_KEY is not configured")

        subject, html, text = render_message(
            template=template,
            context=context,
            settings=self.settings,
            embedded_logo=False,
            omit_insecure_links=True,
        )
        from_name, from_email = _parse_from_address(self.settings.email_from)
        from_header = f"{from_name} <{from_email}>" if from_name else from_email

        content: dict[str, Any] = {
            "From": from_header,
            "ReplyTo": from_email,
            "Subject": subject,
            "Body": [
                {"ContentType": "HTML", "Charset": "utf-8", "Content": html},
                {"ContentType": "PlainText", "Charset": "utf-8", "Content": text},
            ],
        }

        payload = {
            "Recipients": {"To": [to]},
            "Content": content,
            # Account-level tracking wraps every URL through Elastic Email's
            # bounce/click domains. Gmail flags those as phishing.
            "Options": {
                "TrackOpens": False,
                "TrackClicks": False,
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
            snippet = (response.text or "")[:300]
            if elastic_quota_exhausted(response.status_code, snippet):
                _quota_blocked_until = time.monotonic() + _QUOTA_COOLDOWN_SECONDS
                logger.warning(
                    "elastic_email_quota_exhausted",
                    status=response.status_code,
                    template=template,
                    body=snippet,
                )
                raise EmailQuotaExhaustedError(snippet or "Elastic Email credits exhausted")
            logger.error(
                "elastic_email_failed",
                status=response.status_code,
                to=to,
                template=template,
                body=snippet,
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
            logo_mode="wordmark",
            context_keys=sorted(_safe_context(context).keys()),
        )


_sender: EmailSender = LogEmailSender()


def get_email_sender() -> EmailSender:
    return _sender


def outbound_email_is_remote() -> bool:
    """True when send() talks to Elastic Email (do not await it on API requests)."""
    return isinstance(_sender, ElasticEmailSender)


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
        _, from_email = _parse_from_address(settings.email_from)
        from app.modules.identity.company_domain import is_public_mailbox_domain

        if is_public_mailbox_domain(from_email):
            logger.warning(
                "email_from_is_personal_mailbox",
                from_address=settings.email_from,
                hint=(
                    "Do not send as Gmail/Outlook through Elastic Email. "
                    "Gmail will show 'via bounces.elasticemail.net' and flag the message. "
                    "Use a From address on a domain you own and authenticate (SPF/DKIM) in Elastic Email."
                ),
            )
        logger.info("email_provider_configured", provider="elasticemail", from_address=settings.email_from)
    else:
        sender = LogEmailSender()
        logger.info("email_provider_configured", provider="log")
    set_email_sender(sender)
    return sender
