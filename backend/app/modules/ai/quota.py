
from __future__ import annotations

import logging
from datetime import timedelta

from pymongo import ReturnDocument

from app.core.config import Settings, get_settings
from app.core.constants import ErrorCode
from app.core.exceptions import AppError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

logger = logging.getLogger(__name__)

_RETENTION_DAYS = 3

class AIQuotaExceededError(AppError):
    def __init__(self) -> None:
        super().__init__(
            ErrorCode.AI_QUOTA_EXCEEDED,
            "Your team has used all of today's assistant requests. "
            "You can still browse the marketplace and enter requirements manually.",
            status_code=429,
        )

async def consume_ai_quota(
    *,
    subject_id: str,
    feature: str,
    subject_type: str = "business",
    settings: Settings | None = None,
) -> int:
    cfg = settings or get_settings()
    limit = cfg.ai_daily_request_quota
    if limit <= 0:
        return 0

    now = utc_now()
    day = now.strftime("%Y-%m-%d")
    col = mongo_manager.collection(CollectionName.AI_USAGE)
    try:
        doc = await col.find_one_and_update(
            {"subject_id": parse_object_id(subject_id), "day": day},
            {
                "$inc": {"count": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "subject_type": subject_type,
                    "created_at": now,
                    "expires_at": now + timedelta(days=_RETENTION_DAYS),
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except Exception:
        logger.warning("AI quota counter unavailable; allowing request", exc_info=True)
        return 0

    used = int((doc or {}).get("count") or 0)
    if used > limit:
        logger.info("ai_quota_exceeded feature=%s used=%s limit=%s", feature, used, limit)
        raise AIQuotaExceededError()
    return used
