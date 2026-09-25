
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.modules.identity.service import BusinessService
from app.shared.utils.datetime import set_seed_clock


async def run_verification_reviews(
    *, plan: list[dict[str, Any]], reviewer_user_id: str, founded: datetime
) -> None:
    service = BusinessService()
    for offset, entry in enumerate(plan):
        business_id = str(entry["business"]["_id"])
        owner_id = str(entry["owner"]["_id"])
        decision = entry["decision"]
        submitted = founded + timedelta(days=3, hours=offset * 5)
        set_seed_clock(submitted)
        await service.submit_supplier_verification(
            user_id=owner_id, business_id=business_id, documents=entry["documents"]
        )
        if decision == "pending":
            continue
        set_seed_clock(submitted + timedelta(days=6, hours=3))
        if decision == "rejected":
            await service.review_supplier_verification(
                business_id=business_id,
                decision="reject",
                actor_user_id=reviewer_user_id,
                reason=entry.get("reason") or "Documents could not be matched to the company register.",
            )
            continue
        await service.review_supplier_verification(
            business_id=business_id, decision="approve", actor_user_id=reviewer_user_id
        )
        if decision == "revoked":
            set_seed_clock(submitted + timedelta(days=70))
            await service.review_supplier_verification(
                business_id=business_id,
                decision="revoke",
                actor_user_id=reviewer_user_id,
                reason=entry.get("reason") or "Tax certificate expired and was not renewed.",
            )
    set_seed_clock(None)
