"""Identity RBAC, invitations, commercial-write gate, and OTP rules."""

from typing import Any

import pytest
from app.modules.identity.permissions import permission_code
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_members_list_after_register(client: AsyncClient, registered_user: dict[str, Any]) -> None:
    _ = registered_user
    response = await client.get("/api/v1/members")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_system_roles_seeded_and_cannot_delete(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    roles = await client.get("/api/v1/roles")
    assert roles.status_code == 200
    items = roles.json()["data"]
    names = {item["name"] for item in items}
    assert {
        "Business Admin",
        "Sales Manager",
        "Sales Representative",
        "Finance",
        "Viewer",
    }.issubset(names)
    system = next(item for item in items if item["is_system_role"] and item["name"] == "Viewer")
    deleted = await client.delete(f"/api/v1/roles/{system['id']}")
    assert deleted.status_code == 409


@pytest.mark.asyncio
async def test_permission_subset_rejects_escalation(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    created = await client.post(
        "/api/v1/roles",
        json={"name": "Overreach", "permissions": [permission_code("settings", "manage")]},
    )
    assert created.status_code == 403
    assert created.json()["error"]["code"] == "PRIVILEGE_ESCALATION"
    ok = await client.post(
        "/api/v1/roles",
        json={"name": "Limited Viewer", "permissions": viewer["permissions"][:2] or ["users.read"]},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_invitation_carries_role_not_permissions(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": "invitee@example.com",
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200
    body = invited.json()["data"]
    assert body["role_id"] == viewer["id"]
    assert body["permissions"] == sorted(viewer["permissions"])
    assert "token" not in body


@pytest.mark.asyncio
async def test_unverified_user_blocked_from_creating_business(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    response = await client.post("/api/v1/businesses", json={"name": "Second Company"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_UNVERIFIED"
