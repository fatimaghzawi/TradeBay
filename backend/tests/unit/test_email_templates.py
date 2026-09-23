"""Email template rendering stays free of provider SDKs."""

from app.core.config import Settings
from app.modules.identity.email import render_message


def _settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-min-32-characters!!",
        jwt_secret_key="test-jwt-secret-key-32-characters!",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="tradebay_test",
        cors_origins="http://localhost:3000",
        frontend_url="http://localhost:3000",
        app_name="TradeBay",
    )


def test_render_verification_includes_otp_not_link() -> None:
    subject, html, text = render_message(
        template="email_verification",
        context={"token": "48291", "otp": "48291"},
        settings=_settings(),
    )
    assert "verification code" in subject.lower()
    assert "48291" in html
    assert "48291" in text
    assert "token=48291" not in html
    assert "/verify-email" not in html
    assert "15 minutes" in html
    assert "#0d3b2a" in html
    assert "#e86f2a" in html
    assert "TradeBay" in html
    assert "Source · Connect · Grow" in html


def test_render_password_reset_includes_otp_not_link() -> None:
    subject, html, text = render_message(
        template="password_reset",
        context={"token": "73915", "otp": "73915"},
        settings=_settings(),
    )
    assert "reset code" in subject.lower()
    assert "73915" in html
    assert "73915" in text
    assert "token=73915" not in html
    assert "/reset-password" not in html
    assert "15 minutes" in html
    assert "#0d3b2a" in html
    assert "#e86f2a" in html


def test_render_invitation_keeps_link() -> None:
    settings = _settings()
    _, invite_html, _ = render_message(
        template="invitation",
        context={"token": "invite-token", "business_name": "Acme", "role_name": "Viewer"},
        settings=settings,
    )
    assert "Acme" in invite_html
    assert "Viewer" in invite_html
    assert "/accept-invitation?token=invite-token" in invite_html
    assert "#0d3b2a" in invite_html
    assert "Accept invitation" in invite_html


def test_business_event_email_names_the_company() -> None:
    subject, html, text = render_message(
        template="business_event",
        context={
            "title": "Quotation awarded — PO PO-1001",
            "message": "Your quote was accepted.",
            "business_name": "Levant Wholesale",
            "first_name": "Karim",
            "cta_path": "/notifications",
        },
        settings=_settings(),
    )
    assert "Levant Wholesale" in subject
    assert "Quotation awarded" in subject
    assert "personal inbox" not in html.lower()
    assert "Levant Wholesale" in html
    assert "Hi Karim" in html
    assert "/notifications" in html
    assert "company contact" not in html.lower()
    assert "This update is for" in html
    assert "Levant Wholesale" in html


def test_outbound_omits_localhost_and_http_links() -> None:
    _, html, text = render_message(
        template="invitation",
        context={"token": "invite-token", "business_name": "Acme", "role_name": "Viewer"},
        settings=_settings(),
        omit_insecure_links=True,
    )
    assert 'href="http://localhost' not in html
    assert "/accept-invitation?token=invite-token" in html
    assert "/accept-invitation?token=invite-token" in text
    assert "Copy this address into your browser" in html
    assert "Gmail" not in html


def test_https_app_url_keeps_cta() -> None:
    settings = _settings()
    object.__setattr__(settings, "frontend_url", "https://app.tradebay.com")
    _, html, _ = render_message(
        template="invitation",
        context={"token": "invite-token", "business_name": "Acme", "role_name": "Viewer"},
        settings=settings,
        omit_insecure_links=True,
    )
    assert "https://app.tradebay.com/accept-invitation?token=invite-token" in html
