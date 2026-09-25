
from __future__ import annotations

import contextlib
import re

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure

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

async def allocate_seeded_number(
    prefix: str,
    collection: str,
    field: str,
    *,
    session: MongoSession = None,
) -> str:
    year = utc_now().year
    head = f"{prefix}-{year}-"
    counters = mongo_manager.collection(CollectionName.DOCUMENT_COUNTERS)
    counter_id = f"{collection}:{prefix}:{year}"

    if await counters.find_one({"_id": counter_id}, {"_id": 1}) is None:
        source = mongo_manager.collection(str(collection))
        query = {field: {"$regex": f"^{re.escape(head)}"}}
        baseline = await source.count_documents(query)
        async for row in source.find(query, {field: 1}):
            suffix = str(row.get(field) or "")[len(head):]
            if suffix.isdigit():
                baseline = max(baseline, int(suffix))
        with contextlib.suppress(DuplicateKeyError):
            await counters.insert_one({"_id": counter_id, "seq": baseline, "created_at": utc_now()})

    doc = await counters.find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}, "$set": {"updated_at": utc_now()}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if doc is None:
                                                                                          
                                                                                        
        raise OperationFailure(
            f"Counter {counter_id} not visible in transaction snapshot",
            code=112,
            details={"errorLabels": ["TransientTransactionError"]},
        )
    return f"{head}{int(doc['seq']):04d}"
