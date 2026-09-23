"""Local disk storage for AI Visual Sourcing assets and concepts."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BadRequestError
from app.core.paths import UPLOAD_ROOT

SOURCING_UPLOAD_DIR = UPLOAD_ROOT / "ai-sourcing"

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/svg+xml",
        "application/pdf",
    }
)
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf"})
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_ext(filename: str | None, content_type: str | None) -> str:
    name = (filename or "").lower()
    match = re.search(r"(\.[a-z0-9]{2,5})$", name)
    if match and match.group(1) in ALLOWED_EXTENSIONS:
        return match.group(1)
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
    }
    if content_type and content_type.lower() in mapping:
        return mapping[content_type.lower()]
    raise BadRequestError("Unsupported file type. Use JPG, PNG, WEBP, GIF, SVG, or PDF.")


async def save_buyer_upload(
    *,
    session_id: str,
    kind: str,
    upload: UploadFile,
) -> str:
    """Persist buyer logo/reference; return public `/uploads/ai-sourcing/...` path."""
    content_type = (upload.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("Unsupported file type. Use JPG, PNG, WEBP, GIF, SVG, or PDF.")

    data = await upload.read()
    if not data:
        raise BadRequestError("Empty file")
    if len(data) > MAX_BYTES:
        raise BadRequestError("File must be 10 MB or smaller")

    ext = _safe_ext(upload.filename, content_type or None)
    folder = SOURCING_UPLOAD_DIR / session_id / kind
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (folder / filename).write_bytes(data)
    return f"/uploads/ai-sourcing/{session_id}/{kind}/{filename}"


def save_generated_bytes(
    *,
    session_id: str,
    data: bytes,
    ext: str = ".png",
) -> str:
    """Persist AI-generated concept bytes."""
    if not data:
        raise BadRequestError("Empty generated image")
    # Stub may return SVG.
    if data[:200].lstrip().startswith(b"<?xml") or data[:100].lstrip().startswith(b"<svg"):
        ext = ".svg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif data[:2] == b"\xff\xd8":
        ext = ".jpg"
    folder = SOURCING_UPLOAD_DIR / session_id / "concepts"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (folder / filename).write_bytes(data)
    return f"/uploads/ai-sourcing/{session_id}/concepts/{filename}"


def read_upload_bytes(url: str | None) -> tuple[bytes, str] | None:
    """Read a stored `/uploads/ai-sourcing/...` file for image edits."""
    if not url or not url.startswith("/uploads/ai-sourcing/"):
        return None
    relative = url.removeprefix("/uploads/")
    root = UPLOAD_ROOT.resolve()
    path = (UPLOAD_ROOT / relative).resolve()
    if not path.is_file() or root not in path.parents:
        return None
    data = path.read_bytes()
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")
    return data, mime
