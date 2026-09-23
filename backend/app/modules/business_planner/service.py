"""Business Planner service — discovery, market snapshot, AI draft, Decimal finance."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.modules.ai.provider import get_ai_provider
from app.modules.ai_sourcing.constants import SourcingRequestStatus
from app.modules.ai_sourcing.repository import (
    SourcingRequestItemRepository,
    SourcingRequestRepository,
)
from app.modules.business_planner.constants import (
    BUDGET_RANGES,
    STEP_ADAPTIVE,
    STEP_BUDGET,
    STEP_GOAL,
    STEP_LOCATION,
    STEP_PREFERENCES,
    BusinessPlanStatus,
    ItemSourceType,
    MilestoneStatus,
    PlanItemPriority,
    PlannerMessageRole,
    PlannerSessionStatus,
    PriceEstimateSourceType,
)
from app.modules.business_planner.exceptions import (
    PlannerGenerationError,
    PlannerValidationError,
    PlanNotFoundError,
    PlanNotOwnedError,
    SessionNotFoundError,
    SessionNotOwnedError,
)
from app.modules.business_planner.finance import compute_plan_finance, money
from app.modules.business_planner.market import build_market_snapshot
from app.modules.business_planner.planner_ai import (
    assistant_stub_reply,
    generate_adaptive_questions,
    generate_plan_draft,
    resolve_budget_midpoint,
)
from app.modules.business_planner.repository import (
    BusinessPlanItemRepository,
    BusinessPlanMessageRepository,
    BusinessPlanRepository,
    BusinessPlanSessionRepository,
    PriceEstimateRepository,
)
from app.modules.business_planner.schemas import AIPlanDraft, PlannerPreferences
from app.shared.types.money import to_decimal128
from app.shared.utils.objectid import parse_object_id


def _now() -> datetime:
    return datetime.now(UTC)


def _oid_str(value: Any) -> str:
    return str(value)


def _money_out(value: Any) -> str | None:
    if value is None:
        return None
    from bson import Decimal128

    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    return str(value)


class BusinessPlannerService:
    def __init__(
        self,
        *,
        plans: BusinessPlanRepository | None = None,
        items: BusinessPlanItemRepository | None = None,
        estimates: PriceEstimateRepository | None = None,
        sessions: BusinessPlanSessionRepository | None = None,
        messages: BusinessPlanMessageRepository | None = None,
        sourcing_requests: SourcingRequestRepository | None = None,
        sourcing_items: SourcingRequestItemRepository | None = None,
        ai=None,
    ) -> None:
        self.plans = plans or BusinessPlanRepository()
        self.items = items or BusinessPlanItemRepository()
        self.estimates = estimates or PriceEstimateRepository()
        self.sessions = sessions or BusinessPlanSessionRepository()
        self.messages = messages or BusinessPlanMessageRepository()
        self.sourcing_requests = sourcing_requests or SourcingRequestRepository()
        self.sourcing_items = sourcing_items or SourcingRequestItemRepository()
        self.ai = ai or get_ai_provider()

    async def _owned_session(self, session_id: str, *, user_id: str) -> dict[str, Any]:
        doc = await self.sessions.get_by_id(session_id)
        if doc is None:
            raise SessionNotFoundError()
        if str(doc.get("user_id") or "") != user_id:
            raise SessionNotOwnedError()
        return doc

    async def _owned_plan(self, plan_id: str, *, user_id: str) -> dict[str, Any]:
        doc = await self.plans.get_by_id(plan_id)
        if doc is None:
            raise PlanNotFoundError()
        if str(doc.get("user_id") or "") != user_id:
            raise PlanNotOwnedError()
        return doc

    def _merge_preferences(self, existing: dict[str, Any], step: str, answers: dict[str, Any]) -> dict[str, Any]:
        prefs = dict(existing or {})
        if step == STEP_GOAL:
            goal = answers.get("business_goal")
            unsure = bool(answers.get("unsure_goal") or goal in {"not_sure", "I'm not sure yet"})
            prefs["business_goal"] = None if unsure else (str(goal) if goal else prefs.get("business_goal"))
            prefs["unsure_goal"] = unsure
            if answers.get("category_hints"):
                prefs["category_hints"] = list(answers["category_hints"])
        elif step == STEP_LOCATION:
            prefs["location"] = answers.get("location") or prefs.get("location")
        elif step == STEP_BUDGET:
            rng = answers.get("budget_range")
            prefs["budget_range"] = rng
            lo, hi = BUDGET_RANGES.get(str(rng or ""), (None, None))
            prefs["budget_min"] = answers.get("budget_min") or lo
            prefs["budget_max"] = answers.get("budget_max") or hi
            prefs["inventory_budget"] = answers.get("inventory_budget")
            prefs["operating_cash"] = answers.get("operating_cash")
        elif step == STEP_PREFERENCES:
            for key in (
                "business_model",
                "experience",
                "time_commitment",
                "risk_preference",
                "desired_monthly_income",
                "desired_margin",
                "product_preferences",
                "customer_type",
                "category_hints",
            ):
                if key in answers:
                    prefs[key] = answers[key]
        elif step == STEP_ADAPTIVE:
            adaptive = dict(prefs.get("adaptive") or {})
            adaptive.update(answers)
            prefs["adaptive"] = adaptive
            # Promote a few adaptive keys
            if "margin_confirm" in answers and not prefs.get("desired_margin"):
                prefs["desired_margin"] = answers["margin_confirm"]
            if "channel_pref" in answers and not prefs.get("business_model"):
                prefs["business_model"] = [answers["channel_pref"]]
        else:
            # Generic merge for forward-compat
            prefs.update({k: v for k, v in answers.items() if v is not None})
        return prefs

    async def create_session(self, *, user_id: str) -> dict[str, Any]:
        now = _now()
        doc = await self.sessions.create(
            {
                "user_id": parse_object_id(user_id),
                "status": PlannerSessionStatus.COLLECTING,
                "current_step": STEP_GOAL,
                "answers": {},
                "preferences": {},
                "adaptive_questions": [],
                "adaptive_answers": {},
                "plan_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return self._serialize_session(doc)

    async def get_session(self, *, user_id: str, session_id: str) -> dict[str, Any]:
        doc = await self._owned_session(session_id, user_id=user_id)
        return self._serialize_session(doc)

    async def submit_answers(
        self,
        *,
        user_id: str,
        session_id: str,
        step: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        doc = await self._owned_session(session_id, user_id=user_id)
        all_answers = dict(doc.get("answers") or {})
        all_answers[step] = answers
        preferences = self._merge_preferences(doc.get("preferences") or {}, step, answers)
        next_step = {
            STEP_GOAL: STEP_LOCATION,
            STEP_LOCATION: STEP_BUDGET,
            STEP_BUDGET: STEP_PREFERENCES,
            STEP_PREFERENCES: STEP_ADAPTIVE,
            STEP_ADAPTIVE: STEP_ADAPTIVE,
        }.get(step, step)
        now = _now()
        updated = await self.sessions.update(
            doc["_id"],
            {
                "answers": all_answers,
                "preferences": preferences,
                "current_step": next_step,
                "updated_at": now,
            },
        )
        assert updated is not None
        return self._serialize_session(updated)

    async def next_questions(self, *, user_id: str, session_id: str) -> dict[str, Any]:
        doc = await self._owned_session(session_id, user_id=user_id)
        prefs = doc.get("preferences") or {}
        questions = await generate_adaptive_questions(self.ai, prefs)
        now = _now()
        updated = await self.sessions.update(
            doc["_id"],
            {
                "adaptive_questions": [q.model_dump() for q in questions],
                "current_step": STEP_ADAPTIVE,
                "status": PlannerSessionStatus.READY if not questions else PlannerSessionStatus.COLLECTING,
                "updated_at": now,
            },
        )
        assert updated is not None
        return {
            "session": self._serialize_session(updated),
            "questions": [q.model_dump() for q in questions],
        }

    async def generate_from_session(self, *, user_id: str, session_id: str) -> dict[str, Any]:
        doc = await self._owned_session(session_id, user_id=user_id)
        prefs = doc.get("preferences") or {}
        if not prefs.get("location") and not (doc.get("answers") or {}).get(STEP_LOCATION):
            raise PlannerValidationError("Location is required before generating a plan.")
        await self.sessions.update(
            doc["_id"],
            {"status": PlannerSessionStatus.GENERATING, "updated_at": _now()},
        )
        try:
            plan = await self._generate_plan(user_id=user_id, preferences=prefs, session_id=session_id)
        except Exception as exc:
            await self.sessions.update(
                doc["_id"],
                {"status": PlannerSessionStatus.READY, "updated_at": _now()},
            )
            if isinstance(exc, (PlannerValidationError, PlannerGenerationError)):
                raise
            raise PlannerGenerationError() from exc

        await self.sessions.update(
            doc["_id"],
            {
                "status": PlannerSessionStatus.COMPLETED,
                "plan_id": parse_object_id(plan["id"]),
                "updated_at": _now(),
            },
        )
        return plan

    async def _generate_plan(
        self,
        *,
        user_id: str,
        preferences: dict[str, Any],
        session_id: str | None = None,
        parent_plan_id: str | None = None,
        version: int = 1,
        business_account_id: str | None = None,
    ) -> dict[str, Any]:
        market = await build_market_snapshot(preferences=preferences)
        try:
            draft = await generate_plan_draft(self.ai, preferences=preferences, market=market)
            draft = AIPlanDraft.model_validate(draft.model_dump())
        except Exception as exc:
            raise PlannerGenerationError("AI returned an invalid plan. Please try again.") from exc

        # Enrich purchase prices from market candidates when missing
        cand_by_id = {c["product_id"]: c for c in (market.get("candidates") or []) if c.get("product_id")}
        line_inputs: list[dict[str, Any]] = []
        enriched_items: list[dict[str, Any]] = []
        for item in draft.product_strategy:
            cand = cand_by_id.get(item.product_id) if item.product_id else None
            unit_cost_str = item.estimated_purchase_price
            source = item.source_type
            if cand and cand.get("unit_price"):
                unit_cost_str = cand["unit_price"]
                source = ItemSourceType.MARKETPLACE
            if not unit_cost_str:
                continue
            unit_cost = money(unit_cost_str)
            sell = money(item.target_selling_price)
            qty = Decimal(item.quantity)
            # Respect MOQ floor from marketplace
            moq = item.suggested_moq or (cand.get("moq") if cand else None)
            if moq and qty < Decimal(int(moq)):
                qty = Decimal(int(moq))
            line_inputs.append(
                {"quantity": qty, "unit_cost": unit_cost, "selling_price": sell}
            )
            enriched_items.append(
                {
                    "draft": item,
                    "cand": cand,
                    "unit_cost": unit_cost,
                    "sell": sell,
                    "qty": qty,
                    "source": source,
                    "moq": moq,
                }
            )

        available = resolve_budget_midpoint(preferences)
        inv_cap = None
        if preferences.get("inventory_budget"):
            try:
                inv_cap = money(preferences["inventory_budget"])
            except Exception:
                inv_cap = None
        target_income = None
        if preferences.get("desired_monthly_income"):
            try:
                target_income = money(str(preferences["desired_monthly_income"]).replace(",", "").strip())
            except Exception:
                target_income = None

        finance = compute_plan_finance(
            line_inputs=line_inputs,
            available_budget=available,
            inventory_budget_cap=inv_cap,
            target_monthly_income=target_income,
            auto_scale=True,
        )

        # Align quantities with scaled finance lines
        for i, ln in enumerate(finance.lines):
            if i < len(enriched_items):
                enriched_items[i]["qty"] = ln.quantity
                enriched_items[i]["line"] = ln

        now = _now()
        concept = draft.business_concept.model_dump()
        milestones = []
        for m in draft.launch_plan:
            row = m.model_dump()
            row["status"] = MilestoneStatus.PENDING
            milestones.append(row)

        plan_doc = await self.plans.create(
            {
                "user_id": parse_object_id(user_id),
                "business_account_id": parse_object_id(business_account_id)
                if business_account_id
                else None,
                "business_type": preferences.get("business_goal") or concept.get("concept") or "startup",
                "business_name": concept.get("name_suggestion"),
                "title": concept.get("name_suggestion"),
                "description": concept.get("concept"),
                "location": preferences.get("location") or concept.get("target_location"),
                "currency": "USD",
                "budget": to_decimal128(available),
                "status": BusinessPlanStatus.GENERATED,
                "ai_prompt": None,
                "estimated_total_cost": to_decimal128(finance.total_inventory_cost),
                "sourcing_request_id": None,
                "preferences": preferences,
                "concept": concept,
                "budget_allocation": finance.budget_allocation,
                "financial_projection": finance.financial_projection,
                "market_snapshot": {
                    **{k: v for k, v in market.items() if k != "candidates"},
                    "candidate_count": len(market.get("candidates") or []),
                },
                "risks": [r.model_dump() for r in draft.risks],
                "milestones": milestones,
                "assumptions": [a.model_dump() for a in draft.assumptions],
                "budget_adjustments": finance.adjustments,
                "version": version,
                "parent_plan_id": parse_object_id(parent_plan_id) if parent_plan_id else None,
                "session_id": parse_object_id(session_id) if session_id else None,
                "progress": {
                    "milestones_total": len(milestones),
                    "milestones_complete": 0,
                    "next_action": "Review products and compare suppliers",
                },
                "created_at": now,
                "updated_at": now,
            }
        )

        for row in enriched_items:
            if "line" not in row:
                continue
            item = row["draft"]
            cand = row["cand"]
            ln = row["line"]
            item_doc = await self.items.create(
                {
                    "business_plan_id": plan_doc["_id"],
                    "category_id": parse_object_id(item.category_id)
                    if item.category_id
                    else (
                        parse_object_id(cand["category_id"])
                        if cand and cand.get("category_id")
                        else None
                    ),
                    "product_id": parse_object_id(item.product_id) if item.product_id else None,
                    "supplier_business_id": parse_object_id(cand["supplier_business_id"])
                    if cand and cand.get("supplier_business_id")
                    else None,
                    "item_name": item.item_name,
                    "description": item.rationale,
                    "quantity": to_decimal128(ln.quantity),
                    "unit": item.unit,
                    "priority": item.priority
                    if item.priority in {p.value for p in PlanItemPriority}
                    else PlanItemPriority.RECOMMENDED,
                    "estimated_unit_price": to_decimal128(ln.unit_cost),
                    "estimated_total_price": to_decimal128(ln.inventory_cost),
                    "target_selling_price": to_decimal128(ln.selling_price),
                    "estimated_margin": to_decimal128(ln.margin_pct),
                    "suggested_moq": row.get("moq"),
                    "reason": item.rationale,
                    "source_type": row["source"],
                    "supplier_name": cand.get("supplier_name") if cand else None,
                    "category_name": cand.get("category_name") if cand else None,
                    "created_at": now,
                }
            )
            await self.estimates.create(
                {
                    "business_plan_item_id": item_doc["_id"],
                    "source_type": (
                        PriceEstimateSourceType.MARKETPLACE
                        if row["source"] == ItemSourceType.MARKETPLACE
                        else PriceEstimateSourceType.AI_ESTIMATE
                    ),
                    "sample_count": 1 if row["source"] == ItemSourceType.MARKETPLACE else 0,
                    "min_price": to_decimal128(ln.unit_cost),
                    "average_price": to_decimal128(ln.unit_cost),
                    "max_price": to_decimal128(ln.unit_cost),
                    "currency": "USD",
                    "calculated_at": now,
                }
            )

        return await self.get_plan(user_id=user_id, plan_id=_oid_str(plan_doc["_id"]))

    async def list_plans(self, *, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        skip = (page - 1) * page_size
        rows = await self.plans.list_for_user(user_id, skip=skip, limit=page_size)
        total = await self.plans.count_for_user(user_id)
        return [self._serialize_plan_summary(r) for r in rows], total

    async def get_plan(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        items = await self.items.list_for_plan(plan_id)
        detail = self._serialize_plan_detail(plan, items)
        return await self._enrich_plan_media(detail)

    async def patch_plan(
        self,
        *,
        user_id: str,
        plan_id: str,
        title: str | None = None,
        milestone_updates: list[dict[str, Any]] | None = None,
        preferences: PlannerPreferences | None = None,
    ) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        updates: dict[str, Any] = {"updated_at": _now()}
        if title is not None:
            updates["title"] = title
            updates["business_name"] = title
        if preferences is not None:
            merged = dict(plan.get("preferences") or {})
            merged.update({k: v for k, v in preferences.model_dump().items() if v is not None})
            updates["preferences"] = merged
        if milestone_updates:
            milestones = list(plan.get("milestones") or [])
            by_order = {int(m.get("order", i)): m for i, m in enumerate(milestones)}
            for upd in milestone_updates:
                order = int(upd.get("order", -1))
                if order in by_order and upd.get("status"):
                    by_order[order]["status"] = upd["status"]
            milestones = [by_order[k] for k in sorted(by_order.keys())]
            updates["milestones"] = milestones
            complete = sum(1 for m in milestones if m.get("status") == MilestoneStatus.COMPLETE)
            updates["progress"] = {
                **(plan.get("progress") or {}),
                "milestones_total": len(milestones),
                "milestones_complete": complete,
                "next_action": self._next_action(milestones),
            }
        updated = await self.plans.update(plan["_id"], updates)
        assert updated is not None
        items = await self.items.list_for_plan(plan_id)
        detail = self._serialize_plan_detail(updated, items)
        return await self._enrich_plan_media(detail)

    def _next_action(self, milestones: list[dict[str, Any]]) -> str:
        for m in sorted(milestones, key=lambda x: int(x.get("order") or 0)):
            if m.get("status") != MilestoneStatus.COMPLETE:
                return f"Continue: {m.get('title') or m.get('phase')}"
        return "Plan milestones complete — export your plan PDF"

    async def regenerate(
        self,
        *,
        user_id: str,
        plan_id: str,
        preferences: PlannerPreferences | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        prefs = dict(plan.get("preferences") or {})
        if preferences is not None:
            prefs.update({k: v for k, v in preferences.model_dump().items() if v is not None})
        if reason:
            prefs["regenerate_reason"] = reason
        version = int(plan.get("version") or 1) + 1
        biz_id = str(plan["business_account_id"]) if plan.get("business_account_id") else None
        return await self._generate_plan(
            user_id=user_id,
            preferences=prefs,
            session_id=str(plan["session_id"]) if plan.get("session_id") else None,
            parent_plan_id=plan_id,
            version=version,
            business_account_id=biz_id,
        )

    async def assistant(
        self,
        *,
        user_id: str,
        plan_id: str,
        message: str,
    ) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        now = _now()
        await self.messages.create(
            {
                "business_plan_id": plan["_id"],
                "user_id": parse_object_id(user_id),
                "role": PlannerMessageRole.USER,
                "content": message,
                "plan_mutations": None,
                "created_at": now,
            }
        )
        reply, mutations = assistant_stub_reply(message=message, plan=plan)
        await self.messages.create(
            {
                "business_plan_id": plan["_id"],
                "user_id": parse_object_id(user_id),
                "role": PlannerMessageRole.ASSISTANT,
                "content": reply,
                "plan_mutations": mutations,
                "created_at": _now(),
            }
        )
        # Soft-apply preference patches without regenerating automatically
        if mutations and mutations.get("preferences_patch"):
            prefs = dict(plan.get("preferences") or {})
            prefs.update(mutations["preferences_patch"])
            await self.plans.update(plan["_id"], {"preferences": prefs, "updated_at": _now()})

        history = await self.messages.list_for_plan(plan_id, limit=40)
        return {
            "reply": reply,
            "mutations": mutations,
            "messages": [
                {
                    "id": _oid_str(m["_id"]),
                    "role": m.get("role"),
                    "content": m.get("content"),
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
                for m in history
            ],
        }

    async def create_sourcing_draft(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        items = await self.items.list_for_plan(plan_id)
        now = _now()
        product_names = [str(i.get("item_name")) for i in items]
        requirements = {
            "business_type": plan.get("business_type"),
            "business_description": plan.get("description") or plan.get("title") or "Business plan sourcing",
            "location": plan.get("location"),
            "product_requirements": product_names,
            "categories": list(
                {str(i.get("category_name")) for i in items if i.get("category_name")}
            ),
            "quantities": [
                {
                    "product": i.get("item_name"),
                    "quantity": _money_out(i.get("quantity")),
                    "unit": i.get("unit") or "unit",
                }
                for i in items
            ],
            "purchase_frequency": None,
            "delivery_requirements": f"Delivery to {plan.get('location')}" if plan.get("location") else None,
            "supplier_preferences": ["Verified suppliers"],
            "budget_range": _money_out(plan.get("budget")),
            "missing_information": [],
        }
        # Buyer business optional — store with user as buyer reference; business_id may be null
        raw_biz = plan.get("business_account_id")
        business_id = parse_object_id(str(raw_biz)) if raw_biz else None
        req = await self.sourcing_requests.create(
            {
                "buyer_user_id": parse_object_id(user_id),
                "buyer_business_id": business_id,
                "original_prompt": f"Business plan: {plan.get('title') or plan.get('business_name')}",
                "destination": plan.get("location"),
                "required_date": None,
                "status": SourcingRequestStatus.DRAFT,
                "rfq_id": None,
                "business_plan_id": plan["_id"],
                "profile_id": None,
                "requirements": requirements,
                "ai_summary": f"Draft from business plan {plan.get('title')}",
                "created_at": now,
                "updated_at": now,
            }
        )
        created_items = []
        for i in items:
            row = await self.sourcing_items.create(
                {
                    "sourcing_request_id": req["_id"],
                    "requested_name": i.get("item_name"),
                    "quantity": i.get("quantity"),
                    "unit": i.get("unit") or "unit",
                    "destination": plan.get("location"),
                    "product_id": i.get("product_id"),
                    "created_at": now,
                }
            )
            created_items.append(
                {
                    "id": _oid_str(row["_id"]),
                    "requested_name": row.get("requested_name"),
                    "quantity": _money_out(row.get("quantity")),
                    "unit": row.get("unit"),
                    "product_id": _oid_str(row["product_id"]) if row.get("product_id") else None,
                }
            )
        await self.plans.update(
            plan["_id"],
            {
                "sourcing_request_id": req["_id"],
                "status": BusinessPlanStatus.CONVERTED_TO_SOURCING,
                "updated_at": now,
            },
        )
        return {
            "sourcing_request_id": _oid_str(req["_id"]),
            "status": SourcingRequestStatus.DRAFT,
            "items": created_items,
            "message": "Sourcing draft created from your business plan. Review before requesting quotations.",
        }

    async def rfq_preview(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        plan = await self._owned_plan(plan_id, user_id=user_id)
        items = await self.items.list_for_plan(plan_id)
        lines = [
            {
                "product_name": i.get("item_name"),
                "product_id": _oid_str(i["product_id"]) if i.get("product_id") else None,
                "quantity": _money_out(i.get("quantity")),
                "unit": i.get("unit") or "unit",
                "target_unit_price": _money_out(i.get("estimated_unit_price")),
                "supplier_business_id": _oid_str(i["supplier_business_id"])
                if i.get("supplier_business_id")
                else None,
            }
            for i in items
        ]
        return {
            "publishable": True,
            "message": (
                "RFQ draft prepared from your business plan. "
                "Use convert-to-rfq to create a real draft RFQ in Procurement."
            ),
            "rfq_draft": {
                "title": f"RFQ — {plan.get('title') or plan.get('business_name') or 'Business plan'}",
                "delivery_location": plan.get("location"),
                "target_budget": _money_out(plan.get("budget")),
                "desired_timeline": "2-4 weeks",
                "lines": lines,
                "notes": "Generated from TradeBay Business Planner.",
                "supplier_business_ids": sorted(
                    {
                        _oid_str(i["supplier_business_id"])
                        for i in items
                        if i.get("supplier_business_id")
                    }
                ),
            },
        }

    async def convert_to_rfq(self, *, user_id: str, plan_id: str, business: dict[str, Any] | None) -> dict[str, Any]:
        """Create a real draft RFQ from the plan (does not publish)."""
        from app.modules.procurement.service import ProcurementService

        preview = await self.rfq_preview(user_id=user_id, plan_id=plan_id)
        draft = preview["rfq_draft"]
        location = draft.get("delivery_location") or ""
        city = location.split(",")[0].strip() if location else "Beirut"
        items = []
        for line in draft.get("lines") or []:
            if not line.get("product_name"):
                continue
            items.append(
                {
                    "product_id": line.get("product_id"),
                    "product_name": line["product_name"],
                    "quantity": line.get("quantity") or "1",
                    "unit": line.get("unit") or "unit",
                    "target_unit_price": line.get("target_unit_price"),
                }
            )
        if not items:
            from app.core.exceptions import BadRequestError

            raise BadRequestError("Plan has no items to convert into an RFQ")
        rfq = await ProcurementService().create_rfq(
            user_id=user_id,
            business=business,
            payload={
                "title": draft["title"],
                "description": draft.get("notes"),
                "destination": {"city": city, "country": "Lebanon"},
                "currency": "USD",
                "notes": draft.get("notes"),
                "visibility": "invited",
                "business_plan_id": plan_id,
                "items": items,
            },
        )
        supplier_ids = draft.get("supplier_business_ids") or []
        return {
            "rfq": rfq,
            "suggested_supplier_ids": supplier_ids,
            "next_url_hint": f"/procurement/rfqs/{rfq['id']}",
            "message": "Draft RFQ created. Review, publish, then invite suppliers.",
        }

    def _serialize_session(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _oid_str(doc["_id"]),
            "status": doc.get("status"),
            "current_step": doc.get("current_step"),
            "answers": doc.get("answers") or {},
            "preferences": doc.get("preferences") or {},
            "adaptive_questions": doc.get("adaptive_questions") or [],
            "plan_id": _oid_str(doc["plan_id"]) if doc.get("plan_id") else None,
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
            "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
        }

    def _serialize_plan_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        fp = doc.get("financial_projection") or {}
        return {
            "id": _oid_str(doc["_id"]),
            "title": doc.get("title") or doc.get("business_name"),
            "status": doc.get("status"),
            "location": doc.get("location"),
            "version": doc.get("version") or 1,
            "budget": _money_out(doc.get("budget")),
            "estimated_monthly_revenue": fp.get("expected_monthly_sales"),
            "gross_margin_pct": fp.get("gross_margin_pct"),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
            "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
        }

    def _serialize_plan_detail(self, doc: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        summary = self._serialize_plan_summary(doc)
        return {
            **summary,
            "business_type": doc.get("business_type"),
            "description": doc.get("description"),
            "currency": doc.get("currency") or "USD",
            "preferences": doc.get("preferences") or {},
            "concept": doc.get("concept") or {},
            "budget_allocation": doc.get("budget_allocation") or {},
            "financial_projection": doc.get("financial_projection") or {},
            "market_snapshot": doc.get("market_snapshot") or {},
            "risks": doc.get("risks") or [],
            "milestones": doc.get("milestones") or [],
            "assumptions": doc.get("assumptions") or [],
            "budget_adjustments": doc.get("budget_adjustments") or [],
            "progress": doc.get("progress") or {},
            "parent_plan_id": _oid_str(doc["parent_plan_id"]) if doc.get("parent_plan_id") else None,
            "sourcing_request_id": _oid_str(doc["sourcing_request_id"])
            if doc.get("sourcing_request_id")
            else None,
            "items": [
                {
                    "id": _oid_str(i["_id"]),
                    "item_name": i.get("item_name"),
                    "description": i.get("description"),
                    "product_id": _oid_str(i["product_id"]) if i.get("product_id") else None,
                    "category_id": _oid_str(i["category_id"]) if i.get("category_id") else None,
                    "category_name": i.get("category_name"),
                    "supplier_business_id": _oid_str(i["supplier_business_id"])
                    if i.get("supplier_business_id")
                    else None,
                    "supplier_name": i.get("supplier_name"),
                    "quantity": _money_out(i.get("quantity")),
                    "unit": i.get("unit"),
                    "priority": i.get("priority"),
                    "estimated_unit_price": _money_out(i.get("estimated_unit_price")),
                    "estimated_total_price": _money_out(i.get("estimated_total_price")),
                    "target_selling_price": _money_out(i.get("target_selling_price")),
                    "estimated_margin": _money_out(i.get("estimated_margin")),
                    "suggested_moq": i.get("suggested_moq"),
                    "reason": i.get("reason"),
                    "source_type": i.get("source_type"),
                    "image_url": None,
                }
                for i in items
            ],
            "suppliers": self._unique_suppliers(items),
            "next_actions": self._next_actions(doc, items),
        }

    async def _enrich_plan_media(self, detail: dict[str, Any]) -> dict[str, Any]:
        """Attach catalog product images and supplier logos for creative listings."""
        from bson import ObjectId

        from app.modules.catalog.repository import ProductImageRepository
        from app.modules.identity.repository import BusinessRepository
        from app.shared.utils.objectid import parse_object_id

        items = detail.get("items") or []
        product_ids: list[ObjectId] = []
        for row in items:
            pid = row.get("product_id")
            if pid:
                try:
                    product_ids.append(parse_object_id(str(pid)))
                except Exception:
                    continue

        image_by_product: dict[str, str] = {}
        if product_ids:
            images = await ProductImageRepository().find_many(
                {
                    "product_id": {"$in": product_ids},
                    "deleted_at": None,
                },
                limit=max(len(product_ids) * 4, 20),
                sort=[("is_primary", -1), ("display_order", 1)],
            )
            for img in images:
                key = str(img.get("product_id"))
                if key in image_by_product:
                    continue
                url = img.get("url")
                if url:
                    image_by_product[key] = str(url)

        for row in items:
            pid = row.get("product_id")
            if pid and str(pid) in image_by_product:
                row["image_url"] = image_by_product[str(pid)]

        suppliers = detail.get("suppliers") or []
        supplier_ids: list[ObjectId] = []
        for s in suppliers:
            sid = s.get("supplier_business_id")
            if sid:
                try:
                    supplier_ids.append(parse_object_id(str(sid)))
                except Exception:
                    continue

        if supplier_ids:
            businesses = await BusinessRepository().find_many(
                {"_id": {"$in": supplier_ids}},
                limit=max(len(supplier_ids), 1),
            )
            logo_by_id = {
                str(b["_id"]): b.get("logo_url") for b in businesses if b.get("logo_url")
            }
            for s in suppliers:
                sid = str(s.get("supplier_business_id") or "")
                if sid in logo_by_id:
                    s["logo_url"] = logo_by_id[sid]
                else:
                    s["logo_url"] = None

        return detail

    def _unique_suppliers(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for i in items:
            sid = i.get("supplier_business_id")
            if not sid:
                continue
            key = str(sid)
            if key not in seen:
                seen[key] = {
                    "supplier_business_id": key,
                    "supplier_name": i.get("supplier_name"),
                    "product_count": 0,
                    "verified": True,
                    "logo_url": None,
                }
            seen[key]["product_count"] += 1
        return list(seen.values())

    def _next_actions(self, doc: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, str]]:
        actions = [
            {"key": "products", "label": "Review products"},
            {"key": "suppliers", "label": "Compare suppliers"},
            {"key": "launch", "label": "Follow launch roadmap"},
        ]
        if doc.get("budget_adjustments"):
            actions.insert(0, {"key": "budget", "label": "Review budget"})
        if not items:
            actions = [{"key": "products", "label": "Review products"}]
        return actions
