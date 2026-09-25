
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import mongo_manager
from app.modules.identity.dependencies import (
    AuthContext,
    get_current_business,
    get_current_membership,
    get_current_user,
    require_permission,
    require_seller,
    require_verified_email,
)

__all__ = [
    "AuthContext",
    "get_current_business",
    "get_current_membership",
    "get_current_user",
    "get_db",
    "require_permission",
    "require_seller",
    "require_verified_email",
]

async def get_db() -> AsyncIOMotorDatabase[Any]:
    return mongo_manager.database
