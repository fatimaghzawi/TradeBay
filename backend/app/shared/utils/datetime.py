
import time
from datetime import UTC, datetime, timedelta

_seed_clock: tuple[datetime, float] | None = None

def utc_now() -> datetime:
    if _seed_clock is not None:
        base, started = _seed_clock
        return base + timedelta(seconds=time.monotonic() - started)
    return datetime.now(UTC)

def set_seed_clock(moment: datetime | None) -> None:
    global _seed_clock
    _seed_clock = None if moment is None else (as_utc(moment), time.monotonic())

def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
