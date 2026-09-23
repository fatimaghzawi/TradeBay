"""Supplier verification files stay off the public StaticFiles mount."""

from __future__ import annotations

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.identity import storage
from app.modules.identity.service import _serialize_verification_documents


def test_parse_verification_url_roundtrip() -> None:
    url = storage.verification_file_url(
        business_id="biz1",
        document_type="tax_certificate",
        filename="tax_certificate-abc123.pdf",
    )
    assert storage.parse_verification_url(url) == (
        "biz1",
        "tax_certificate",
        "tax_certificate-abc123.pdf",
    )


def test_parse_rejects_pending_and_public_paths() -> None:
    assert storage.parse_verification_url("pending://tax_certificate") is None
    assert storage.parse_verification_url("/uploads/verification/biz1/tax.pdf") is None


def test_resolve_and_is_stored(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "VERIFICATION_DIR", tmp_path)
    filename = "tax_certificate-abc123.pdf"
    folder = tmp_path / "biz1"
    folder.mkdir()
    (folder / filename).write_bytes(b"%PDF-1.4")
    url = storage.verification_file_url(
        business_id="biz1",
        document_type="tax_certificate",
        filename=filename,
    )
    assert storage.is_stored_verification_url("biz1", "tax_certificate", url) is True
    path = storage.resolve_verification_path(
        business_id="biz1",
        document_type="tax_certificate",
        filename=filename,
    )
    assert path.is_file()


def test_resolve_rejects_path_traversal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "VERIFICATION_DIR", tmp_path)
    with pytest.raises(BadRequestError):
        storage.resolve_verification_path(
            business_id="biz1",
            document_type="tax_certificate",
            filename="../secret.pdf",
        )
    with pytest.raises(BadRequestError):
        storage.resolve_verification_path(
            business_id="biz1",
            document_type="tax_certificate",
            filename="address_proof-abc.pdf",
        )
    with pytest.raises(NotFoundError):
        storage.resolve_verification_path(
            business_id="biz1",
            document_type="tax_certificate",
            filename="tax_certificate-missing.pdf",
        )


def test_serialize_strips_pending_placeholders() -> None:
    rows = _serialize_verification_documents(
        {
            "documents": [
                {
                    "document_type": "tax_certificate",
                    "url": "pending://tax_certificate",
                    "file_name": "tax.pdf",
                },
                {
                    "document_type": "address_proof",
                    "url": "/api/v1/businesses/x/verification/documents/address_proof/files/address_proof-1.pdf",
                    "file_name": "addr.pdf",
                },
            ]
        }
    )
    assert rows[0]["url"] is None
    assert rows[1]["url"].startswith("/api/v1/")
