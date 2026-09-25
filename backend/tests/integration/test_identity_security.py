
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import pytest
from app.core.config import get_settings
from app.core.constants import REFRESH_COOKIE_NAME
from app.core.security import hash_otp, hash_token, verify_password
from app.db.mongodb import mongo_manager
from app.modules.identity.constants import SYSTEM_ROLE_PLATFORM_ADMIN, MembershipStatus
from app.modules.identity.email import MemoryEmailSender
from app.modules.identity.permissions import permission_code
from app.shared.utils.datetime import utc_now
from bson import ObjectId
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

def _otp_filter(token: str, user_id: str, purpose: str) -> dict[str, Any]:
    return {"token_hash": hash_otp(token, user_id=user_id, purpose=purpose, settings=get_settings())}

def _wrong_code(token: str) -> str:
    return "000000" if token != "000000" else "111111"

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
async def test_unverified_reregister_with_same_password_resends_code(
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
            "password": registered_user["password"],
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

@pytest.mark.asyncio
async def test_unverified_reregister_with_other_password_cannot_take_over(
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as attacker:
        hijack = await attacker.post(
            "/api/v1/auth/register",
            json={
                "email": registered_user["email"],
                "password": "AttackerPass123!",
                "first_name": "Mallory",
                "last_name": "X",
                "business_name": "Evil Co",
            },
        )
        assert hijack.status_code == 409, hijack.text
        assert hijack.json()["error"]["code"] == "EMAIL_PENDING_VERIFICATION"
        assert "tb_access" not in hijack.cookies
        me = await attacker.get("/api/v1/auth/me")
        assert me.status_code == 401

        attacker_login = await attacker.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "AttackerPass123!"},
        )
        assert attacker_login.status_code == 401

                                                                                     
    fresh = email_inbox.last_token(to=registered_user["email"], template="email_verification")
    assert fresh and fresh != registered_user["verification_token"]
    user = await mongo_manager.database["users"].find_one({"email": registered_user["email"]})
    assert user is not None
    assert verify_password(registered_user["password"], user["password_hash"])

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
        _otp_filter(token, registered_user["user"]["id"], "email_verification"),
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
        _otp_filter(token, registered_user["user"]["id"], "email_verification"),
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
    wrong = _wrong_code(registered_user["verification_token"])
    for i in range(4):
        bad = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": wrong, "email": email},
        )
        assert bad.status_code == 401, bad.text
        body = bad.json()["error"]
        assert body["code"] == "OTP_INVALID"
        assert body["details"]["remaining_attempts"] == 4 - i

    fifth = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": wrong, "email": email},
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
        json={"email": registered_user["email"], "token": token, "password": "BrandNewPass123!"},
    )
    assert reset.status_code == 200
    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": registered_user["email"], "token": token, "password": "BrandNewPass123!"},
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
        _otp_filter(token, registered_user["user"]["id"], "password_reset"),
        {"$set": {"expires_at": utc_now() - timedelta(hours=3)}},
    )
    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": registered_user["email"], "token": token, "password": "BrandNewPass123!"},
    )
    assert expired.status_code == 401

    await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    verify_token = registered_user["verification_token"]
    wrong = await client.post(
        "/api/v1/auth/reset-password",
        json={"email": registered_user["email"], "token": verify_token, "password": "BrandNewPass123!"},
    )
    assert wrong.status_code == 401

@pytest.mark.asyncio
async def test_password_reset_requires_email_and_counts_every_guess(
    client: AsyncClient, registered_user: dict[str, Any], email_inbox: MemoryEmailSender
) -> None:
    await client.post("/api/v1/auth/forgot-password", json={"email": registered_user["email"]})
    token = email_inbox.last_token(to=registered_user["email"], template="password_reset")
    assert token

    no_email = await client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "BrandNewPass123!"}
    )
    assert no_email.status_code == 422

    other = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "someone-else@example.com", "token": token, "password": "BrandNewPass123!"},
    )
    assert other.status_code == 401

    wrong = _wrong_code(token)
    for _ in range(5):
        guess = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": registered_user["email"], "token": wrong, "password": "BrandNewPass123!"},
        )
        assert guess.status_code == 401
    locked = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": registered_user["email"], "token": token, "password": "BrandNewPass123!"},
    )
    assert locked.status_code == 401
    assert locked.json()["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"

@pytest.mark.asyncio
async def test_same_code_for_two_users_only_affects_the_named_account(
    app: Any, email_inbox: MemoryEmailSender
) -> None:
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as first,
        AsyncClient(transport=transport, base_url="http://test") as second,
    ):
        a = await _register(first, email_inbox)
        b = await _register(second, email_inbox)
        shared = "424242"
        for user in (a, b):
            await mongo_manager.database["auth_tokens"].update_one(
                {"user_id": ObjectId(user["user"]["id"]), "purpose": "email_verification", "used_at": None},
                {"$set": {"token_hash": _otp_filter(shared, user["user"]["id"], "email_verification")["token_hash"]}},
            )
        verified = await first.post("/api/v1/auth/email/verify", json={"token": shared, "email": a["email"]})
        assert verified.status_code == 200
        other = await mongo_manager.database["users"].find_one({"email": b["email"]})
        assert other is not None and other.get("email_verified_at") is None

@pytest.mark.asyncio
async def test_long_multibyte_password_is_rejected_cleanly(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"long_{os.urandom(4).hex()}@example.com",
            "password": "كلمة" * 10 + "1a",
            "first_name": "A",
            "last_name": "B",
        },
    )
    assert response.status_code == 422
    assert "too long" in response.json()["error"]["message"]

@pytest.mark.asyncio
async def test_unverified_user_cannot_write_trading_data(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    blocked = await client.post(
        "/api/v1/cart/items", json={"product_id": "0" * 24, "quantity": 1}
    )
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["error"]["code"] == "EMAIL_UNVERIFIED"
    reads = await client.get("/api/v1/auth/me")
    assert reads.status_code == 200

@pytest.mark.asyncio
async def test_repeated_failed_logins_are_throttled_per_email(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    for _ in range(10):
        bad = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "WrongPass999!"},
        )
        assert bad.status_code == 401
    throttled = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert throttled.status_code == 429

@pytest.mark.asyncio
async def test_login_skips_suspended_company_and_session_survives(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    business_id = registered_user["business"]["id"]
    await mongo_manager.database["business_accounts"].update_one(
        {"_id": ObjectId(business_id)}, {"$set": {"status": "suspended"}}
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["active_business"]["status"] == "suspended"
    trading = await client.get("/api/v1/members")
    assert trading.status_code == 403
    assert trading.json()["error"]["code"] == "BUSINESS_INACTIVE"

@pytest.mark.asyncio
async def test_replayed_refresh_token_revokes_rotated_sessions(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    _ = registered_user
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    assert old_refresh
    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    await mongo_manager.database["sessions"].update_one(
        {"refresh_token_hash": hash_token(old_refresh)},
        {"$set": {"revoked_at": utc_now() - timedelta(minutes=5)}},
    )
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401

    live = await mongo_manager.database["sessions"].find_one(
        {"refresh_token_hash": hash_token(new_refresh)}
    )
    assert live is not None and live["revoked_at"] is not None

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
                                                                   
    assert any(item["id"] == viewer_a["id"] for item in roles_on_a)

@pytest.mark.asyncio
async def test_invitation_accept_wrong_recipient_and_reuse(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
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
        invitee = await _register(other_client, email_inbox, email=invitee_email, business_name=None)
        await _verify(other_client, invitee["verification_token"])
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
    await _verify(client, registered_user["verification_token"])
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
        invitee = await _register(other, email_inbox, email=email, business_name=None)
        await _verify(other, invitee["verification_token"])
        accepted = await other.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 403

@pytest.mark.asyncio
async def test_duplicate_pending_invitation_is_friendly(
    client: AsyncClient,
    registered_user: dict[str, Any],
) -> None:
    await _verify(client, registered_user["verification_token"])
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
    await _verify(client, registered_user["verification_token"])
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
    await _verify(client, registered_user["verification_token"])
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    email = f"viewer_{os.urandom(3).hex()}@example.com"
    await client.post(
        "/api/v1/invitations",
        json={"email": email, "role_id": viewer["id"], "permissions": viewer["permissions"]},
    )
    token = email_inbox.last_token(to=email, template="invitation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        invitee = await _register(other, email_inbox, email=email, business_name=None)
        await _verify(other, invitee["verification_token"])
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
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
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

    own = await client.post(
        "/api/v1/platform/users/suspend",
        json={"user_id": registered_user["user"]["id"], "reason": "Oops"},
    )
    assert own.status_code == 403

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as target:
        target_reg = await _register(target, email_inbox, business_name="Target Co")
        target_id = target_reg["user"]["id"]
        missing = await client.post(
            "/api/v1/users/suspend",
            json={"user_id": target_id, "reason": ""},
        )
        assert missing.status_code == 422
        suspended = await client.post(
            "/api/v1/platform/users/suspend",
            json={"user_id": target_id, "reason": "Policy violation"},
        )
        assert suspended.status_code == 200, suspended.text
        me = await target.get("/api/v1/auth/me")
        assert me.status_code == 403
        refresh = await target.post("/api/v1/auth/refresh")
        assert refresh.status_code in {401, 403}
        login = await target.post(
            "/api/v1/auth/login",
            json={"email": target_reg["email"], "password": target_reg["password"]},
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
    await _verify(client, registered_user["verification_token"])
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
                                                                                               
    assert invited.status_code == 409, invited.text
    assert invited.json()["error"]["details"]["reason"] == "already_member"
    assert email_inbox.last_token(to=registered_user["email"], template="invitation") is None
    members = (await client.get("/api/v1/members")).json()["data"]
    assert members[0]["role_name"] == "Business Admin"

@pytest.mark.asyncio
async def test_invitation_reaccept_after_membership_removed(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
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
        invitee = await _register(other, email_inbox, email=invitee_email, business_name=None)
        await _verify(other, invitee["verification_token"])
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
    await _verify(client, registered_user["verification_token"])
                                                                
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
        invitee = await _register(other, email_inbox, email=email, business_name=None)
        await _verify(other, invitee["verification_token"])
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
async def test_member_manager_cannot_act_on_broader_access(
    client: AsyncClient,
    app: Any,
    registered_user: dict[str, Any],
    email_inbox: MemoryEmailSender,
) -> None:
    await _verify(client, registered_user["verification_token"])
    hr_codes = ["users.read", "users.update", "users.remove", "roles.read", "roles.manage"]
    hr = await client.post(
        "/api/v1/roles", json={"name": f"HR {os.urandom(2).hex()}", "permissions": hr_codes}
    )
    assert hr.status_code == 200, hr.text
    senior = await client.post(
        "/api/v1/roles",
        json={"name": f"Senior {os.urandom(2).hex()}", "permissions": ["users.read", "businesses.read"]},
    )
    assert senior.status_code == 200, senior.text
    roles = (await client.get("/api/v1/roles")).json()["data"]
    viewer = next(item for item in roles if item["name"] == "Viewer")
    owner_membership = (await client.get("/api/v1/members")).json()["data"][0]
    business_id = registered_user["business"]["id"]

    email = f"hr_{os.urandom(3).hex()}@example.com"
    invited = await client.post(
        "/api/v1/invitations",
        json={"email": email, "role_id": hr.json()["data"]["id"], "permissions": hr_codes},
    )
    assert invited.status_code == 200, invited.text
    token = email_inbox.last_token(to=email, template="invitation")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        member = await _register(other, email_inbox, email=email, business_name=None)
        await _verify(other, member["verification_token"])
        accepted = await other.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text
        await other.post("/api/v1/businesses/current/switch", json={"business_id": business_id})

        demote = await other.patch(
            f"/api/v1/members/{owner_membership['id']}", json={"role_id": viewer["id"]}
        )
        assert demote.status_code == 403, demote.text
        assert demote.json()["error"]["code"] == "PRIVILEGE_ESCALATION"
        suspend = await other.post(
            f"/api/v1/members/{owner_membership['id']}/suspend", json={"reason": "test"}
        )
        assert suspend.status_code == 403, suspend.text
        remove = await other.delete(f"/api/v1/members/{owner_membership['id']}")
        assert remove.status_code == 403, remove.text
        strip = await other.patch(
            f"/api/v1/roles/{senior.json()['data']['id']}", json={"permissions": ["users.read"]}
        )
        assert strip.status_code == 403, strip.text

    still_admin = (await client.get("/api/v1/members")).json()["data"]
    owner_after = next(item for item in still_admin if item["id"] == owner_membership["id"])
    assert owner_after["status"] == MembershipStatus.ACTIVE

@pytest.mark.asyncio
async def test_role_with_open_invitation_cannot_be_deleted(
    client: AsyncClient, registered_user: dict[str, Any]
) -> None:
    await _verify(client, registered_user["verification_token"])
    role = await client.post(
        "/api/v1/roles",
        json={"name": f"Temp {os.urandom(2).hex()}", "permissions": ["users.read"]},
    )
    role_id = role.json()["data"]["id"]
    invited = await client.post(
        "/api/v1/invitations",
        json={"email": f"t_{os.urandom(3).hex()}@example.com", "role_id": role_id, "permissions": ["users.read"]},
    )
    assert invited.status_code == 200, invited.text
    blocked = await client.delete(f"/api/v1/roles/{role_id}")
    assert blocked.status_code == 409, blocked.text

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

