
from __future__ import annotations

import asyncio

from app.db.mongodb import mongo_manager
from app.modules.catalog.constants import ProductStatus
from app.modules.identity.constants import (
    BusinessAccountStatus,
    SupplierVerificationStatus,
)
from app.shared.utils.datetime import utc_now

async def main() -> None:
    await mongo_manager.connect()
    db = mongo_manager.database
    now = utc_now()
    blocked = await db.supplier_profiles.find(
        {
            "verification_status": {
                "$in": [
                    SupplierVerificationStatus.REVOKED,
                    SupplierVerificationStatus.REJECTED,
                    SupplierVerificationStatus.UNVERIFIED,
                    SupplierVerificationStatus.PENDING,
                ]
            }
        }
    ).to_list(None)
    ids = [p["business_account_id"] for p in blocked if p.get("business_account_id")]
    print("blocked_suppliers", len(ids))
    if ids:
        result = await db.products.update_many(
            {
                "business_account_id": {"$in": ids},
                "status": {"$ne": ProductStatus.INACTIVE},
            },
            {
                "$set": {
                    "status": ProductStatus.INACTIVE,
                    "updated_at": now,
                    "deactivated_reason": "supplier_not_verified",
                }
            },
        )
        print("products_deactivated", result.modified_count)
        cart = await db.cart_items.delete_many({"supplier_business_id": {"$in": ids}})
        print("cart_lines_removed", cart.deleted_count)

    revoked = [
        p["business_account_id"]
        for p in blocked
        if p.get("verification_status") == SupplierVerificationStatus.REVOKED
        and p.get("business_account_id")
    ]
    if revoked:
        br = await db.business_accounts.update_many(
            {
                "_id": {"$in": revoked},
                "status": {"$ne": BusinessAccountStatus.SUSPENDED},
            },
            {"$set": {"status": BusinessAccountStatus.SUSPENDED, "updated_at": now}},
        )
        print("businesses_suspended", br.modified_count)

    await mongo_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
