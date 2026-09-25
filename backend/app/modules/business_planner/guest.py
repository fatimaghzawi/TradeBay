
from __future__ import annotations

import hashlib
import re
from typing import Annotated

from fastapi import Depends, Header

from app.core.exceptions import UnauthorizedError
from app.modules.identity.dependencies import AuthContext, get_optional_user

_GUEST_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

def guest_owner_id(guest_key: str) -> str:
    digest = hashlib.sha256(f"tradebay-guest:{guest_key.strip().lower()}".encode()).hexdigest()
    return digest[:24]

def resolve_planner_owner_id(
    auth: AuthContext | None,
    guest_key: str | None,
) -> str:
    if auth is not None:
        return auth.user_id
    if guest_key and _GUEST_RE.match(guest_key.strip()):
        return guest_owner_id(guest_key)
    raise UnauthorizedError("Sign in or continue as guest to use the business planner")

async def get_planner_owner_id(
    auth: Annotated[AuthContext | None, Depends(get_optional_user)],
    x_tradebay_guest: Annotated[str | None, Header()] = None,
) -> str:
    return resolve_planner_owner_id(auth, x_tradebay_guest)
