
from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.transactions import run_in_transaction
from app.modules.platform_money.commission import commission_rate
from app.modules.platform_money.constants import CommissionBase, CommissionType
from app.modules.settings.constants import SINGLETON_KEY, TaxType
from app.modules.settings.repository import (
    BusinessSettingsRepository,
    PlatformSettingsRepository,
    TaxSettingsRepository,
)
from app.modules.settings.tax import MAX_TAX_RATE, as_decimal, money, tax_is_effective
from app.shared.repositories.base import MongoSession
from app.shared.services.audit import AuditService
from app.shared.types.money import to_decimal128
from app.shared.utils.datetime import utc_now
from app.shared.utils.objectid import parse_object_id

ALLOWED_CURRENCIES = frozenset({"USD", "LBP"})

def _money_out(value: Any) -> str | None:
    if value is None:
        return None
    return format(money(value), "f")

class SettingsService:
    def __init__(
        self,
        *,
        platform_repo: PlatformSettingsRepository | None = None,
        tax_repo: TaxSettingsRepository | None = None,
        business_repo: BusinessSettingsRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.platform = platform_repo or PlatformSettingsRepository()
        self.tax = tax_repo or TaxSettingsRepository()
        self.business = business_repo or BusinessSettingsRepository()
        self.audit = audit or AuditService()

    def _require_platform_admin(self, business: dict[str, Any] | None) -> dict[str, Any]:
        if not business or str(business.get("type")) != "platform":
            raise ForbiddenError("Only platform administrators can manage system settings")
        return business

    async def get_all(self, *, business: dict[str, Any] | None) -> dict[str, Any]:
        self._require_platform_admin(business)
        platform = await self.platform.find_one({"key": SINGLETON_KEY})
        letterhead = await self.business.find_one({"key": SINGLETON_KEY})
        active_tax = await self.get_active_tax()
        tax_history = await self.tax.find_many({}, limit=20, sort=[("effective_from", -1)])
        return {
            "platform": self._serialize_platform(platform) if platform else None,
            "tax": self._serialize_tax(active_tax) if active_tax else None,
            "tax_history": [self._serialize_tax(t) for t in tax_history],
            "business": self._serialize_business(letterhead) if letterhead else None,
        }

    async def get_active_tax(self, *, at: datetime | None = None) -> dict[str, Any] | None:
        moment = at or utc_now()
        rows = await self.tax.find_many({"is_active": True}, limit=5)
        for row in rows:
            if tax_is_effective(row, at=moment):
                return row
                                                                         
        history = await self.tax.find_many({}, limit=50, sort=[("effective_from", -1)])
        for row in history:
            start = row.get("effective_from")
            end = row.get("effective_until")
            if start and moment < start:
                continue
            if end and moment > end:
                continue
            return row
        return None

    async def update_platform(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        biz = self._require_platform_admin(business)
        current = await self.platform.find_one({"key": SINGLETON_KEY})
        if current is None:
            raise NotFoundError("Platform settings not seeded")

        updates: dict[str, Any] = {}
        changes: dict[str, Any] = {}

        if "platform_name" in payload and payload["platform_name"] is not None:
            name = payload["platform_name"].strip()
            if not name:
                raise BadRequestError("Platform name is required")
            if name != current.get("platform_name"):
                changes["platform_name"] = {"from": current.get("platform_name"), "to": name}
                updates["platform_name"] = name

        if "default_currency" in payload and payload["default_currency"] is not None:
            cur = payload["default_currency"].upper()
            if cur not in ALLOWED_CURRENCIES:
                raise BadRequestError(
                    f"Default currency must be one of: {', '.join(sorted(ALLOWED_CURRENCIES))}"
                )
            if cur != current.get("default_currency"):
                changes["default_currency"] = {"from": current.get("default_currency"), "to": cur}
                updates["default_currency"] = cur

        if "commission_rate" in payload and payload["commission_rate"] is not None:
            rate = as_decimal(payload["commission_rate"])
            if rate < 0 or rate > 1:
                raise BadRequestError("Commission rate must be between 0 and 1 (for example, 0.05 for 5%)")
            rate_m = commission_rate(rate)
            if rate_m != commission_rate(current.get("commission_rate")):
                changes["commission_rate"] = {
                    "from": _money_out(current.get("commission_rate")),
                    "to": format(rate_m, "f"),
                }
                updates["commission_rate"] = to_decimal128(rate_m)

        if "commission_type" in payload and payload["commission_type"] is not None:
            ctype = payload["commission_type"].strip().lower()
            if ctype not in {CommissionType.PERCENTAGE, CommissionType.FIXED, "percentage", "fixed"}:
                raise BadRequestError("Commission type must be percentage or fixed")
            if ctype != current.get("commission_type"):
                changes["commission_type"] = {"from": current.get("commission_type"), "to": ctype}
                updates["commission_type"] = ctype

        if "commission_base" in payload and payload["commission_base"] is not None:
            base = payload["commission_base"].strip().lower()
            allowed = {CommissionBase.ORDER_TOTAL, CommissionBase.ORDER_SUBTOTAL}
            if base not in allowed:
                raise BadRequestError("Commission basis must be order total or order subtotal")
            if base != current.get("commission_base"):
                changes["commission_base"] = {"from": current.get("commission_base"), "to": base}
                updates["commission_base"] = base

        if "minimum_order_value" in payload and payload["minimum_order_value"] is not None:
            mov = money(payload["minimum_order_value"])
            if mov < 0:
                raise BadRequestError("Minimum order value cannot be negative")
            if mov != money(current.get("minimum_order_value") or 0):
                changes["minimum_order_value"] = {
                    "from": _money_out(current.get("minimum_order_value")),
                    "to": format(mov, "f"),
                }
                updates["minimum_order_value"] = to_decimal128(mov)

        if "payment_provider" in payload:
                                                             
            prov = payload["payment_provider"]
            if prov is not None:
                prov = str(prov).strip() or None
            if "secret" in str(prov or "").lower() or "key" in str(prov or "").lower():
                raise BadRequestError("Do not store provider secrets in system settings")
            if prov != current.get("payment_provider"):
                changes["payment_provider"] = {"from": current.get("payment_provider"), "to": prov}
                updates["payment_provider"] = prov

        if "payment_provider_active" in payload and payload["payment_provider_active"] is not None:
            active = bool(payload["payment_provider_active"])
            if active != bool(current.get("payment_provider_active")):
                changes["payment_provider_active"] = {
                    "from": current.get("payment_provider_active"),
                    "to": active,
                }
                updates["payment_provider_active"] = active

        if not updates:
            return self._serialize_platform(current)

        updates["updated_by"] = parse_object_id(user_id)
        updates["updated_at"] = utc_now()

        async def _work(session: MongoSession) -> dict[str, Any]:
            refreshed = await self.platform.update(
                current["_id"], updates, session=session
            )
            assert refreshed is not None
            return refreshed

        refreshed = await run_in_transaction(_work)
        await self.audit.log(
            action="UPDATE_PLATFORM_SETTING",
            resource_type="platform_settings",
            resource_id=str(current["_id"]),
            business_account_id=biz.get("_id"),
            actor_id=user_id,
            metadata={"changes": changes},
        )
        return self._serialize_platform(refreshed)

    async def update_tax(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        biz = self._require_platform_admin(business)
        active = await self.tax.find_one({"is_active": True})
        now = utc_now()

        name = (payload.get("name") or (active or {}).get("name") or "VAT").strip()
        if not name:
            raise BadRequestError("Tax name is required")

        rate_raw = payload.get("rate")
        if rate_raw is None:
            if active is None:
                raise BadRequestError("rate is required when creating tax settings")
            rate = as_decimal(active.get("rate"))
        else:
            rate = as_decimal(rate_raw)
        if rate < 0 or rate > MAX_TAX_RATE:
            raise BadRequestError("Tax rate must be between 0 and 1")

        tax_type = (payload.get("type") or (active or {}).get("type") or TaxType.VAT).upper()
        if tax_type not in {TaxType.VAT, "OTHER", "VAT"}:
            raise BadRequestError("Tax type must be VAT or OTHER")

        effective_from = payload.get("effective_from") or now
        effective_until = payload.get("effective_until")
        if effective_until and effective_until < effective_from:
            raise BadRequestError("effective_until must be >= effective_from")

        rate_changed = active is None or money(rate) != money(active.get("rate"))
        changes = {
            "name": name,
            "rate": format(money(rate), "f"),
            "type": tax_type,
        }

        async def _work(session: MongoSession) -> dict[str, Any]:
            if active and not rate_changed:
                                                        
                updates: dict[str, Any] = {
                    "name": name,
                    "type": tax_type,
                    "updated_by": parse_object_id(user_id),
                    "updated_at": now,
                }
                if payload.get("effective_from") is not None:
                    updates["effective_from"] = effective_from
                if "effective_until" in payload:
                    updates["effective_until"] = effective_until
                if payload.get("is_active") is False:
                    updates["is_active"] = False
                    updates["effective_until"] = effective_until or now
                refreshed = await self.tax.update(active["_id"], updates, session=session)
                assert refreshed is not None
                return refreshed

                                                                              
            if active:
                await self.tax.update(
                    active["_id"],
                    {
                        "is_active": False,
                        "effective_until": effective_until or now,
                        "updated_by": parse_object_id(user_id),
                        "updated_at": now,
                    },
                    session=session,
                )
            created = await self.tax.create(
                {
                    "_id": ObjectId(),
                    "name": name,
                    "rate": to_decimal128(money(rate)),
                    "type": tax_type,
                    "is_active": True if payload.get("is_active", True) else False,
                    "effective_from": effective_from,
                    "effective_until": effective_until,
                    "updated_by": parse_object_id(user_id),
                    "created_at": now,
                    "updated_at": now,
                },
                session=session,
            )
            return created

        refreshed = await run_in_transaction(_work)
        await self.audit.log(
            action="UPDATE_TAX_SETTING",
            resource_type="tax_settings",
            resource_id=str(refreshed["_id"]),
            business_account_id=biz.get("_id"),
            actor_id=user_id,
            metadata={
                "changes": changes,
                "previous_tax_id": str(active["_id"]) if active else None,
                "rate_changed": rate_changed,
            },
        )
        return self._serialize_tax(refreshed)

    async def update_business(
        self,
        *,
        user_id: str,
        business: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        biz = self._require_platform_admin(business)
        current = await self.business.find_one({"key": SINGLETON_KEY})
        if current is None:
            raise NotFoundError("Business settings not seeded")

        updates: dict[str, Any] = {}
        changes: dict[str, Any] = {}

        if "business_name" in payload and payload["business_name"] is not None:
            name = payload["business_name"].strip()
            if not name:
                raise BadRequestError("Business name is required")
            if name != current.get("business_name"):
                changes["business_name"] = {"from": current.get("business_name"), "to": name}
                updates["business_name"] = name

        if "business_email" in payload:
            email = payload["business_email"]
            if email != current.get("business_email"):
                changes["business_email"] = {"from": current.get("business_email"), "to": email}
                updates["business_email"] = email

        if "business_phone" in payload:
            phone = payload["business_phone"]
            if phone is not None:
                phone = str(phone).strip() or None
            if phone != current.get("business_phone"):
                changes["business_phone"] = {"from": current.get("business_phone"), "to": phone}
                updates["business_phone"] = phone

        if "tax_registration_number" in payload:
            trn = payload["tax_registration_number"]
            if trn is not None:
                trn = str(trn).strip() or None
            if trn != current.get("tax_registration_number"):
                changes["tax_registration_number"] = {
                    "from": current.get("tax_registration_number"),
                    "to": trn,
                }
                updates["tax_registration_number"] = trn

        if "invoice_prefix" in payload and payload["invoice_prefix"] is not None:
            prefix = payload["invoice_prefix"].strip().upper()
            if not prefix or not all(c.isalnum() or c in "-_" for c in prefix):
                raise BadRequestError(
                    "Invoice prefix must be letters or numbers (dashes and underscores allowed)"
                )
            if prefix != current.get("invoice_prefix"):
                changes["invoice_prefix"] = {
                    "from": current.get("invoice_prefix"),
                    "to": prefix,
                }
                updates["invoice_prefix"] = prefix

        if "address" in payload and payload["address"] is not None:
            addr = payload["address"]
            if isinstance(addr, dict):
                updates["address"] = addr
                changes["address"] = "updated"

        if not updates:
            return self._serialize_business(current)

        updates["updated_by"] = parse_object_id(user_id)
        updates["updated_at"] = utc_now()

        async def _work(session: MongoSession) -> dict[str, Any]:
            refreshed = await self.business.update(current["_id"], updates, session=session)
            assert refreshed is not None
            return refreshed

        refreshed = await run_in_transaction(_work)
        await self.audit.log(
            action="UPDATE_BUSINESS_SETTING",
            resource_type="business_settings",
            resource_id=str(current["_id"]),
            business_account_id=biz.get("_id"),
            actor_id=user_id,
            metadata={"changes": changes},
        )
        return self._serialize_business(refreshed)

    def _serialize_platform(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "platform_name": doc.get("platform_name"),
            "default_currency": doc.get("default_currency") or "USD",
            "commission_rate": format(commission_rate(doc.get("commission_rate")), "f")
            if doc.get("commission_rate") is not None
            else None,
            "commission_type": doc.get("commission_type"),
            "commission_base": doc.get("commission_base"),
            "minimum_order_value": _money_out(doc.get("minimum_order_value")),
            "payment_provider": doc.get("payment_provider"),
            "payment_provider_active": bool(doc.get("payment_provider_active")),
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        }

    def _serialize_tax(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "rate": _money_out(doc.get("rate")),
            "type": doc.get("type"),
            "is_active": bool(doc.get("is_active")),
            "effective_from": doc.get("effective_from").isoformat()
            if doc.get("effective_from")
            else None,
            "effective_until": doc.get("effective_until").isoformat()
            if doc.get("effective_until")
            else None,
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        }

    def _serialize_business(self, doc: dict[str, Any]) -> dict[str, Any]:
        addr = doc.get("address")
        return {
            "id": str(doc["_id"]),
            "business_name": doc.get("business_name"),
            "business_email": doc.get("business_email"),
            "business_phone": doc.get("business_phone"),
            "address": addr if isinstance(addr, dict) else None,
            "tax_registration_number": doc.get("tax_registration_number"),
            "invoice_prefix": doc.get("invoice_prefix") or "TB-INV",
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        }
