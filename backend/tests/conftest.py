"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# Configure test env before importing the app
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_NAME", "TradeBay")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-characters!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-characters!")
os.environ.setdefault(
    "MONGODB_URI",
    os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true"),
)
os.environ.setdefault("MONGODB_DATABASE", "tradebay_test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.core.config import reset_settings_cache
from app.db.mongodb import mongo_manager
from app.main import create_app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def app() -> AsyncIterator[Any]:
    reset_settings_cache()
    application = create_app()
    await mongo_manager.connect()
    yield application
    # Drop test database collections for isolation across runs
    if mongo_manager.is_ready:
        await mongo_manager.database.client.drop_database(mongo_manager.database.name)
    await mongo_manager.disconnect()
    reset_settings_cache()


@pytest.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict[str, Any]:
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
    return {
        "email": email,
        "password": "SecurePass123!",
        "user": payload["user"],
        "business": payload.get("business"),
        "verification_token": payload.get("verification_token"),
        "cookies": response.cookies,
    }
