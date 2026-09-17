"""Unit tests for API response helpers."""

from app.shared.schemas.response import paginated, success


def test_success_envelope() -> None:
    body = success({"ok": True}, meta={"source": "test"})
    assert body == {"data": {"ok": True}, "meta": {"source": "test"}}


def test_paginated_envelope() -> None:
    body = paginated([1, 2], page=2, page_size=10, total=12)
    assert body["meta"]["page"] == 2
    assert body["meta"]["total"] == 12
    assert body["data"] == [1, 2]
