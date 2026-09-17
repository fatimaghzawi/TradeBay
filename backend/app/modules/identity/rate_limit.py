"""In-process sliding-window limiter for OTP / reset challenge endpoints."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.core.exceptions import RateLimitError
from app.shared.utils.datetime import utc_now

CHALLENGE_MAX_HITS = 5
CHALLENGE_WINDOW_SECONDS = 15 * 60


class SlidingWindowLimiter:
    def __init__(self, *, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = defaultdict(list)

    def hit(self, key: str) -> None:
        now = utc_now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        recent = [stamp for stamp in self._hits[key] if stamp > cutoff]
        if len(recent) >= self.max_hits:
            self._hits[key] = recent
            raise RateLimitError()
        recent.append(now)
        self._hits[key] = recent

    def reset(self) -> None:
        self._hits.clear()


challenge_limiter = SlidingWindowLimiter(
    max_hits=CHALLENGE_MAX_HITS,
    window_seconds=CHALLENGE_WINDOW_SECONDS,
)
