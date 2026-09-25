
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.core.exceptions import RateLimitError
from app.shared.utils.datetime import utc_now

CHALLENGE_MAX_HITS = 5
CHALLENGE_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 15 * 60

class SlidingWindowLimiter:
    def __init__(self, *, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = defaultdict(list)

    def _recent(self, key: str) -> list[datetime]:
        cutoff = utc_now() - timedelta(seconds=self.window_seconds)
        recent = [stamp for stamp in self._hits.get(key, []) if stamp > cutoff]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def hit(self, key: str) -> None:
        recent = self._recent(key)
        if len(recent) >= self.max_hits:
            raise RateLimitError()
        self._hits[key] = [*recent, utc_now()]

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_hits

    def record(self, key: str) -> None:
        self._hits[key] = [*self._recent(key), utc_now()]

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)

    def reset(self) -> None:
        self._hits.clear()

challenge_limiter = SlidingWindowLimiter(
    max_hits=CHALLENGE_MAX_HITS,
    window_seconds=CHALLENGE_WINDOW_SECONDS,
)

                                                                                  
login_failure_limiter = SlidingWindowLimiter(
    max_hits=LOGIN_MAX_FAILURES,
    window_seconds=LOGIN_WINDOW_SECONDS,
)
