
from __future__ import annotations

import json
import logging
from typing import Any

_REDACTED = frozenset(
    {
        "api_key",
        "authorization",
        "password",
        "access_token",
        "refresh_token",
        "secret",
        "prompt",
        "messages",
        "business_description",
    }
)

def log_ai_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if key.lower() not in _REDACTED}
    logger.info("ai_event %s %s", event, json.dumps(safe, default=str, sort_keys=True))
