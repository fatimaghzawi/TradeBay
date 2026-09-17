"""Authorization dependency foundation tests."""

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient) -> None:
    client.cookies.clear()
    response = await client.get("/api/v1/members")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_businesses_list(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    _ = registered_user
    response = await client.get("/api/v1/businesses")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_members_allowed_for_seeded_admin(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    _ = registered_user
    response = await client.get("/api/v1/members")
    assert response.status_code == 200
    assert "data" in response.json()
