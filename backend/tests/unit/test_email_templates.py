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


def test_render_verification_includes_token_link() -> None:
    subject, html, text = render_message(
        template="email_verification",
        context={"token": "abc123token"},
        settings=_settings(),
    )
    assert "Verify" in subject
    assert "token=abc123token" in html
    assert "token=abc123token" in text
    assert "abc123token" not in subject


def test_render_password_reset_and_invitation() -> None:
    settings = _settings()
    _, reset_html, _ = render_message(
        template="password_reset",
        context={"token": "reset-token"},
        settings=settings,
    )
    assert "/reset-password?token=reset-token" in reset_html

    _, invite_html, _ = render_message(
        template="invitation",
        context={"token": "invite-token", "business_name": "Acme", "role_name": "Viewer"},
        settings=settings,
    )
    assert "Acme" in invite_html
    assert "Viewer" in invite_html
    assert "/accept-invitation?token=invite-token" in invite_html
