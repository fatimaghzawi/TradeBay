"""Writable upload root for local disk media (products, logos, evidence)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_upload_root() -> Path:
    """Prefer UPLOAD_ROOT env (Docker/Render); else `<repo>/uploads` next to the app package."""
    override = (os.environ.get("UPLOAD_ROOT") or "").strip()
    if override:
        return Path(override)
    # app/core/paths.py → parents[2] == install root (`/app` in Docker, `backend` locally)
    return Path(__file__).resolve().parents[2] / "uploads"


UPLOAD_ROOT = resolve_upload_root()
