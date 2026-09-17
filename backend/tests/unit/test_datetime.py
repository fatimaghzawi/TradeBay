"""UTC datetime helper tests."""

from datetime import UTC, datetime

from app.shared.utils.datetime import as_utc


def test_as_utc_treats_naive_as_utc() -> None:
    naive = datetime(2026, 9, 17, 6, 0, 0)
    aware = as_utc(naive)
    assert aware.tzinfo is UTC
    assert aware.replace(tzinfo=None) == naive


def test_as_utc_preserves_aware_instant() -> None:
    original = datetime(2026, 9, 17, 6, 0, 0, tzinfo=UTC)
    assert as_utc(original) == original
    assert as_utc(original) < datetime(2026, 9, 17, 7, 0, 0, tzinfo=UTC)
