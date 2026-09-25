
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BadRequestError
from app.core.paths import UPLOAD_ROOT

PRODUCT_UPLOAD_DIR = UPLOAD_ROOT / "products"
CATEGORY_UPLOAD_DIR = UPLOAD_ROOT / "categories"

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

def _image_bytes_match(data: bytes) -> bool:
    if data.startswith(b"\xff\xd8\xff"):
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data.startswith((b"GIF87a", b"GIF89a")):
        return True
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"

async def _save_image(*, folder: Path, public_prefix: str, upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower().strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("Unsupported image type. Use JPG, PNG, WEBP, or GIF.")

    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await upload.read(64 * 1024)
        if not piece:
            break
        total += len(piece)
        if total > MAX_BYTES:
            raise BadRequestError("Image must be 8 MB or smaller")
        chunks.append(piece)
    data = b"".join(chunks)
    if not data:
        raise BadRequestError("Empty file")
    if not _image_bytes_match(data):
        raise BadRequestError("File contents are not a supported image.")

    ext = _safe_ext(upload.filename, content_type or None)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = folder / filename
    path.write_bytes(data)
    return f"{public_prefix}/{filename}"

async def save_product_image(
    *,
    product_id: str,
    upload: UploadFile,
) -> str:
    return await _save_image(
        folder=PRODUCT_UPLOAD_DIR / product_id,
        public_prefix=f"/uploads/products/{product_id}",
        upload=upload,
    )

async def save_category_image(
    *,
    category_id: str,
    upload: UploadFile,
) -> str:
    return await _save_image(
        folder=CATEGORY_UPLOAD_DIR / category_id,
        public_prefix=f"/uploads/categories/{category_id}",
        upload=upload,
    )

def delete_stored_file(url: str | None) -> None:
    if not url or not url.startswith("/uploads/"):
        return
    relative = url.removeprefix("/uploads/")
    root = UPLOAD_ROOT.resolve()
    path = (UPLOAD_ROOT / relative).resolve()
    try:
        if path.is_file() and (path == root or root in path.parents):
            path.unlink(missing_ok=True)
    except OSError:
        pass
