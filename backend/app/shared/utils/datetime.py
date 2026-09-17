"""UTC datetime helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize Mongo-returned datetimes for comparison with utc_now()."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
