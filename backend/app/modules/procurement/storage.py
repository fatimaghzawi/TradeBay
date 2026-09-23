"""Local disk storage for procurement delivery evidence."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BadRequestError, NotFoundError

UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads"
EVIDENCE_DIR = UPLOAD_ROOT / "delivery-evidence"

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf"})
MAX_BYTES = 10 * 1024 * 1024


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
        "application/pdf": ".pdf",
    }
    if content_type and content_type.lower() in mapping:
        return mapping[content_type.lower()]
    raise BadRequestError("Unsupported evidence type. Use JPG, PNG, WEBP, or PDF.")


async def save_delivery_evidence(*, shipment_id: str, upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("Unsupported evidence type. Use JPG, PNG, WEBP, or PDF.")
    data = await upload.read()
    if not data:
        raise BadRequestError("Empty file")
    if len(data) > MAX_BYTES:
        raise BadRequestError("Evidence must be 10 MB or smaller")
    ext = _safe_ext(upload.filename, content_type or None)
    folder = EVIDENCE_DIR / shipment_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (folder / filename).write_bytes(data)
    # Authenticated download route — not under the public StaticFiles mount.
    return f"/api/v1/shipments/{shipment_id}/delivery-evidence/files/{filename}"


def resolve_evidence_path(*, shipment_id: str, filename: str) -> Path:
    """Resolve a stored evidence file, rejecting path traversal."""
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise BadRequestError("Invalid evidence filename")
    path = (EVIDENCE_DIR / shipment_id / safe_name).resolve()
    root = (EVIDENCE_DIR / shipment_id).resolve()
    if not str(path).startswith(str(root)) or not path.is_file():
        raise NotFoundError("Evidence file not found")
    return path


def public_evidence_url(*, shipment_id: str, stored_url: str | None) -> str | None:
    """Normalize legacy `/uploads/delivery-evidence/...` URLs to the authz route."""
    if not stored_url:
        return stored_url
    prefix = f"/uploads/delivery-evidence/{shipment_id}/"
    if stored_url.startswith(prefix):
        filename = stored_url.removeprefix(prefix)
        return f"/api/v1/shipments/{shipment_id}/delivery-evidence/files/{filename}"
    return stored_url
