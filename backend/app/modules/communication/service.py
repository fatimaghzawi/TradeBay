
from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.communication.constants import (
    CONTEXTLESS_CONVERSATION_TYPES,
    ConversationStatus,
    ConversationType,
    MessageReferenceType,
    MessageType,
    ParticipantRole,
    SystemEvent,
)
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id


class ConversationNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("We couldn't find that conversation.")

class CommunicationService:
    def _biz_id(self, business: dict[str, Any] | None) -> str:
        if not business:
            raise ForbiddenError("Select a company to continue")
        return str(business["_id"])

    @staticmethod
    def _pair_query(left: ObjectId, right: ObjectId) -> dict[str, Any]:
        return {
            "status": {"$ne": ConversationStatus.ARCHIVED},
            "$or": [
                {"initiator_business_id": left, "counterparty_business_id": right},
                {"initiator_business_id": right, "counterparty_business_id": left},
            ],
        }

    async def _find_pair_conversation(
        self, left: ObjectId, right: ObjectId
    ) -> dict[str, Any] | None:
        rows = (
            await mongo_manager.collection(CollectionName.CONVERSATIONS)
            .find(self._pair_query(left, right))
            .sort([("last_message_at", -1), ("created_at", -1)])
            .to_list(length=25)
        )
        if not rows:
            return None
        active = [row for row in rows if row.get("status") == ConversationStatus.ACTIVE]
        return (active or rows)[0]

    @staticmethod
    def _one_thread_per_pair(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        unique: list[dict[str, Any]] = []
        for row in rows:
            pair = tuple(
                sorted(
                    (
                        str(row.get("initiator_business_id") or ""),
                        str(row.get("counterparty_business_id") or ""),
                    )
                )
            )
            if pair in seen:
                continue
            seen.add(pair)
            unique.append(row)
        return unique

    async def list_inbox(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        bid = parse_object_id(self._biz_id(business))
        col = mongo_manager.collection(CollectionName.CONVERSATIONS)
        query = {
            "$or": [
                {"initiator_business_id": bid},
                {"counterparty_business_id": bid},
            ],
            "status": {"$ne": ConversationStatus.ARCHIVED},
        }
        total = await col.count_documents(query)
        rows = (
            await col.find(query)
            .sort([("last_message_at", -1), ("created_at", -1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        rows = self._one_thread_per_pair(rows)
        out: list[dict[str, Any]] = []
        for row in rows:
            part = await self._ensure_participant(
                conversation=row,
                user_id=user_id,
                business_id=bid,
                role=ParticipantRole.MEMBER,
            )
            serialized = await self._serialize_conversation(
                row, viewer_business_id=str(bid), participant=part
            )
            out.append(serialized)
        return out, total

    async def unread_inbox_count(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
    ) -> int:
        bid = parse_object_id(self._biz_id(business))
        convs = (
            await mongo_manager.collection(CollectionName.CONVERSATIONS)
            .find(
                {
                    "$or": [
                        {"initiator_business_id": bid},
                        {"counterparty_business_id": bid},
                    ],
                    "status": {"$ne": ConversationStatus.ARCHIVED},
                },
                {"_id": 1},
            )
            .to_list(length=500)
        )
        if not convs:
            return 0
        convs = self._one_thread_per_pair(convs)
        ids = [row["_id"] for row in convs]
        parts = (
            await mongo_manager.collection(CollectionName.CONVERSATION_PARTICIPANTS)
            .find(
                {
                    "conversation_id": {"$in": ids},
                    "user_id": parse_object_id(user_id),
                    "left_at": None,
                },
                {"conversation_id": 1, "last_read_at": 1},
            )
            .to_list(length=500)
        )
        last_read = {row["conversation_id"]: row.get("last_read_at") for row in parts}
        total = 0
        for cid in ids:
            total += await self._unread_count(cid, last_read.get(cid))
        return total

    async def get(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
        mark_read: bool = True,
    ) -> dict[str, Any]:
        conv, part = await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        if mark_read:
            part = await self.mark_read(
                user_id=user_id, business=business, conversation_id=conversation_id
            )
                                             
            part = await self._get_participant(conv["_id"], user_id) or part
        return await self._serialize_conversation(
            conv, viewer_business_id=self._biz_id(business), participant=part
        )

    async def open_or_get(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        counterparty_business_id: str,
        type_: str = ConversationType.DIRECT,
        context_type: str | None = None,
        context_id: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        bid = self._biz_id(business)
        if bid == counterparty_business_id:
            raise BadRequestError("You can't start a conversation with your own company.")
        if type_ not in {t.value for t in ConversationType}:
            raise BadRequestError("This kind of conversation isn't available.")
        if type_ not in CONTEXTLESS_CONVERSATION_TYPES and (not context_type or not context_id):
            raise BadRequestError("Start this conversation from an RFQ, quotation, or order")

        col = mongo_manager.collection(CollectionName.CONVERSATIONS)
        initiator = parse_object_id(bid)
        counterparty = parse_object_id(counterparty_business_id)
        await self._assert_counterparty(counterparty)
        if context_type and context_id:
            await self._assert_context_parties(context_type, context_id, {bid, str(counterparty)})

        existing = await self._find_pair_conversation(initiator, counterparty)
        if existing:
            return await self._reuse_conversation(
                existing=existing,
                user_id=user_id,
                viewer_business_id=bid,
                initiator=initiator,
                type_=type_,
                context_type=context_type,
                context_id=context_id,
                subject=subject,
            )

        now = utc_now()
        doc = {
            "_id": ObjectId(),
            "subject": (subject or "").strip() or None,
            "type": type_,
            "context_type": context_type,
            "context_id": parse_object_id(context_id) if context_id else None,
            "initiator_business_id": initiator,
            "counterparty_business_id": counterparty,
            "created_by_user_id": parse_object_id(user_id),
            "status": ConversationStatus.ACTIVE,
            "last_message_at": None,
            "last_message_preview": None,
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await col.insert_one(doc)
        except DuplicateKeyError:
            existing = await self._find_pair_conversation(initiator, counterparty)
            if existing is None:
                raise
            return await self._reuse_conversation(
                existing=existing,
                user_id=user_id,
                viewer_business_id=bid,
                initiator=initiator,
                type_=type_,
                context_type=context_type,
                context_id=context_id,
                subject=subject,
            )
        await self._ensure_participant(
            conversation=doc,
            user_id=user_id,
            business_id=initiator,
            role=ParticipantRole.OWNER,
        )
        return await self._serialize_conversation(doc, viewer_business_id=bid)

    async def _assert_counterparty(self, counterparty: ObjectId) -> None:
        other = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": counterparty}, {"status": 1, "deleted_at": 1}
        )
        if other is None or other.get("deleted_at") or other.get("status") == "suspended":
            raise NotFoundError("We couldn't find that company.")

    async def _assert_context_parties(
        self, context_type: str, context_id: str, parties: set[str]
    ) -> None:
        oid = parse_object_id(context_id)
        db = mongo_manager
        allowed: set[str] = set()
        if context_type == "rfq":
            rfq = await db.collection(CollectionName.RFQS).find_one({"_id": oid})
            if rfq is not None:
                allowed.add(str(rfq.get("buyer_business_id")))
                sides = {str(rfq.get("supplier_business_id") or "")}
                sides |= {
                    str(i.get("supplier_business_id"))
                    for i in rfq.get("supplier_invites") or []
                }
                async for q in db.collection(CollectionName.QUOTATIONS).find(
                    {"rfq_id": oid}, {"supplier_id": 1}
                ):
                    sides.add(str(q.get("supplier_id")))
                other = parties - allowed
                if len(other) == 1 and other <= sides:
                    allowed |= other
        elif context_type in {"order", "negotiation", "dispute"}:
            collection = {
                "order": CollectionName.ORDERS,
                "negotiation": CollectionName.NEGOTIATIONS,
                "dispute": CollectionName.DISPUTES,
            }[context_type]
            doc = await db.collection(collection).find_one(
                {"_id": oid}, {"buyer_business_id": 1, "supplier_business_id": 1}
            )
            if doc is not None:
                allowed = {str(doc.get("buyer_business_id")), str(doc.get("supplier_business_id"))}
        elif context_type == "quotation":
            doc = await db.collection(CollectionName.QUOTATIONS).find_one(
                {"_id": oid}, {"buyer_business_id": 1, "supplier_id": 1}
            )
            if doc is not None:
                allowed = {str(doc.get("buyer_business_id")), str(doc.get("supplier_id"))}
        elif context_type == "product":
            doc = await db.collection(CollectionName.PRODUCTS).find_one(
                {"_id": oid, "deleted_at": None}, {"business_account_id": 1}
            )
            if doc is not None and str(doc.get("business_account_id")) in parties:
                allowed = set(parties)
        if not parties <= allowed:
            raise ForbiddenError("This conversation can only be linked to a deal both companies are part of.")

    async def _reuse_conversation(
        self,
        *,
        existing: dict[str, Any],
        user_id: str,
        viewer_business_id: str,
        initiator: ObjectId,
        type_: str,
        context_type: str | None,
        context_id: str | None,
        subject: str | None,
    ) -> dict[str, Any]:
        now = utc_now()
        updates: dict[str, Any] = {"updated_at": now}
        if existing.get("status") == ConversationStatus.CLOSED:
            updates["status"] = ConversationStatus.ACTIVE
        if context_type and context_id:
            updates["context_type"] = context_type
            updates["context_id"] = parse_object_id(context_id)
            if type_ not in CONTEXTLESS_CONVERSATION_TYPES:
                updates["type"] = type_
        label = (subject or "").strip()
        if label and not existing.get("subject"):
            updates["subject"] = label
        if updates:
            await mongo_manager.collection(CollectionName.CONVERSATIONS).update_one(
                {"_id": existing["_id"]},
                {"$set": updates},
            )
            existing.update(updates)
        await self._ensure_participant(
            conversation=existing,
            user_id=user_id,
            business_id=initiator,
            role=ParticipantRole.MEMBER,
        )
        return await self._serialize_conversation(
            existing, viewer_business_id=viewer_business_id
        )

    async def list_messages(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
        page: int = 1,
        page_size: int = 50,
        after: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        col = mongo_manager.collection(CollectionName.MESSAGES)
        oid = parse_object_id(conversation_id)
        query: dict[str, Any] = {"conversation_id": oid}
                                                                                   
        if after:
            try:
                after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
                query["created_at"] = {"$gt": after_dt}
            except ValueError as exc:
                raise BadRequestError("Couldn't load messages from that position—check the cursor and try again") from exc
        total = await col.count_documents({"conversation_id": oid})
        rows = (
            await col.find(query)
            .sort("created_at", 1)
            .skip((page - 1) * page_size if not after else 0)
            .limit(page_size)
            .to_list(length=page_size)
        )
        return [self._serialize_message(r) for r in rows], total

    async def send_message(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
        body: str | None = None,
        message_type: str = MessageType.TEXT,
        reply_to_message_id: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> dict[str, Any]:
        conv, _part = await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        if conv.get("status") != ConversationStatus.ACTIVE:
            raise BadRequestError("This conversation is closed, so new messages can't be sent.")

        if message_type not in {
            MessageType.TEXT,
            MessageType.ATTACHMENT,
            MessageType.REFERENCE,
        }:
            raise BadRequestError("This kind of message can't be sent here.")
        if message_type == MessageType.SYSTEM:
            raise BadRequestError("This kind of message can't be sent here.")

        text = (body or "").strip()
        if message_type == MessageType.TEXT and not text:
            raise BadRequestError("Write a message before sending.")
        if len(text) > 8000:
            raise BadRequestError("This message is too long. Keep it under 8,000 characters.")

        if message_type == MessageType.REFERENCE:
            if not reference_type or not reference_id:
                raise BadRequestError("Attach a linked document to share it in this conversation")
            if reference_type not in {t.value for t in MessageReferenceType}:
                raise BadRequestError("That kind of document can't be shared here.")
                                                                                                 
            text = text or None
        else:
            reference_type = None
            reference_id = None

        reply_oid = None
        if reply_to_message_id:
            parent = await mongo_manager.collection(CollectionName.MESSAGES).find_one(
                {
                    "_id": parse_object_id(reply_to_message_id),
                    "conversation_id": conv["_id"],
                }
            )
            if parent is None:
                raise BadRequestError("The message you're replying to wasn't found in this conversation")
            reply_oid = parent["_id"]

        now = utc_now()
        bid = parse_object_id(self._biz_id(business))
        msg = {
            "_id": ObjectId(),
            "conversation_id": conv["_id"],
            "sender_user_id": parse_object_id(user_id),
            "sender_business_id": bid,
            "message_type": message_type,
            "body": text,
            "attachments": [],
            "reply_to_message_id": reply_oid,
            "reference_type": reference_type,
            "reference_id": parse_object_id(reference_id) if reference_id else None,
            "system_event": None,
            "created_at": now,
            "edited_at": None,
            "deleted_at": None,
        }
        await mongo_manager.collection(CollectionName.MESSAGES).insert_one(msg)
        preview = self._preview_for(msg)
        await mongo_manager.collection(CollectionName.CONVERSATIONS).update_one(
            {"_id": conv["_id"]},
            {
                "$set": {
                    "last_message_at": now,
                    "last_message_preview": preview,
                    "updated_at": now,
                },
                "$inc": {"message_count": 1},
            },
        )
        await self._ensure_participant(
            conversation=conv,
            user_id=user_id,
            business_id=bid,
            role=ParticipantRole.MEMBER,
            last_read_at=now,
        )
                                                                                 
                                                       
        return self._serialize_message(msg)

    async def edit_message(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
        message_id: str,
        body: str,
    ) -> dict[str, Any]:
        await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        text = (body or "").strip()
        if not text:
            raise BadRequestError("Write a message before saving.")
        if len(text) > 8000:
            raise BadRequestError("This message is too long. Keep it under 8,000 characters.")
        now = utc_now()
        from pymongo import ReturnDocument

        updated = await mongo_manager.collection(CollectionName.MESSAGES).find_one_and_update(
            {
                "_id": parse_object_id(message_id),
                "conversation_id": parse_object_id(conversation_id),
                "sender_user_id": parse_object_id(user_id),
                "message_type": MessageType.TEXT,
                "deleted_at": None,
            },
            {"$set": {"body": text, "edited_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise NotFoundError("You can only edit your own messages that haven't been removed.")
        return self._serialize_message(updated)

    async def soft_delete_message(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        now = utc_now()
        from pymongo import ReturnDocument

        updated = await mongo_manager.collection(CollectionName.MESSAGES).find_one_and_update(
            {
                "_id": parse_object_id(message_id),
                "conversation_id": parse_object_id(conversation_id),
                "sender_user_id": parse_object_id(user_id),
                "deleted_at": None,
                "message_type": {"$ne": MessageType.SYSTEM},
            },
            {"$set": {"body": None, "deleted_at": now, "attachments": []}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise NotFoundError("This message was already removed or isn't yours to remove.")
        return self._serialize_message(updated)

    async def mark_read(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
    ) -> dict[str, Any]:
        conv, part = await self._require_participant_access(
            user_id=user_id, business=business, conversation_id=conversation_id
        )
        now = utc_now()
        await mongo_manager.collection(CollectionName.CONVERSATION_PARTICIPANTS).update_one(
            {"_id": part["_id"]},
            {"$set": {"last_read_at": now, "updated_at": now}},
        )
        part["last_read_at"] = now
        return await self._serialize_conversation(
            conv, viewer_business_id=self._biz_id(business), participant=part
        )

    async def post_system_event(
        self,
        *,
        context_type: str,
        context_id: str,
        system_event: str,
        body: str,
        initiator_business_id: str | None = None,
        counterparty_business_id: str | None = None,
        subject: str | None = None,
        type_: str | None = None,
    ) -> dict[str, Any] | None:
        if system_event not in {e.value for e in SystemEvent}:
            raise BadRequestError("Unrecognized system event")
        col = mongo_manager.collection(CollectionName.CONVERSATIONS)
        ctx_oid = parse_object_id(context_id)
        lookup: dict[str, Any] = {
            "context_type": context_type,
            "context_id": ctx_oid,
            "status": {"$ne": ConversationStatus.ARCHIVED},
        }
        if initiator_business_id and counterparty_business_id:
                                                                                  
            lookup = {
                **self._pair_query(
                    parse_object_id(initiator_business_id),
                    parse_object_id(counterparty_business_id),
                ),
                "context_type": context_type,
                "context_id": ctx_oid,
            }
        conv = await col.find_one(lookup)
        if conv is None and initiator_business_id and counterparty_business_id:
            conv = await self._find_pair_conversation(
                parse_object_id(initiator_business_id),
                parse_object_id(counterparty_business_id),
            )
            if conv is not None:
                await col.update_one(
                    {"_id": conv["_id"]},
                    {
                        "$set": {
                            "context_type": context_type,
                            "context_id": ctx_oid,
                            "updated_at": utc_now(),
                            **(
                                {"status": ConversationStatus.ACTIVE}
                                if conv.get("status") == ConversationStatus.CLOSED
                                else {}
                            ),
                        }
                    },
                )
                conv["context_type"] = context_type
                conv["context_id"] = ctx_oid
        if conv is None:
            if not initiator_business_id or not counterparty_business_id:
                return None
            now = utc_now()
            mapped_type = type_ or {
                "rfq": ConversationType.RFQ,
                "quotation": ConversationType.QUOTATION,
                "negotiation": ConversationType.NEGOTIATION,
                "order": ConversationType.ORDER,
                "dispute": ConversationType.DISPUTE,
                "product": ConversationType.PRODUCT_INQUIRY,
            }.get(context_type, ConversationType.DIRECT)
            conv = {
                "_id": ObjectId(),
                "subject": subject,
                "type": mapped_type,
                "context_type": context_type,
                "context_id": parse_object_id(context_id),
                "initiator_business_id": parse_object_id(initiator_business_id),
                "counterparty_business_id": parse_object_id(counterparty_business_id),
                "created_by_user_id": None,
                "status": ConversationStatus.ACTIVE,
                "last_message_at": None,
                "last_message_preview": None,
                "message_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            await col.insert_one(conv)

        now = utc_now()
        msg = {
            "_id": ObjectId(),
            "conversation_id": conv["_id"],
            "sender_user_id": None,
            "sender_business_id": None,
            "message_type": MessageType.SYSTEM,
            "body": body.strip(),
            "attachments": [],
            "reply_to_message_id": None,
            "reference_type": None,
            "reference_id": None,
            "system_event": system_event,
            "created_at": now,
            "edited_at": None,
            "deleted_at": None,
        }
        await mongo_manager.collection(CollectionName.MESSAGES).insert_one(msg)
        preview = body.strip()[:140]
        await col.update_one(
            {"_id": conv["_id"]},
            {
                "$set": {
                    "last_message_at": now,
                    "last_message_preview": preview,
                    "updated_at": now,
                },
                "$inc": {"message_count": 1},
            },
        )
        return self._serialize_message(msg)

    async def _require_participant_access(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        conversation_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        bid = self._biz_id(business)
        conv = await mongo_manager.collection(CollectionName.CONVERSATIONS).find_one(
            {"_id": parse_object_id(conversation_id)}
        )
        if conv is None:
            raise ConversationNotFoundError()
        self._assert_party(conv, bid)
        part = await self._ensure_participant(
            conversation=conv,
            user_id=user_id,
            business_id=parse_object_id(bid),
            role=ParticipantRole.MEMBER,
        )
        if part.get("left_at") is not None:
            raise ForbiddenError("You have left this conversation")
        return conv, part

    async def _ensure_participant(
        self,
        *,
        conversation: dict[str, Any],
        user_id: str,
        business_id: ObjectId,
        role: str,
        last_read_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        parts = mongo_manager.collection(CollectionName.CONVERSATION_PARTICIPANTS)
        existing = await parts.find_one(
            {
                "conversation_id": conversation["_id"],
                "user_id": parse_object_id(user_id),
            }
        )
        if existing:
            updates: dict[str, Any] = {
                "business_account_id": business_id,
                "updated_at": now,
            }
            if last_read_at is not None:
                updates["last_read_at"] = last_read_at
            if existing.get("left_at") is not None:
                updates["left_at"] = None
                updates["joined_at"] = now
            await parts.update_one({"_id": existing["_id"]}, {"$set": updates})
            existing.update(updates)
            return existing

        doc = {
            "_id": ObjectId(),
            "conversation_id": conversation["_id"],
            "user_id": parse_object_id(user_id),
            "business_account_id": business_id,
            "role": role,
            "last_read_at": last_read_at,
            "is_muted": False,
            "joined_at": now,
            "left_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await parts.insert_one(doc)
        return doc

    async def _get_participant(
        self, conversation_id: ObjectId, user_id: str
    ) -> dict[str, Any] | None:
        return await mongo_manager.collection(CollectionName.CONVERSATION_PARTICIPANTS).find_one(
            {
                "conversation_id": conversation_id,
                "user_id": parse_object_id(user_id),
            }
        )

    def _assert_party(self, conv: dict[str, Any], business_id: str) -> None:
        if business_id not in {
            str(conv.get("initiator_business_id")),
            str(conv.get("counterparty_business_id")),
        }:
            raise ForbiddenError("This conversation belongs to other companies.")

    async def _unread_count(
        self, conversation_id: ObjectId, last_read_at: datetime | None
    ) -> int:
                                                                        
        query: dict[str, Any] = {"conversation_id": conversation_id, "deleted_at": None}
        if last_read_at is not None:
            query["created_at"] = {"$gt": last_read_at}
        return int(
            await mongo_manager.collection(CollectionName.MESSAGES).count_documents(query)
        )

    async def _business_card(self, business_id: ObjectId | None) -> dict[str, str | None]:
        empty = {"name": None, "logo_url": None}
        if not business_id:
            return empty
        row = await mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS).find_one(
            {"_id": business_id},
            {"name": 1, "logo_url": 1},
        )
        if not row:
            return empty
        return {"name": row.get("name"), "logo_url": row.get("logo_url")}

    async def _business_name(self, business_id: ObjectId | None) -> str | None:
        return (await self._business_card(business_id))["name"]

    def _preview_for(self, msg: dict[str, Any]) -> str:
        if msg.get("deleted_at"):
            return "Message removed"
        if msg.get("message_type") == MessageType.REFERENCE:
            return f"Shared {msg.get('reference_type') or 'document'}"
        if msg.get("message_type") == MessageType.SYSTEM:
            return (msg.get("body") or msg.get("system_event") or "Update")[:140]
        text = msg.get("body") or ""
        return text if len(text) <= 140 else f"{text[:137]}..."

    async def _serialize_conversation(
        self,
        doc: dict[str, Any],
        *,
        viewer_business_id: str | None = None,
        participant: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        initiator = doc.get("initiator_business_id")
        counterparty = doc.get("counterparty_business_id")
        other = None
        if viewer_business_id:
            if str(initiator) == viewer_business_id:
                other = counterparty
            elif str(counterparty) == viewer_business_id:
                other = initiator
        unread = 0
        last_read_at = None
        if participant is not None:
            last_read_at = participant.get("last_read_at")
            unread = await self._unread_count(doc["_id"], last_read_at)
        other_card = await self._business_card(other)
        return {
            "id": str(doc["_id"]),
            "subject": doc.get("subject"),
            "type": doc.get("type"),
            "context_type": doc.get("context_type"),
            "context_id": str(doc["context_id"]) if doc.get("context_id") else None,
            "initiator_business_id": str(initiator) if initiator else None,
            "counterparty_business_id": str(counterparty) if counterparty else None,
            "counterparty_name": other_card["name"],
            "counterparty_logo_url": other_card["logo_url"],
            "status": doc.get("status"),
            "last_message_at": doc.get("last_message_at").isoformat()
            if doc.get("last_message_at")
            else None,
            "last_message_preview": doc.get("last_message_preview"),
            "message_count": int(doc.get("message_count") or 0),
            "unread_count": unread,
            "last_read_at": last_read_at.isoformat() if last_read_at else None,
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        }

    def _serialize_message(self, doc: dict[str, Any]) -> dict[str, Any]:
        deleted = doc.get("deleted_at") is not None
        return {
            "id": str(doc["_id"]),
            "conversation_id": str(doc["conversation_id"]) if doc.get("conversation_id") else None,
            "sender_user_id": str(doc["sender_user_id"]) if doc.get("sender_user_id") else None,
            "sender_business_id": str(doc["sender_business_id"])
            if doc.get("sender_business_id")
            else None,
            "message_type": doc.get("message_type"),
            "body": None if deleted else doc.get("body"),
            "is_deleted": deleted,
            "reply_to_message_id": str(doc["reply_to_message_id"])
            if doc.get("reply_to_message_id")
            else None,
            "reference_type": doc.get("reference_type"),
            "reference_id": str(doc["reference_id"]) if doc.get("reference_id") else None,
            "system_event": doc.get("system_event"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "edited_at": doc.get("edited_at").isoformat() if doc.get("edited_at") else None,
            "deleted_at": doc.get("deleted_at").isoformat() if doc.get("deleted_at") else None,
        }
