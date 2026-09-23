"""Unit tests for security helpers."""

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_otp_code,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Secret123!")
    assert hashed != "Secret123!"
    assert verify_password("Secret123!", hashed)
    assert not verify_password("wrong", hashed)


def test_token_hash_stable() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abcd")


def test_generate_otp_code_is_numeric_fixed_length() -> None:
    code = generate_otp_code(length=6)
    assert len(code) == 6
    assert code.isdigit()
    codes = {generate_otp_code(length=6) for _ in range(40)}
    assert len(codes) > 1


def test_production_forces_secure_cookies_and_rate_limit() -> None:
    settings = Settings(
        app_env="production",
        secret_key="test-secret-key-min-32-characters!!",
        jwt_secret_key="test-jwt-secret-key-32-characters!",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="tradebay_test",
        cors_origins="https://app.tradebay.example",
        cookie_secure=False,
        rate_limit_enabled=False,
        app_debug=True,
    )
    assert settings.cookie_secure is True
    assert settings.rate_limit_enabled is True
    assert settings.app_debug is False
    assert settings.is_production is True


def test_production_rejects_placeholder_secrets() -> None:
    import pytest

    with pytest.raises(Exception):
        Settings(
            app_env="production",
            secret_key="change-me-to-a-long-random-string-at-least-32-chars",
            jwt_secret_key="test-jwt-secret-key-32-characters!",
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="tradebay_test",
            cors_origins="https://app.tradebay.example",
        )

def test_access_token_roundtrip() -> None:
    settings = Settings(
        secret_key="test-secret-key-min-32-characters!!",
        jwt_secret_key="test-jwt-secret-key-32-characters!",
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="tradebay_test",
        cors_origins="http://localhost:3000",
    )
    token = create_access_token(
        settings=settings,
        user_id="507f1f77bcf86cd799439011",
        session_id="507f1f77bcf86cd799439012",
        business_account_id="507f1f77bcf86cd799439013",
    )
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "507f1f77bcf86cd799439011"
    assert payload["sid"] == "507f1f77bcf86cd799439012"
    assert payload["typ"] == "access"
