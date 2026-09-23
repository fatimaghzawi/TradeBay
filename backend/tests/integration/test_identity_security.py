"""Identity security integration tests: OTP, recovery, sessions, RBAC, isolation."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import pytest
from app.core.constants import REFRESH_COOKIE_NAME
from app.core.security import hash_token, verify_password
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import SYSTEM_ROLE_PLATFORM_ADMIN, MembershipStatus
from app.modules.identity.email import MemoryEmailSender
from app.modules.identity.permissions import permission_code
from app.shared.utils.datetime import utc_now
from httpx import ASGITransport, AsyncClient


async def _register(
    client: AsyncClient,
    email_inbox: MemoryEmailSender,
    *,
    email: str | None = None,
    business_name: str | None = "Co Ltd",
) -> dict[str, Any]:
    address = email or f"u_{os.urandom(4).hex()}@example.com"
    payload: dict[str, Any] = {
        "email": address,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
    }
    if business_name:
        payload["business_name"] = business_name
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert "verification_token" not in body
    return {
        "email": address,
        "password": "SecurePass123!",
        "user": body["user"],
        "business": body.get("business"),
        "verification_token": email_inbox.last_token(to=address, template="email_verification"),
    }


async def _verify(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_register_hashes_password_and_starts_unverified(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    user = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    assert user is not None
    assert user["password_hash"] != registered_user["password"]
    assert verify_password(registered_user["password"], user["password_hash"])
    assert user["status"] == "pending"
    assert user.get("email_verified_at") is None


@pytest.mark.asyncio
async def test_duplicate_verified_email_rejected(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _verify(client, registered_user["verification_token"])
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": registered_user["email"],
            "password": "SecurePass123!",
            "first_name": "Other",
            "last_name": "Person",
            "business_name": "Other Co",
            "business_type": "buyer",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_unverified_reregister_resends_code_and_updates_password(
    client: AsyncClient,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    first_token = registered_user["verification_token"]
    assert first_token
    retry = await client.post(
        "/api/v1/auth/register",
        json={
            "email": registered_user["email"],
            "password": "NewerPass123!",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Analytical Engines Ltd",
            "business_type": "buyer",
        },
    )
    assert retry.status_code == 200, retry.text
    second_token = email_inbox.last_token(
        to=registered_user["email"], template="email_verification"
    )
    assert second_token
    assert second_token != first_token
    stale = await client.post("/api/v1/auth/verify-email", json={"token": first_token})
    assert stale.status_code == 401
    ok = await client.post("/api/v1/auth/verify-email", json={"token": second_token})
    assert ok.status_code == 200
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "NewerPass123!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_invalid_email_and_password_rejected(client: AsyncClient) -> None:
    bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "SecurePass123!", "first_name": "A", "last_name": "B"},
    )
    assert bad_email.status_code == 422
    weak = await client.post(
        "/api/v1/auth/register",
        json={"email": "ok@example.com", "password": "short", "first_name": "A", "last_name": "B"},
    )
    assert weak.status_code == 422
    no_digit = await client.post(
        "/api/v1/auth/register",
        json={"email": "ok2@example.com", "password": "NoDigitsHere", "first_name": "A", "last_name": "B"},
    )
    assert no_digit.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_invalid_expired_reused_and_wrong_purpose(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    token = registered_user["verification_token"]
    assert token
    bad = await client.post("/api/v1/auth/verify-email", json={"token": "totally-invalid-token"})
    assert bad.status_code == 401

    reset = await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    assert reset.status_code == 200
    reset_token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert reset_token
    wrong_purpose = await client.post("/api/v1/auth/verify-email", json={"token": reset_token})
    assert wrong_purpose.status_code == 401

    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"expires_at": utc_now() - timedelta(hours=1)}},
    )
    expired = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert expired.status_code == 401

    fresh = await client.post("/api/v1/auth/resend-verification")
    assert fresh.status_code == 200
    new_token = email_inbox.last_token(to=registered_user["email"], template="email_verification")
    assert new_token
    assert new_token != token
    old_again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert old_again.status_code == 401

    ok = await client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert ok.status_code == 200
    reused = await client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert reused.status_code == 401
    already = await client.post("/api/v1/auth/resend-verification")
    assert already.status_code == 200


@pytest.mark.asyncio
async def test_otp_max_attempts_on_same_challenge(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    token = registered_user["verification_token"]
    assert token
    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"attempts": 5}},
    )
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"


@pytest.mark.asyncio
async def test_wrong_otp_allows_five_attempts_then_locks(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    email = registered_user["email"]
    for i in range(4):
        bad = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": "00000", "email": email},
        )
        assert bad.status_code == 401, bad.text
        body = bad.json()["error"]
        assert body["code"] == "OTP_INVALID"
        assert body["details"]["remaining_attempts"] == 4 - i

    fifth = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": "00000", "email": email},
    )
    assert fifth.status_code == 401
    assert fifth.json()["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"

    locked = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": registered_user["verification_token"], "email": email},
    )
    assert locked.status_code == 401
    assert locked.json()["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"

@pytest.mark.asyncio
async def test_verified_user_cannot_create_second_owned_business(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _verify(client, registered_user["verification_token"])
    created = await client.post(
        "/api/v1/businesses",
        json={"name": "Second Trading"},
    )
    assert created.status_code == 409, created.text
    assert created.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_password_reset_flow_and_session_invalidation(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200
    assert unknown.json()["data"]["requested"] is True

    requested = await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    assert requested.status_code == 200
    token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert token

    verify_with_reset = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_with_reset.status_code == 401

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert reset.status_code == 200
    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert reused.status_code == 401

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "BrandNewPass123!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_expired_and_attempts(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert token
    await mongo_manager.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"expires_at": utc_now() - timedelta(hours=3)}},
    )
    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass123!"},
    )
    assert expired.status_code == 401

    verify_token = registered_user["verification_token"]
    wrong = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": verify_token, "password": "BrandNewPass123!"},
    )
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_rejects_old_credential(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    assert old_refresh
    first = await client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    reused = await client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_current_and_revokes_sessions(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPass123!", "new_password": "NewerPass123!"},
    )
    assert wrong.status_code == 401
    ok = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": registered_user["password"], "new_password": "NewerPass123!"},
    )
    assert ok.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "NewerPass123!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_company_email_domain_stored_on_register(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    business = registered_user["business"]
    assert business is not None
    assert business.get("email_domain") == "example.com"
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    active = me.json()["data"]["active_business"]
    assert active["email_domain"] == "example.com"


@pytest.mark.asyncio
async def test_register_with_personal_gmail_sends_verification(
    client: AsyncClient, email_inbox: MemoryEmailSender
) -> None:
    email = f"owner_{os.urandom(4).hex()}@gmail.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Fatima",
            "last_name": "Haddad",
            "business_name": "Safawi Trading",
            "business_type": "buyer",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["user"]["email"] == email
    business = payload.get("business")
    assert business is not None
    assert business.get("email_domain") in (None, "")
    token = email_inbox.last_token(to=email, template="email_verification")
    assert token


@pytest.mark.asyncio
async def test_invitation_rejects_foreign_company_login_domain(
    client: AsyncClient,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")

    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": f"outsider_{os.urandom(3).hex()}@gmail.com",
            "company_email": f"outsider_{os.urandom(3).hex()}@othercompany.com",
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 403, invited.text
    body = invited.json()["error"]
    assert body["code"] == "COMPANY_DOMAIN_MISMATCH"


@pytest.mark.asyncio
async def test_invitation_delivers_to_personal_email_login_is_company_email(
    client: AsyncClient,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    personal = f"personal_{os.urandom(3).hex()}@gmail.com"
    company_login = f"teammate_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": personal,
            "company_email": company_login,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200, invited.text
    data = invited.json()["data"]
    assert data["invited_email"] == company_login
    assert data["delivery_email"] == personal
    assert email_inbox.last_token(to=personal, template="invitation")
    assert email_inbox.last_token(to=company_login, template="invitation") is None


@pytest.mark.asyncio
async def test_invite_signup_skips_otp_and_marks_verified(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    """Company login emails are not mailboxes — invitation proof replaces OTP."""
    await _verify(client, registered_user["verification_token"])
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    personal = f"personal_{os.urandom(3).hex()}@gmail.com"
    company_login = f"invitee_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": personal,
            "company_email": company_login,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200, invited.text
    invite_token = email_inbox.last_token(to=personal, template="invitation")
    assert invite_token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        registered = await other.post(
            "/api/v1/auth/register",
            json={
                "email": company_login,
                "password": "SecurePass123!",
                "first_name": "Invited",
                "last_name": "Member",
                "invitation_token": invite_token,
            },
        )
        assert registered.status_code == 200, registered.text
        user = registered.json()["data"]["user"]
        assert user["email"] == company_login
        assert user["email_verified_at"] is not None
        assert user["status"] == "active"
        assert email_inbox.last_token(to=company_login, template="email_verification") is None

        accepted = await other.post("/api/v1/invitations/accept", json={"token": invite_token})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["data"].get("already_accepted") is False

        me = await other.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["data"]["user"]["email_verified_at"] is not None

        # Idempotent re-accept should succeed without error.
        again = await other.post("/api/v1/invitations/accept", json={"token": invite_token})
        assert again.status_code == 200, again.text
        assert again.json()["data"].get("already_accepted") is True


@pytest.mark.asyncio
async def test_invitation_allows_same_company_domain(
    client: AsyncClient,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    teammate = f"teammate_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": teammate,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["data"]["invited_email"] == teammate
    assert email_inbox.last_token(to=teammate, template="invitation")


@pytest.mark.asyncio
async def test_unauthorized_business_switch_rejected(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    other = await _register(client, email_inbox, business_name="Other Co")
    other_id = other["business"]["id"]
    # Restore first user's cookies by logging in again.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200
    switch = await client.post("/api/v1/businesses/current/switch", json={"business_id": other_id})
    assert switch.status_code == 403


@pytest.mark.asyncio
async def test_multi_business_permission_isolation(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    """Cross-business isolation via invitation join (one owned business per account)."""
    await _verify(client, registered_user["verification_token"])
    first_id = registered_user["business"]["id"]
    roles_a = (await client.get("/api/v1/roles")).json()["data"]
    viewer_a = next(item for item in roles_a if item["name"] == "Viewer")

    other_email = f"other_{os.urandom(3).hex()}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        other_reg = await _register(other, email_inbox, email=other_email, business_name="Other Co")
        await _verify(other, other_reg["verification_token"])
        second_id = other_reg["business"]["id"]
        roles_b = (await other.get("/api/v1/roles")).json()["data"]
        viewer_b = next(item for item in roles_b if item["name"] == "Viewer")

        # Invite registered_user into other company as Viewer.
        invited = await other.post(
            "/api/v1/invitations",
            json={
                "email": registered_user["email"],
                "role_id": viewer_b["id"],
                "permissions": viewer_b["permissions"],
            },
        )
        assert invited.status_code == 200, invited.text
        token = email_inbox.last_token(to=registered_user["email"], template="invitation")
        assert token

    accepted = await client.post("/api/v1/invitations/accept", json={"token": token})
    assert accepted.status_code == 200, accepted.text
    switched = await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": second_id}
    )
    assert switched.status_code == 200
    roles_on_b = (await client.get("/api/v1/roles")).json()["data"]
    await client.post("/api/v1/businesses/current/switch", json={"business_id": first_id})
    roles_on_a = (await client.get("/api/v1/roles")).json()["data"]
    ids_a = {item["id"] for item in roles_on_a}
    ids_b = {item["id"] for item in roles_on_b}
    assert ids_a.isdisjoint(ids_b)
    foreign = next(item for item in roles_on_b if item["name"] == "Viewer")
    patch = await client.patch(
        f"/api/v1/roles/{foreign['id']}",
        json={"permissions": ["users.read"]},
    )
    assert patch.status_code == 403
    # Sanity: own Viewer role still addressable in active business.
    assert any(item["id"] == viewer_a["id"] for item in roles_on_a)


@pytest.mark.asyncio
async def test_invitation_accept_wrong_recipient_and_reuse(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    invitee_email = f"invitee_{os.urandom(3).hex()}@example.com"
    escalated = await client.post(
        "/api/v1/invitations",
        json={
            "email": invitee_email,
            "role_id": viewer["id"],
            "permissions": ["settings.manage"],
        },
    )
    assert escalated.status_code == 403

    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": invitee_email,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200
    assert "token" not in invited.json()["data"]
    assert invited.json()["data"]["permissions"] == sorted(viewer["permissions"])
    token = email_inbox.last_token(to=invitee_email, template="invitation")
    assert token

    wrong = await client.post("/api/v1/invitations/accept", json={"token": token})
    assert wrong.status_code == 403

    other_transport = ASGITransport(app=app)
    async with AsyncClient(transport=other_transport, base_url="http://test") as other_client:
        await _register(other_client, email_inbox, email=invitee_email, business_name=None)
        accepted = await other_client.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text
        reused = await other_client.post("/api/v1/invitations/accept", json={"token": token})
        assert reused.status_code == 200, reused.text
        assert reused.json()["data"].get("already_accepted") is True


@pytest.mark.asyncio
async def test_invitation_expired_and_revoked(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"later_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={"email": email, "role_id": viewer["id"], "permissions": viewer["permissions"]},
    )
    invitation_id = invited.json()["data"]["id"]
    token = email_inbox.last_token(to=email, template="invitation")
    revoked = await client.post(f"/api/v1/invitations/{invitation_id}/revoke")
    assert revoked.status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=email, business_name=None)
        accepted = await other.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_pending_invitation_is_friendly(
    client: AsyncClient,
    registered_user: dict[str, Any],
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"dup_{os.urandom(3).hex()}@example.com"
    payload = {
        "email": email,
        "role_id": viewer["id"],
        "permissions": viewer["permissions"][:1] or ["users.read"],
    }
    first = await client.post("/api/v1/invitations", json=payload)
    assert first.status_code == 200
    assert first.json()["data"]["already_pending"] is False
    second = await client.post("/api/v1/invitations", json=payload)
    assert second.status_code == 200, second.text
    body = second.json()["data"]
    assert body["already_pending"] is True
    assert body["id"] == first.json()["data"]["id"]
    assert "pending invitation" in (body.get("message") or "").lower()


@pytest.mark.asyncio
async def test_custom_role_and_system_role_protection(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    created = await client.post(
        "/api/v1/roles",
        json={"name": "Ops Desk", "permissions": ["users.read", "roles.read"]},
    )
    assert created.status_code == 200
    role_id = created.json()["data"]["id"]
    deleted = await client.delete(f"/api/v1/roles/{role_id}")
    assert deleted.status_code == 200
    roles = (await client.get("/api/v1/roles")).json()["data"]
    admin = next(item for item in roles if item["name"] == "Business Admin")
    blocked = await client.delete(f"/api/v1/roles/{admin['id']}")
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_permission_denied_uses_resource_action_not_role_name(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"viewer_{os.urandom(3).hex()}@example.com"
    await client.post(
        "/api/v1/invitations",
        json={"email": email, "role_id": viewer["id"], "permissions": viewer["permissions"]},
    )
    token = email_inbox.last_token(to=email, template="invitation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=email, business_name=None)
        await other.post("/api/v1/invitations/accept", json={"token": token})
        await other.post(
            "/api/v1/businesses/current/switch",
            json={"business_id": registered_user["business"]["id"]},
        )
        denied = await other.post("/api/v1/roles", json={"name": "Nope", "permissions": ["users.read"]})
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
        assert denied.json()["error"]["details"]["resource"] == "roles"
        assert denied.json()["error"]["details"]["action"] == "manage"


@pytest.mark.asyncio
async def test_trading_admin_cannot_global_suspend_users(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    """Global account suspend is platform-only — trading Business Admin must not ban outsiders."""
    other_email = f"target_{os.urandom(3).hex()}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        other_reg = await _register(other, email_inbox, email=other_email, business_name="Target Co")
        target_id = other_reg["user"]["id"]

    denied = await client.post(
        "/api/v1/users/suspend",
        json={"user_id": target_id, "reason": "Should not work"},
    )
    assert denied.status_code == 403
    still = await mongo_manager.database["users"].find_one({"email": other_email})
    assert still is not None
    assert still["status"] != "suspended"


@pytest.mark.asyncio
async def test_suspend_requires_reason_blocks_sessions_and_audits(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    # Elevate to platform admin so global suspend is authorized.
    user_doc = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    now = utc_now()
    await mongo_manager.database["business_memberships"].insert_one(
        {
            "user_id": user_doc["_id"],
            "business_account_id": platform["_id"],
            "role_id": role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])}
    )

    missing = await client.post(
        "/api/v1/users/suspend",
        json={"user_id": registered_user["user"]["id"], "reason": ""},
    )
    assert missing.status_code == 422
    suspended = await client.post(
        "/api/v1/platform/users/suspend",
        json={"user_id": registered_user["user"]["id"], "reason": "Policy violation"},
    )
    assert suspended.status_code == 200, suspended.text
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 403
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code in {401, 403}
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 403
    logs = await mongo_manager.database["audit_logs"].find({"action": "USER_SUSPENDED"}).to_list(10)
    assert logs
    assert logs[-1]["metadata"]["reason"] == "Policy violation"
    assert "password" not in logs[-1]["metadata"]


@pytest.mark.asyncio
async def test_platform_staff_through_platform_business(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    me = await client.get("/api/v1/auth/me")
    trading_permissions = set(me.json()["data"]["permissions"])
    assert permission_code("settings", "manage") not in trading_permissions
    assert permission_code("suppliers", "verify") not in trading_permissions
    user_doc = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    assert user_doc is not None
    assert "is_platform_admin" not in user_doc
    assert "is_staff" not in user_doc

    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    assert platform is not None
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    assert role is not None
    now = utc_now()
    await mongo_manager.database["business_memberships"].insert_one(
        {
            "user_id": user_doc["_id"],
            "business_account_id": platform["_id"],
            "role_id": role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    switched = await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])}
    )
    assert switched.status_code == 200, switched.text
    platform_me = await client.get("/api/v1/auth/me")
    codes = set(platform_me.json()["data"]["permissions"])
    assert permission_code("settings", "manage") in codes
    assert permission_code("suppliers", "verify") in codes
    await client.post(
        "/api/v1/businesses/current/switch",
        json={"business_id": registered_user["business"]["id"]},
    )
    back = await client.get("/api/v1/auth/me")
    assert permission_code("settings", "manage") not in set(back.json()["data"]["permissions"])


@pytest.mark.asyncio
async def test_audit_registration_has_actor_and_no_secrets(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    logs = await mongo_manager.database["audit_logs"].find(
        {"action": "USER_REGISTERED", "resource_id": __import__("bson").ObjectId(registered_user["user"]["id"])}
    ).to_list(5)
    assert logs
    row = logs[0]
    assert row.get("user_id") is not None
    assert row.get("action") == "USER_REGISTERED"
    assert row.get("created_at") is not None
    blob = str(row.get("metadata") or {})
    assert "SecurePass123!" not in blob
    assert registered_user["verification_token"] not in blob


@pytest.mark.asyncio
async def test_invitation_cannot_demote_last_business_admin(
    client: AsyncClient,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": registered_user["email"],
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200
    token = email_inbox.last_token(to=registered_user["email"], template="invitation")
    assert token
    accepted = await client.post("/api/v1/invitations/accept", json={"token": token})
    assert accepted.status_code == 409, accepted.text
    assert accepted.json()["error"]["code"] == "LAST_ADMIN_PROTECTED"


@pytest.mark.asyncio
async def test_invitation_reaccept_after_membership_removed(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    invitee_email = f"rejoin_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={
            "email": invitee_email,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited.status_code == 200
    token = email_inbox.last_token(to=invitee_email, template="invitation")
    assert token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=invitee_email, business_name=None)
        accepted = await other.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text
        membership_id = accepted.json()["data"]["membership_id"]

    removed = await client.delete(f"/api/v1/members/{membership_id}")
    assert removed.status_code == 200

    invited2 = await client.post(
        "/api/v1/invitations",
        json={
            "email": invitee_email,
            "role_id": viewer["id"],
            "permissions": viewer["permissions"],
        },
    )
    assert invited2.status_code == 200, invited2.text
    token2 = email_inbox.last_token(to=invitee_email, template="invitation")
    assert token2

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.post(
            "/api/v1/auth/login",
            json={"email": invitee_email, "password": "SecurePass123!"},
        )
        reaccepted = await other.post("/api/v1/invitations/accept", json={"token": token2})
        assert reaccepted.status_code == 200, reaccepted.text


@pytest.mark.asyncio
async def test_nested_member_get_requires_users_read(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    # Viewer includes users.read — use a custom role without it.
    custom = await client.post(
        "/api/v1/roles",
        json={"name": f"Limited {os.urandom(2).hex()}", "permissions": ["roles.read"]},
    )
    assert custom.status_code == 200, custom.text
    limited_role_id = custom.json()["data"]["id"]

    members = (await client.get("/api/v1/members")).json()["data"]
    admin_membership = members[0]
    business_id = registered_user["business"]["id"]

    email = f"noview_{os.urandom(3).hex()}@example.com"
    await client.post(
        "/api/v1/invitations",
        json={"email": email, "role_id": limited_role_id, "permissions": ["roles.read"]},
    )
    token = email_inbox.last_token(to=email, template="invitation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _register(other, email_inbox, email=email, business_name=None)
        await other.post("/api/v1/invitations/accept", json={"token": token})
        await other.post(
            "/api/v1/businesses/current/switch",
            json={"business_id": business_id},
        )
        denied = await other.get(
            f"/api/v1/businesses/{business_id}/members/{admin_membership['id']}"
        )
        assert denied.status_code == 403


@pytest.mark.asyncio
async def test_platform_users_pagination_meta(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    user_doc = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    now = utc_now()
    await mongo_manager.database["business_memberships"].insert_one(
        {
            "user_id": user_doc["_id"],
            "business_account_id": platform["_id"],
            "role_id": role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])}
    )
    page1 = await client.get("/api/v1/platform/users", params={"page": 1, "page_size": 1})
    assert page1.status_code == 200, page1.text
    body = page1.json()
    assert "data" in body and "meta" in body
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 1
    assert body["meta"]["total"] >= 1
    assert len(body["data"]) <= 1


async def _elevate_platform_admin(client: AsyncClient, email: str) -> str:
    user_doc = await mongo_manager.database["users"].find_one({"email": email})
    platform = await mongo_manager.database["business_accounts"].find_one({"type": "platform"})
    role = await mongo_manager.database["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    now = utc_now()
    await mongo_manager.database["business_memberships"].insert_one(
        {
            "user_id": user_doc["_id"],
            "business_account_id": platform["_id"],
            "role_id": role["_id"],
            "status": MembershipStatus.ACTIVE,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
    )
    await client.post(
        "/api/v1/businesses/current/switch", json={"business_id": str(platform["_id"])}
    )
    return str(platform["_id"])


@pytest.mark.asyncio
async def test_platform_can_provision_user_buyer_and_supplier(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _elevate_platform_admin(client, registered_user["email"])
    suffix = os.urandom(3).hex()

    user_res = await client.post(
        "/api/v1/platform/users",
        json={
            "email": f"ops_{suffix}@example.com",
            "password": "SecurePass123!",
            "first_name": "Ops",
            "last_name": "User",
        },
    )
    assert user_res.status_code == 200, user_res.text
    user_body = user_res.json()["data"]
    assert user_body["email"] == f"ops_{suffix}@example.com"
    assert user_body["status"] == "active"
    assert user_body["email_verified_at"] is not None

    buyer_res = await client.post(
        "/api/v1/platform/businesses",
        json={
            "account_type": "buyer",
            "business_name": f"Buyer Co {suffix}",
            "email_domain": f"buyer{suffix}.com",
            "owner_email": f"owner@buyer{suffix}.com",
            "owner_password": "SecurePass123!",
            "owner_first_name": "Buy",
            "owner_last_name": "Owner",
        },
    )
    assert buyer_res.status_code == 200, buyer_res.text
    buyer = buyer_res.json()["data"]
    assert buyer["business"]["type"] == "buyer"
    assert buyer["business"]["status"] == "verified"
    assert buyer["business"]["email_domain"] == f"buyer{suffix}.com"
    assert buyer["user"]["email"] == f"owner@buyer{suffix}.com"

    supplier_res = await client.post(
        "/api/v1/platform/businesses",
        json={
            "account_type": "supplier",
            "business_name": f"Supplier Co {suffix}",
            "email_domain": f"supplier{suffix}.com",
            "owner_email": f"owner@supplier{suffix}.com",
            "owner_password": "SecurePass123!",
            "owner_first_name": "Sup",
            "owner_last_name": "Owner",
            "verify_supplier": True,
        },
    )
    assert supplier_res.status_code == 200, supplier_res.text
    supplier = supplier_res.json()["data"]
    assert supplier["business"]["type"] == "supplier"
    assert supplier["business"]["status"] == "verified"
    assert supplier["business"]["verification_status"] == "verified"

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": f"owner@buyer{suffix}.com",
            "password": "SecurePass123!",
        },
    )
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_platform_full_control_on_trading_company_roles(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    """Platform Admin can list/edit Business Admin and create custom roles on tenants."""
    await _elevate_platform_admin(client, registered_user["email"])
    suffix = os.urandom(3).hex()
    buyer_res = await client.post(
        "/api/v1/platform/businesses",
        json={
            "account_type": "buyer",
            "business_name": f"Roles Co {suffix}",
            "email_domain": f"roles{suffix}.com",
            "owner_email": f"owner@roles{suffix}.com",
            "owner_password": "SecurePass123!",
            "owner_first_name": "Roles",
            "owner_last_name": "Owner",
        },
    )
    assert buyer_res.status_code == 200, buyer_res.text
    business_id = buyer_res.json()["data"]["business"]["id"]

    listed = await client.get(f"/api/v1/platform/businesses/{business_id}/roles")
    assert listed.status_code == 200, listed.text
    roles = listed.json()["data"]
    admin = next(item for item in roles if item["name"] == "Business Admin")
    assert "users.read" in admin["permissions"]

    # Trading company Business Admin cannot be edited via company routes by platform
    # session (wrong tenant) — but platform oversight unlocks it.
    updated = await client.patch(
        f"/api/v1/platform/businesses/{business_id}/roles/{admin['id']}",
        json={"permissions": ["users.read", "roles.read", "businesses.read"]},
    )
    assert updated.status_code == 200, updated.text
    assert set(updated.json()["data"]["permissions"]) == {
        "users.read",
        "roles.read",
        "businesses.read",
    }

    # Platform-only codes must not land on trading roles.
    blocked = await client.patch(
        f"/api/v1/platform/businesses/{business_id}/roles/{admin['id']}",
        json={"permissions": ["users.read", "settings.manage"]},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PRIVILEGE_ESCALATION"

    created = await client.post(
        f"/api/v1/platform/businesses/{business_id}/roles",
        json={"name": f"Desk {suffix}", "permissions": ["users.read", "orders.read"]},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["name"] == f"Desk {suffix}"

