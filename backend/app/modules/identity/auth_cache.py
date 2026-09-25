
from __future__ import annotations

import time
from typing import Any

_role_permissions: dict[str, tuple[float, frozenset[str]]] = {}
                                             
_session_auth: dict[str, tuple[float, dict[str, Any]]] = {}

ROLE_PERMISSIONS_TTL_SECONDS = 60.0
SESSION_AUTH_TTL_SECONDS = 8.0

def get_cached_role_permissions(role_id: str) -> frozenset[str] | None:
    hit = _role_permissions.get(role_id)
    if hit is None:
        return None
    ts, codes = hit
    if time.monotonic() - ts > ROLE_PERMISSIONS_TTL_SECONDS:
        _role_permissions.pop(role_id, None)
        return None
    return codes

def set_cached_role_permissions(role_id: str, codes: set[str] | frozenset[str]) -> None:
    _role_permissions[role_id] = (time.monotonic(), frozenset(codes))

def invalidate_role_permissions(role_id: str | None = None) -> None:
    if role_id is None:
        _role_permissions.clear()
    else:
        _role_permissions.pop(str(role_id), None)
                                                                
    _session_auth.clear()

def get_cached_session_auth(session_id: str) -> dict[str, Any] | None:
    hit = _session_auth.get(session_id)
    if hit is None:
        return None
    ts, snapshot = hit
    if time.monotonic() - ts > SESSION_AUTH_TTL_SECONDS:
        _session_auth.pop(session_id, None)
        return None
    return snapshot

def set_cached_session_auth(session_id: str, snapshot: dict[str, Any]) -> None:
    _session_auth[session_id] = (time.monotonic(), snapshot)

def invalidate_session_auth(session_id: str | None = None) -> None:
    if session_id is None:
        _session_auth.clear()
    else:
        _session_auth.pop(str(session_id), None)
