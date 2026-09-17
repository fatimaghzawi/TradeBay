"""Unit tests for Identity password policy, rate limits, and commercial-write gate."""

import pytest
from app.core.exceptions import RateLimitError
from app.modules.identity.dependencies import assert_email_verified
from app.modules.identity.exceptions import AccountInactiveError, EmailUnverifiedError, PrivilegeEscalationError
from app.modules.identity.password import validate_password
from app.modules.identity.rate_limit import SlidingWindowLimiter


def test_validate_password_accepts_mixed() -> None:
    assert validate_password("SecurePass123!") == "SecurePass123!"


def test_validate_password_rejects_weak() -> None:
    with pytest.raises(ValueError):
        validate_password("short")
    with pytest.raises(ValueError):
        validate_password("NoDigitsHere")
    with pytest.raises(ValueError):
        validate_password("12345678")


def test_assert_email_verified_gate() -> None:
    with pytest.raises(EmailUnverifiedError):
        assert_email_verified({"email_verified_at": None, "status": "pending"})
    with pytest.raises(AccountInactiveError):
        assert_email_verified({"email_verified_at": "2026-01-01T00:00:00Z", "status": "suspended"})
    assert_email_verified({"email_verified_at": "2026-01-01T00:00:00Z", "status": "active"})


def test_challenge_limiter() -> None:
    limiter = SlidingWindowLimiter(max_hits=2, window_seconds=60)
    limiter.hit("a")
    limiter.hit("a")
    with pytest.raises(RateLimitError):
        limiter.hit("a")
    limiter.hit("b")


@pytest.mark.asyncio
async def test_permission_subset_comparison() -> None:
    from app.modules.identity.directory import DirectoryService

    directory = DirectoryService()
    await directory.assert_subset(actor_permissions={"A", "B", "C"}, requested={"A", "B"})
    with pytest.raises(PrivilegeEscalationError):
        await directory.assert_subset(actor_permissions={"A", "B", "C"}, requested={"A", "B", "D"})
