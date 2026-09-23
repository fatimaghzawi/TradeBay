"""Deprecated import path — use ``auth_router`` instead.

Historically Identity exposed a single ``router``. Authentication now lives in
``auth_router.py``; members/roles/invitations live in ``identity_router.py``.

This module keeps ``from app.modules.identity.router import router`` working.
"""

from app.modules.identity.auth_router import router

__all__ = ["router"]
