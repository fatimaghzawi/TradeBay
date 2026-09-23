"""Atomic document numbering — never count()+1 under concurrency."""

from __future__ import annotations

from pymongo import ReturnDocument

from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.shared.repositories.base import MongoSession
from app.shared.utils.datetime import utc_now


async def allocate_document_number(
    *,
    kind: str,
    prefix: str,
    session: MongoSession = None,
    width: int = 4,
) -> str:
    """Return `{prefix}-{year}-{seq}` using an atomic counter per kind/prefix/year."""
    clean_prefix = (prefix or "TB-INV").strip().upper()
    if not clean_prefix:
        clean_prefix = "TB-INV"
    year = utc_now().year
    counter_id = f"{kind}:{clean_prefix}:{year}"
    now = utc_now()
    doc = await mongo_manager.collection(CollectionName.DOCUMENT_COUNTERS).find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}, "$setOnInsert": {"created_at": now}, "$set": {"updated_at": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    seq = int((doc or {}).get("seq") or 1)
    return f"{clean_prefix}-{year}-{seq:0{width}d}"
