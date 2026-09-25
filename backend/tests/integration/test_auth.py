
from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_me(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    assert registered_user["user"]["email"] == registered_user["email"]
    assert registered_user["user"]["status"] == "pending"
    assert registered_user["user"]["email_verified_at"] is None
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    me = response.json()["data"]
    assert me["user"]["email"] == registered_user["email"]
    assert me["active_business"] is not None
    assert "users.read" in me["permissions"]

@pytest.mark.asyncio
async def test_login_logout(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    me_after = await client.get("/api/v1/auth/me")
    assert me_after.status_code == 401

@pytest.mark.asyncio
async def test_refresh(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    _ = registered_user
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200
    assert "access_token_expires_in_minutes" in refresh.json()["data"]

@pytest.mark.asyncio
async def test_validation_error_shape(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"

@pytest.mark.asyncio
async def test_verify_email(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    token = registered_user.get("verification_token")
    assert token
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["data"]["user"]["status"] == "active"
    me = await client.get("/api/v1/auth/me")
    assert me.json()["data"]["user"]["email_verified_at"] is not None

@pytest.mark.asyncio
async def test_forgot_password_does_not_reveal_account(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["requested"] is True
