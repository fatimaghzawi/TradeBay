
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import Settings

TokenType = Literal["access"]

class TokenError(Exception):
    pass

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def hash_otp(raw: str, *, user_id: str, purpose: str, settings: Settings) -> str:
    message = f"{user_id}:{purpose}:{raw.strip()}".encode()
    key = settings.secret_key.get_secret_value().encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()

def otp_matches(raw: str, expected_hash: str, *, user_id: str, purpose: str, settings: Settings) -> bool:
    candidate = hash_otp(raw, user_id=user_id, purpose=purpose, settings=settings)
    return hmac.compare_digest(candidate, expected_hash)

def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)

def generate_otp_code(*, length: int = 6) -> str:
    if length < 4 or length > 8:
        raise ValueError("OTP length must be between 4 and 8")
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"

def create_access_token(
    *,
    settings: Settings,
    user_id: str,
    session_id: str,
    business_account_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "bid": business_account_id,
        "typ": "access",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "jti": str(uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired access token") from exc
    if payload.get("typ") != "access":
        raise TokenError("Unexpected token type")
    return payload
