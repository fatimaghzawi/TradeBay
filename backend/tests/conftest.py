
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient


def _dotenv_value(key: str) -> str | None:
    existing = os.environ.get(key)
    if existing:
        return existing
    conftest_dir = Path(__file__).resolve().parent
    for path in (conftest_dir.parents[1] / ".env", conftest_dir.parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, _, value = stripped.partition("=")
            if name.strip() == key:
                cleaned = value.strip().strip("'").strip('"')
                return cleaned or None
    return None

                                              
                                                                                   
                                                                 
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_NAME", "TradeBay")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-characters!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters!")
os.environ.setdefault(
    "MONGODB_URI",
    _dotenv_value("MONGODB_URI") or "mongodb://localhost:27017/?directConnection=true",
)
os.environ.setdefault("MONGODB_DATABASE", "tradebay_test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.core.config import reset_settings_cache
from app.db.mongodb import mongo_manager
from app.main import create_app
from app.modules.identity.email import LogEmailSender, MemoryEmailSender, set_email_sender
from app.modules.identity.rate_limit import challenge_limiter, login_failure_limiter


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"

@pytest.fixture(scope="session")
async def app() -> AsyncIterator[Any]:
    reset_settings_cache()
    application = create_app()
    await mongo_manager.connect()
    yield application
                                                              
    if mongo_manager.is_ready:
        await mongo_manager.database.client.drop_database(mongo_manager.database.name)
    await mongo_manager.disconnect()
    reset_settings_cache()

@pytest.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
def email_inbox() -> Any:
    inbox = MemoryEmailSender()
    set_email_sender(inbox)
    challenge_limiter.reset()
    login_failure_limiter.reset()
    yield inbox
    inbox.clear()
    set_email_sender(LogEmailSender())
    challenge_limiter.reset()
    login_failure_limiter.reset()

@pytest.fixture
async def registered_user(client: AsyncClient, email_inbox: MemoryEmailSender) -> dict[str, Any]:
    email = f"user_{os.urandom(4).hex()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Analytical Engines Ltd",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert "verification_token" not in payload
    return {
        "email": email,
        "password": "SecurePass123!",
        "user": payload["user"],
        "business": payload.get("business"),
        "verification_token": email_inbox.last_token(to=email, template="email_verification"),
        "cookies": response.cookies,
    }

@pytest.fixture
async def verified_user(client: AsyncClient, registered_user: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/verify-email", json={"token": registered_user["verification_token"]}
    )
    assert response.status_code == 200, response.text
    return registered_user
