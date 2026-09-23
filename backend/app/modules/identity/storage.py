"""Local disk storage for business logo and cover images."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.paths import UPLOAD_ROOT
from app.modules.identity.constants import REQUIRED_SUPPLIER_DOCUMENT_TYPES

BUSINESS_UPLOAD_DIR = UPLOAD_ROOT / "businesses"

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)
ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
MAX_BYTES = 8 * 1024 * 1024


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
    }
    if content_type and content_type.lower() in mapping:
        return mapping[content_type.lower()]
    raise BadRequestError("Unsupported image type. Use JPG, PNG, WEBP, or GIF.")


async def save_business_image(
    *,
    business_id: str,
    kind: str,
    upload: UploadFile,
) -> str:
    """Persist logo/cover and return public URL `/uploads/businesses/...`."""
    if kind not in {"logo", "cover"}:
        raise BadRequestError("kind must be logo or cover")

    content_type = (upload.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("Unsupported image type. Use JPG, PNG, WEBP, or GIF.")

    data = await upload.read()
    if not data:
        raise BadRequestError("Empty file")
    if len(data) > MAX_BYTES:
        raise BadRequestError("Image must be 8 MB or smaller")

    ext = _safe_ext(upload.filename, content_type or None)
    folder = BUSINESS_UPLOAD_DIR / business_id / kind
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (folder / filename).write_bytes(data)
    return f"/uploads/businesses/{business_id}/{kind}/{filename}"


# ── Supplier verification documents (authenticated download, not public) ──────

VERIFICATION_DIR = UPLOAD_ROOT / "verification"

VERIFICATION_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)
VERIFICATION_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf"})
VERIFICATION_MAX_BYTES = 10 * 1024 * 1024


def _verification_ext(filename: str | None, content_type: str | None) -> str:
    name = (filename or "").lower()
    match = re.search(r"(\.[a-z0-9]{2,5})$", name)
    if match and match.group(1) in VERIFICATION_EXTENSIONS:
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
    raise BadRequestError("Unsupported document type. Use PDF, JPG, or PNG.")


def verification_file_url(*, business_id: str, document_type: str, filename: str) -> str:
    return (
        f"/api/v1/businesses/{business_id}/verification/documents/"
        f"{document_type}/files/{filename}"
    )


def parse_verification_url(url: str | None) -> tuple[str, str, str] | None:
    """Return ``(business_id, document_type, filename)`` for a stored file URL."""
    if not url:
        return None
    path = url.strip()
    if "://" in path:
        from urllib.parse import urlparse

        path = urlparse(path).path
    parts = path.split("/")
    # /api/v1/businesses/{id}/verification/documents/{type}/files/{filename}
    if (
        len(parts) != 10
        or parts[1:4] != ["api", "v1", "businesses"]
        or parts[5:7] != ["verification", "documents"]
        or parts[8] != "files"
    ):
        return None
    business_id, document_type, filename = parts[4], parts[7], parts[9]
    if not business_id or document_type not in REQUIRED_SUPPLIER_DOCUMENT_TYPES or not filename:
        return None
    return business_id, document_type, filename


def resolve_verification_path(
    *, business_id: str, document_type: str, filename: str
) -> Path:
    """Resolve a stored verification file, rejecting path traversal."""
    if document_type not in REQUIRED_SUPPLIER_DOCUMENT_TYPES:
        raise BadRequestError("Unknown verification document type")
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise BadRequestError("Invalid document filename")
    if not safe_name.startswith(f"{document_type}-"):
        raise BadRequestError("Invalid document filename")
    folder = (VERIFICATION_DIR / business_id).resolve()
    path = (folder / safe_name).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise NotFoundError("Verification document not found")
    return path


def is_stored_verification_url(business_id: str, document_type: str, url: str | None) -> bool:
    parsed = parse_verification_url(url)
    if parsed is None:
        return False
    stored_business, stored_type, filename = parsed
    if stored_business != business_id or stored_type != document_type:
        return False
    try:
        resolve_verification_path(
            business_id=stored_business,
            document_type=stored_type,
            filename=filename,
        )
    except (BadRequestError, NotFoundError):
        return False
    return True


def delete_verification_file_from_url(url: str | None) -> None:
    parsed = parse_verification_url(url)
    if parsed is None:
        return
    business_id, document_type, filename = parsed
    try:
        path = resolve_verification_path(
            business_id=business_id,
            document_type=document_type,
            filename=filename,
        )
    except (BadRequestError, NotFoundError):
        return
    path.unlink(missing_ok=True)


def media_type_for_verification_file(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")


async def save_verification_document(
    *,
    business_id: str,
    document_type: str,
    upload: UploadFile,
) -> str:
    """Persist a KYC file and return the authenticated download URL."""
    if document_type not in REQUIRED_SUPPLIER_DOCUMENT_TYPES:
        raise BadRequestError("Unknown verification document type")

    content_type = (upload.content_type or "").lower().strip()
    if content_type and content_type not in VERIFICATION_CONTENT_TYPES:
        raise BadRequestError("Unsupported document type. Use PDF, JPG, or PNG.")

    data = await upload.read()
    if not data:
        raise BadRequestError("Empty file")
    if len(data) > VERIFICATION_MAX_BYTES:
        raise BadRequestError("Document must be 10 MB or smaller")

    ext = _verification_ext(upload.filename, content_type or None)
    folder = VERIFICATION_DIR / business_id
    folder.mkdir(parents=True, exist_ok=True)
    for leftover in folder.glob(f"{document_type}-*"):
        leftover.unlink(missing_ok=True)
    filename = f"{document_type}-{uuid.uuid4().hex}{ext}"
    (folder / filename).write_bytes(data)
    return verification_file_url(
        business_id=business_id,
        document_type=document_type,
        filename=filename,
    )
