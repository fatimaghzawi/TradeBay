
from __future__ import annotations

import asyncio
from typing import Any, Coroutine

from bson import ObjectId

from app.core.logging import get_logger
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

logger = get_logger(__name__)

                                                                         
_EMAIL_SKIP_PREFIXES = ("RFQ_", "QUOTE_", "QUOTATION_", "NEGOTIATION_")
_EMAIL_SKIP_TYPES = frozenset(
    {"TRACKING_UPDATED", "GENERAL", "CONVERSATION_MESSAGE"}
)

def _email_event(event_type: str) -> bool:
    if event_type in _EMAIL_SKIP_TYPES:
        return False
    return not event_type.startswith(_EMAIL_SKIP_PREFIXES)

async def notify(
    *,
    recipient_user_id: str | ObjectId | None = None,
    recipient_business_id: str | ObjectId | None = None,
    type: str,
    title: str,
    message: str | None = None,
    reference_type: str | None = None,
    reference_id: str | ObjectId | None = None,
    fanout_business: bool = True,
    email: bool | None = None,
    cta_path: str | None = None,
) -> int:
    biz_oid = parse_object_id(str(recipient_business_id)) if recipient_business_id else None
    user_oids: list[ObjectId] = []

    if recipient_user_id:
        user_oids.append(parse_object_id(str(recipient_user_id)))
    elif biz_oid is not None and fanout_business:
        cursor = mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).find(
            {"business_account_id": biz_oid, "status": "active"},
            {"user_id": 1},
        )
        async for membership in cursor:
            uid = membership.get("user_id")
            if uid and uid not in user_oids:
                user_oids.append(uid)
        user_oids = user_oids[:25]
    elif biz_oid is not None:
        membership = await mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).find_one(
            {"business_account_id": biz_oid, "status": "active"},
            sort=[("created_at", 1)],
        )
        if membership and membership.get("user_id"):
            user_oids.append(membership["user_id"])

    if not user_oids:
        return 0

    now = utc_now()
    ref = parse_object_id(str(reference_id)) if reference_id else None
    docs: list[dict[str, Any]] = []
    for user_oid in user_oids:
        docs.append(
            {
                "_id": ObjectId(),
                "recipient_user_id": user_oid,
                "recipient_business_id": biz_oid,
                "type": type,
                "title": title,
                "message": message,
                "reference_type": reference_type,
                "reference_id": ref,
                "cta_path": cta_path or _default_cta(reference_type, ref),
                "is_read": False,
                "read_at": None,
                "created_at": now,
            }
        )
    if docs:
        await mongo_manager.collection(CollectionName.NOTIFICATIONS).insert_many(docs)

    send_email = email if email is not None else _email_event(type)
    if send_email:
        email_oids = user_oids
        if fanout_business and biz_oid is not None and len(user_oids) > 1:
            email_oids = await _admin_user_oids(biz_oid) or user_oids[:1]
        coro = _email_personal_inboxes(
            user_oids=email_oids,
            business_id=biz_oid,
            title=title,
            message=message,
            event_type=type,
            cta_path=cta_path or _default_cta(reference_type, ref),
        )
        if _email_should_await():
            await coro
        else:
            _spawn_background(coro)
    return len(docs)

def _email_should_await() -> bool:
    try:
        from app.core.config import get_settings

        if get_settings().is_test:
            return True
    except Exception:
        pass
    return False

def _spawn_background(coro: Coroutine[Any, Any, None]) -> None:
    try:
        task = asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        logger.warning("notification_email_skipped_no_loop")
        return
    task.add_done_callback(_log_background)

def _log_background(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("background_notification_email_failed", error=str(exc))

async def notify_platform_staff(
    *,
    type: str,
    title: str,
    message: str | None = None,
    reference_type: str | None = None,
    reference_id: str | ObjectId | None = None,
    cta_path: str | None = None,
) -> int:
    platform = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
        {"type": "platform"},
        {"_id": 1},
    )
    if platform is None:
        return 0
    return await notify(
        recipient_business_id=platform["_id"],
        type=type,
        title=title,
        message=message,
        reference_type=reference_type,
        reference_id=reference_id,
        cta_path=cta_path or "/admin/suppliers",
    )

async def _admin_user_oids(business_id: ObjectId) -> list[ObjectId]:
    from app.modules.identity.constants import SYSTEM_ROLE_BUSINESS_ADMIN, MembershipStatus

    role_ids = [
        row["_id"]
        async for row in mongo_manager.collection(CollectionName.ROLES).find(
            {
                "business_account_id": business_id,
                "name": SYSTEM_ROLE_BUSINESS_ADMIN,
                "deleted_at": None,
            },
            {"_id": 1},
        )
    ]
    if not role_ids:
        return []
    user_oids: list[ObjectId] = []
    async for membership in mongo_manager.collection(CollectionName.BUSINESS_MEMBERSHIPS).find(
        {
            "business_account_id": business_id,
            "role_id": {"$in": role_ids},
            "status": MembershipStatus.ACTIVE,
        },
        {"user_id": 1},
    ):
        uid = membership.get("user_id")
        if uid and uid not in user_oids:
            user_oids.append(uid)
    return user_oids

async def notify_business_admins(
    *,
    business_id: str | ObjectId,
    type: str,
    title: str,
    message: str | None = None,
    reference_type: str | None = None,
    reference_id: str | ObjectId | None = None,
    cta_path: str | None = None,
    exclude_user_id: str | ObjectId | None = None,
    extra_user_ids: list[str | ObjectId | None] | None = None,
) -> int:
    biz_oid = parse_object_id(str(business_id))
    exclude = parse_object_id(str(exclude_user_id)) if exclude_user_id else None
    user_oids = [uid for uid in await _admin_user_oids(biz_oid) if uid != exclude]
    for raw in extra_user_ids or []:
        if not raw:
            continue
        uid = parse_object_id(str(raw))
        if uid != exclude and uid not in user_oids:
            user_oids.append(uid)
    if not user_oids:
        return 0
    written = 0
    for uid in user_oids:
        written += await notify(
            recipient_user_id=uid,
            recipient_business_id=biz_oid,
            fanout_business=False,
            type=type,
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id,
            cta_path=cta_path or "/members",
        )
    return written

def _default_cta(reference_type: str | None, reference_id: ObjectId | None) -> str:
    rid = str(reference_id) if reference_id else None
    if reference_type == "order" and rid:
        return f"/procurement/orders/{rid}"
    if reference_type == "rfq" and rid:
        return f"/procurement/rfqs/{rid}"
    if reference_type == "shipment" and rid:
        return f"/procurement/shipments/{rid}"
    if reference_type == "quotation":
        return "/quotations"
    if reference_type == "negotiation" and rid:
        return f"/negotiations/{rid}"
    if reference_type == "conversation" and rid:
        return f"/conversations/{rid}"
    if reference_type == "checkout" and rid:
        return f"/orders/checkouts/{rid}"
    if reference_type == "invoice" and rid:
        return f"/finance/invoices/{rid}"
    if reference_type == "invoice":
        return "/finance"
    if reference_type == "dispute":
        return "/notifications"
    if reference_type == "supplier_verification":
        return "/admin/suppliers"
    if reference_type == "invitation":
        return "/accept-invitation"
    if reference_type == "membership":
        return "/members"
    if reference_type == "business":
        return "/settings"
    return "/notifications"

def _personal_inbox(
    user: dict[str, Any],
    *,
    invite_delivery: dict[str, str],
    company_contact: str | None,
) -> str | None:
    login = str(user.get("email") or "").strip().lower()
    stored = str(user.get("personal_email") or "").strip().lower()
    invited = invite_delivery.get(login, "")
    company = (company_contact or "").strip().lower()
    for candidate in (stored, invited, login):
        if candidate and candidate != company:
            return candidate
    if login and login == company:
                                                                               
        return login
    return stored or invited or login or None

async def _email_personal_inboxes(
    *,
    user_oids: list[ObjectId],
    business_id: ObjectId | None,
    title: str,
    message: str | None,
    event_type: str,
    cta_path: str,
) -> None:
    try:
        from app.modules.identity.email import EmailQuotaExhaustedError, get_email_sender
    except Exception:
        return

    users = await mongo_manager.collection(CollectionName.USERS).find(
        {"_id": {"$in": user_oids}},
        {"email": 1, "personal_email": 1, "first_name": 1},
    ).to_list(length=len(user_oids))
    if not users:
        return

    business_name: str | None = None
    company_contact: str | None = None
    invite_delivery: dict[str, str] = {}
    if business_id is not None:
        business = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": business_id},
            {"name": 1, "contact_email": 1},
        )
        if business:
            business_name = str(business.get("name") or "").strip() or None
            company_contact = str(business.get("contact_email") or "").strip().lower() or None
        logins = [str(u.get("email") or "").strip().lower() for u in users if u.get("email")]
        if logins:
            cursor = mongo_manager.collection(CollectionName.INVITATIONS).find(
                {
                    "business_account_id": business_id,
                    "invited_email": {"$in": logins},
                    "delivery_email": {"$exists": True, "$nin": [None, ""]},
                },
                {"invited_email": 1, "delivery_email": 1, "accepted_at": 1, "created_at": 1},
            )
            async for row in cursor:
                login = str(row.get("invited_email") or "").strip().lower()
                delivery = str(row.get("delivery_email") or "").strip().lower()
                if login and delivery:
                    invite_delivery[login] = delivery

    sender = get_email_sender()
    seen: set[str] = set()
    for user in users:
        to = _personal_inbox(
            user,
            invite_delivery=invite_delivery,
            company_contact=company_contact,
        )
        if not to or to in seen:
            continue
        seen.add(to)
        try:
            await sender.send(
                to=to,
                template="business_event",
                context={
                    "title": title,
                    "message": message or "",
                    "business_name": business_name or "",
                    "first_name": user.get("first_name") or "",
                    "event_type": event_type,
                    "cta_path": cta_path,
                },
            )
        except EmailQuotaExhaustedError:
            logger.warning(
                "event_email_skipped_quota",
                event_type=event_type,
                remaining=max(len(users) - len(seen), 0),
            )
            return
        except Exception as exc:
            logger.warning(
                "event_email_failed",
                to=to,
                event_type=event_type,
                error=str(exc),
            )
