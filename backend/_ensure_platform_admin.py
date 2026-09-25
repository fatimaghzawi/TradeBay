
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from bson import ObjectId

def _load_dotenv() -> None:
    for path in (Path(__file__).resolve().parents[1] / ".env", Path(__file__).resolve().parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))

async def main() -> None:
    _load_dotenv()
    from app.core.config import reset_settings_cache
    from app.db.mongodb import mongo_manager
    from app.core.security import hash_password
    from app.modules.identity.constants import (
        SYSTEM_ROLE_PLATFORM_ADMIN,
        MembershipStatus,
        UserStatus,
    )
    from app.shared.utils.datetime import utc_now

    reset_settings_cache()
    from app.core.config import get_settings

    settings = get_settings()
    if settings.is_production or settings.app_env == "production":
        raise SystemExit("Refusing to reset the platform admin password in production.")
    await mongo_manager.connect()
    db = mongo_manager.database

    email = "admin@tradebay.com"
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or "AdminPass123!"

    platform = await db["business_accounts"].find_one({"type": "platform"})
    if platform is None:
        raise SystemExit("Platform business missing — start the API once so seed can run.")

    role = await db["roles"].find_one(
        {"business_account_id": platform["_id"], "name": SYSTEM_ROLE_PLATFORM_ADMIN}
    )
    if role is None:
        raise SystemExit("Platform Admin role missing — restart API to re-seed roles.")

    user = await db["users"].find_one({"email": email})
    now = utc_now()
    if user is None:
        user = {
            "_id": ObjectId(),
            "email": email,
            "password_hash": hash_password(password),
            "first_name": "Platform",
            "last_name": "Admin",
            "phone": None,
            "status": UserStatus.ACTIVE,
            "email_verified_at": now,
            "created_at": now,
            "updated_at": now,
        }
        await db["users"].insert_one(user)
        print("created_user")
    else:
        await db["users"].update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_hash": hash_password(password),
                    "status": UserStatus.ACTIVE,
                    "email_verified_at": user.get("email_verified_at") or now,
                    "updated_at": now,
                }
            },
        )
        print("updated_user_password")

    membership = await db["business_memberships"].find_one(
        {"user_id": user["_id"], "business_account_id": platform["_id"]}
    )
    if membership is None:
        await db["business_memberships"].insert_one(
            {
                "_id": ObjectId(),
                "user_id": user["_id"],
                "business_account_id": platform["_id"],
                "role_id": role["_id"],
                "status": MembershipStatus.ACTIVE,
                "joined_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
        print("created_membership")
    else:
        await db["business_memberships"].update_one(
            {"_id": membership["_id"]},
            {
                "$set": {
                    "role_id": role["_id"],
                    "status": MembershipStatus.ACTIVE,
                    "updated_at": now,
                }
            },
        )
        print("updated_membership")

    print(f"EMAIL={email}")
    print(f"PASSWORD={password}")
    print("After login, switch to the TradeBay platform company if needed, then open /admin")
    await mongo_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
