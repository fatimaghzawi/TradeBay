
from __future__ import annotations

import os
from pathlib import Path


def resolve_upload_root() -> Path:
    override = (os.environ.get("UPLOAD_ROOT") or "").strip()
    if override:
        return Path(override)
                                                                                          
    return Path(__file__).resolve().parents[2] / "uploads"

UPLOAD_ROOT = resolve_upload_root()
