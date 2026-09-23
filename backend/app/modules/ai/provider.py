"""AIProvider abstraction — advisory extraction only, never marketplace writes."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.constants import ErrorCode
from app.core.exceptions import AppError
from app.modules.ai.requirements import ProcurementRequirements, QuantityRequirement

logger = logging.getLogger(__name__)


class AIProviderError(AppError):
    def __init__(self, message: str = "AI service unavailable") -> None:
        super().__init__(ErrorCode.INTERNAL_ERROR, message, status_code=503)


class AIProvider(ABC):
    @abstractmethod
    async def extract_procurement_requirements(
        self,
        business_description: str,
        *,
        context: str | None = None,
    ) -> ProcurementRequirements:
        raise NotImplementedError


_PRODUCT_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(beverage|drink|soft drink|soda|juice|water|bottled water)\b", re.I), "beverages", "Beverages"),
    (re.compile(r"\b(clean(?:ing)?|detergent|soap|disinfectant|household)\b", re.I), "cleaning products", "Cleaning"),
    (re.compile(r"\b(snack|chips|biscuit|candy|chocolate)\b", re.I), "snacks", "Snacks"),
    (re.compile(r"\b(dairy|milk|cheese|yogurt)\b", re.I), "dairy", "Dairy"),
    (re.compile(r"\b(fruit|vegetable|produce|fresh)\b", re.I), "fresh produce", "Produce"),
    (re.compile(r"\b(rice|grain|pasta|oil|pantry|grocery)\b", re.I), "grocery staples", "Grocery"),
    (re.compile(r"\b(meat|poultry|chicken|beef)\b", re.I), "meat", "Meat"),
    (re.compile(r"\b(electronics|cable|charger|device)\b", re.I), "electronics", "Electronics"),
    (re.compile(r"\b(build(?:ing)?|cement|steel|hardware|construction)\b", re.I), "construction materials", "Construction"),
]

_BUSINESS_TYPES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsupermarket|grocery store|mini[- ]?market\b", re.I), "supermarket"),
    (re.compile(r"\brestaurant|cafe|hotel|hospitality\b", re.I), "hospitality"),
    (re.compile(r"\bpharmacy|drugstore\b", re.I), "pharmacy"),
    (re.compile(r"\bwholesaler|distributor\b", re.I), "wholesaler"),
    (re.compile(r"\bretaile?r|shop|store\b", re.I), "retailer"),
]


class StubAIProvider(AIProvider):
    """Heuristic extractor used when no LLM key is configured.

    Only surfaces signals present in the text — does not invent suppliers or prices.
    """

    async def extract_procurement_requirements(
        self,
        business_description: str,
        *,
        context: str | None = None,
    ) -> ProcurementRequirements:
        text = business_description.strip()
        if len(text) < 8:
            raise AIProviderError(
                "We couldn't understand your description. Please add more detail about what you need."
            )

        products: list[str] = []
        categories: list[str] = []
        for pattern, product, category in _PRODUCT_HINTS:
            if pattern.search(text):
                if product not in products:
                    products.append(product)
                if category not in categories:
                    categories.append(category)

        # Optional RAG vocabulary: surface catalog product/category names that
        # overlap the buyer's wording (still no invented prices or suppliers).
        if context:
            for match in re.finditer(
                r"(?:Product|Category):\s*([^.\n]+)",
                context,
                re.I,
            ):
                label = match.group(1).strip(" .")
                if len(label) < 3:
                    continue
                label_tokens = {t for t in re.findall(r"[a-z0-9]+", label.lower()) if len(t) > 2}
                text_tokens = {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}
                if not label_tokens or not (label_tokens & text_tokens):
                    continue
                kind = match.group(0).split(":", 1)[0].strip().lower()
                if kind == "category":
                    if label not in categories:
                        categories.append(label)
                else:
                    if label not in products:
                        products.append(label)

        business_type = None
        for pattern, label in _BUSINESS_TYPES:
            if pattern.search(text):
                business_type = label
                break

        location = None
        loc_match = re.search(
            r"\b(?:in|from|based in|deliver(?:y)? to)\s+([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*(?:,?\s*Lebanon)?)",
            text,
        )
        if loc_match:
            location = loc_match.group(1).strip(" .,")
        elif re.search(r"\b(south lebanon|beirut|tyre|tripoli|saida|bekkaa?)\b", text, re.I):
            m = re.search(r"\b(south lebanon|beirut|tyre|tripoli|saida|bekkaa?)\b", text, re.I)
            location = m.group(1).title() if m else None

        frequency = None
        if re.search(r"\b(every month|monthly)\b", text, re.I):
            frequency = "monthly"
        elif re.search(r"\b(weekly|every week)\b", text, re.I):
            frequency = "weekly"
        elif re.search(r"\b(quarterly|every quarter)\b", text, re.I):
            frequency = "quarterly"

        delivery = None
        if re.search(r"\bdeliver", text, re.I):
            if location:
                delivery = f"Delivery to {location}"
            else:
                delivery = "Delivery required"

        prefs: list[str] = []
        if re.search(r"\bbulk\b", text, re.I):
            prefs.append("Bulk availability")
        if re.search(r"\blocal\b", text, re.I):
            prefs.append("Local suppliers")
        if re.search(r"\breliab|trust|verified\b", text, re.I):
            prefs.append("Reliable fulfillment")

        quantities: list[QuantityRequirement] = []
        for qty_match in re.finditer(
            r"(\d[\d,]*(?:\.\d+)?)\s*(kg|tons?|cases?|units?|cartons?|liters?|l)\s+(?:of\s+)?([a-z][a-z\s-]{2,40})",
            text,
            re.I,
        ):
            raw_qty = qty_match.group(1).replace(",", "")
            try:
                qty_val = float(raw_qty)
            except ValueError:
                continue
            quantities.append(
                QuantityRequirement(
                    product=qty_match.group(3).strip(),
                    quantity=qty_val,
                    unit=qty_match.group(2).lower(),
                )
            )

        missing: list[str] = []
        if not products:
            missing.append("product categories you need")
        if not quantities:
            missing.append("expected quantities")
        if not location:
            missing.append("business location")
        if not frequency:
            missing.append("purchase frequency")
        if "budget" not in text.lower() and "price" not in text.lower():
            missing.append("preferred budget")

        summary_bits = []
        if business_type:
            summary_bits.append(f"a {business_type}")
        if products:
            summary_bits.append("sourcing " + ", ".join(products[:4]))
        if location:
            summary_bits.append(f"in {location}")

        return ProcurementRequirements(
            business_type=business_type,
            business_description=text,
            location=location,
            product_requirements=products,
            categories=categories,
            quantities=quantities,
            purchase_frequency=frequency,
            delivery_requirements=delivery,
            supplier_preferences=prefs,
            budget_range=None,
            missing_information=missing,
        )


class OpenAICompatibleProvider(AIProvider):
    """JSON-schema style extraction via OpenAI-compatible chat completions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def extract_procurement_requirements(
        self,
        business_description: str,
        *,
        context: str | None = None,
    ) -> ProcurementRequirements:
        api_key = self._settings.ai_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise AIProviderError(
                "AI provider is not configured. Please enter your requirements manually."
            )

        model = self._settings.ai_model or "gpt-4o-mini"
        schema = ProcurementRequirements.model_json_schema()
        system = (
            "You extract procurement requirements for TradeBay, a Lebanese B2B wholesale marketplace. "
            "Return ONLY JSON matching the schema. Extract only facts supported by the buyer's text. "
            "Do not invent suppliers, products, prices, MOQs, ratings, or verification. "
            "If catalog context is provided, use it only to align product/category wording with "
            "real marketplace vocabulary — never invent listings from it. "
            "Put unknowns in missing_information."
        )
        context_block = ""
        if context and context.strip():
            context_block = f"\n\nCatalog context:\n{context.strip()}\n"
        user = (
            "Extract procurement requirements from this buyer description:\n\n"
            f"{business_description.strip()}"
            f"{context_block}\n"
            f"JSON schema:\n{json.dumps(schema)}"
        )

        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self._settings.ai_timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code == 429:
                    raise AIProviderError(
                        "AI rate limit reached. Please try again shortly or enter requirements manually."
                    )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                data = json.loads(content)
                if isinstance(data, dict) and "business_description" not in data:
                    data["business_description"] = business_description.strip()
                return ProcurementRequirements.model_validate(data)
        except AIProviderError:
            raise
        except Exception as exc:
            logger.warning("AI extraction failed: %s", exc)
            raise AIProviderError(
                "We couldn't understand your description right now. Please try again or enter your requirements manually."
            ) from exc


class FallbackAIProvider(AIProvider):
    """Try the primary LLM, then fall back to heuristics so analyze stays usable."""

    def __init__(self, primary: AIProvider, fallback: AIProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def extract_procurement_requirements(
        self,
        business_description: str,
        *,
        context: str | None = None,
    ) -> ProcurementRequirements:
        try:
            return await self._primary.extract_procurement_requirements(
                business_description, context=context
            )
        except AIProviderError as exc:
            logger.warning("Primary AI unavailable (%s); using heuristic fallback", exc.message)
            return await self._fallback.extract_procurement_requirements(
                business_description, context=context
            )


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    cfg = settings or get_settings()
    provider = (cfg.ai_provider or "stub").strip().lower()
    if provider in {"openai", "openai_compatible", "llm"}:
        return FallbackAIProvider(OpenAICompatibleProvider(cfg), StubAIProvider())
    return StubAIProvider()
