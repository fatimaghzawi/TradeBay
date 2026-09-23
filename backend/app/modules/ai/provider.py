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


# Plural-safe patterns: "beverage" and "beverages" both match.
_PRODUCT_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"\b(beverages?|drinks?|soft[\s-]?drinks?|sodas?|juices?|"
            r"bottled\s+waters?|mineral\s+waters?|waters?)\b",
            re.I,
        ),
        "beverages",
        "Beverages",
    ),
    (
        re.compile(
            r"\b(clean(?:ing|ers?)?|detergents?|soaps?|disinfectants?|"
            r"household\s+clean(?:ing|ers?)?)\b",
            re.I,
        ),
        "cleaning products",
        "Cleaning",
    ),
    (
        re.compile(r"\b(snacks?|chips?|biscuits?|cand(?:y|ies)|chocolates?)\b", re.I),
        "snacks",
        "Snacks",
    ),
    (
        re.compile(r"\b(dairy|milks?|cheeses?|yogurts?|labneh)\b", re.I),
        "dairy",
        "Dairy",
    ),
    (
        re.compile(r"\b(fruits?|vegetables?|produce|fresh\s+produce)\b", re.I),
        "fresh produce",
        "Produce",
    ),
    (
        re.compile(
            r"\b(rices?|grains?|pastas?|oils?|olive\s+oils?|pantry|"
            r"grocer(?:y|ies)|staples?|spices?|seasonings?)\b",
            re.I,
        ),
        "grocery staples",
        "Grocery",
    ),
    (
        re.compile(r"\b(meats?|poultry|chickens?|beef|lamb)\b", re.I),
        "meat",
        "Meat",
    ),
    (
        re.compile(
            r"\b(electronics?|cables?|chargers?|devices?|appliances?)\b",
            re.I,
        ),
        "electronics",
        "Electronics",
    ),
    (
        re.compile(
            r"\b(build(?:ing)?|cements?|steels?|hardwares?|construction|"
            r"building\s+materials?)\b",
            re.I,
        ),
        "construction materials",
        "Construction",
    ),
    (
        re.compile(
            r"\b(pharma(?:cy|ceuticals?)?|medicines?|drugs?|medical\s+supplies?|"
            r"packaging)\b",
            re.I,
        ),
        "pharmacy supplies",
        "Pharmacy",
    ),
    (
        re.compile(
            r"\b(kitchen|housewares?|cookware|food[\s-]?service|hospitality\s+supplies?)\b",
            re.I,
        ),
        "kitchen housewares",
        "Housewares",
    ),
    (
        re.compile(r"\b(papers?|packaging|plastics?|disposables?)\b", re.I),
        "packaging materials",
        "Packaging",
    ),
]

_BUSINESS_TYPES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsupermarket|grocery\s+store|mini[\s-]?market\b", re.I), "supermarket"),
    (re.compile(r"\brestaurant|cafe|hôtel|hotel|hospitality|catering\b", re.I), "hospitality"),
    (re.compile(r"\bpharmacy|drugstore\b", re.I), "pharmacy"),
    (re.compile(r"\bwholesaler|distributor\b", re.I), "wholesaler"),
    (re.compile(r"\bcontractor|construction\s+compan\w*\b", re.I), "contractor"),
    (re.compile(r"\bretaile?r|shop|store\b", re.I), "retailer"),
]

# Capture free-form product lists: "looking for X, Y, and Z"
_NEED_LIST = re.compile(
    r"(?:looking\s+for|need(?:ing)?|want(?:ing)?|source|sourcing|buy(?:ing)?|"
    r"suppliers?\s+(?:of|for)|restock(?:ing)?)\s+"
    r"(.+?)(?:\.|$|\b(?:every|each|monthly|weekly|who|that|with|from|in\s+[A-Z]))",
    re.I | re.S,
)

_STOP = frozenset(
    {
        "and",
        "or",
        "the",
        "a",
        "an",
        "for",
        "my",
        "our",
        "to",
        "in",
        "of",
        "with",
        "who",
        "can",
        "bulk",
        "suppliers",
        "supplier",
        "products",
        "product",
        "some",
        "good",
        "best",
        "local",
        "verified",
        "reliable",
    }
)


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

        for phrase in self._extract_need_phrases(text):
            if phrase not in products:
                products.append(phrase)

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
            r"\b(?:in|from|based in|deliver(?:y)? to)\s+"
            r"([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*(?:,?\s*Lebanon)?)",
            text,
        )
        if loc_match:
            location = loc_match.group(1).strip(" .,")
        else:
            m = re.search(
                r"\b(south lebanon|mount lebanon|beirut|tyre|tripoli|saida|sidon|bekkaa?|zahle|jounieh)\b",
                text,
                re.I,
            )
            if m:
                location = m.group(1).title()

        frequency = None
        if re.search(r"\b(every month|monthly)\b", text, re.I):
            frequency = "monthly"
        elif re.search(r"\b(weekly|every week)\b", text, re.I):
            frequency = "weekly"
        elif re.search(r"\b(quarterly|every quarter)\b", text, re.I):
            frequency = "quarterly"

        delivery = None
        if re.search(r"\bdeliver", text, re.I):
            delivery = f"Delivery to {location}" if location else "Delivery required"

        prefs: list[str] = []
        if re.search(r"\bbulk\b", text, re.I):
            prefs.append("Bulk availability")
        if re.search(r"\blocal\b", text, re.I):
            prefs.append("Local suppliers")
        if re.search(r"\breliab|trust|verified\b", text, re.I):
            prefs.append("Reliable fulfillment")

        quantities: list[QuantityRequirement] = []
        for qty_match in re.finditer(
            r"(\d[\d,]*(?:\.\d+)?)\s*(kg|tons?|cases?|units?|cartons?|liters?|l)\s+"
            r"(?:of\s+)?([a-z][a-z\s-]{2,40})",
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

        return ProcurementRequirements(
            business_type=business_type,
            business_description=text,
            location=location,
            product_requirements=products[:12],
            categories=categories[:12],
            quantities=quantities,
            purchase_frequency=frequency,
            delivery_requirements=delivery,
            supplier_preferences=prefs,
            budget_range=None,
            missing_information=missing,
        )

    @staticmethod
    def _extract_need_phrases(text: str) -> list[str]:
        """Pull concrete items from 'looking for X, Y and Z' style clauses."""
        found: list[str] = []
        for match in _NEED_LIST.finditer(text):
            chunk = match.group(1)
            # Stop at delivery / frequency / "for my …" clauses
            chunk = re.split(
                r"\b(?:every|monthly|weekly|who|that|with|from|delivered|deliver|"
                r"for\s+(?:my|our|a|the))\b",
                chunk,
                maxsplit=1,
                flags=re.I,
            )[0]
            parts = re.split(r",|/|\band\b|\bor\b", chunk, flags=re.I)
            for part in parts:
                cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", " ", part)
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
                if len(cleaned) < 3 or len(cleaned) > 48:
                    continue
                tokens = [t for t in cleaned.lower().split() if t not in _STOP]
                if not tokens:
                    continue
                # Prefer multi-word product phrases; skip vague singles
                if len(tokens) == 1 and tokens[0] in {
                    "food",
                    "help",
                    "partners",
                    "company",
                    "stuff",
                    "things",
                    "items",
                }:
                    continue
                # Skip vague partner/help phrases that aren't catalog products
                if any(
                    bad in tokens
                    for bad in ("help", "partners", "partner", "nearby", "somewhere")
                ):
                    continue
                label = cleaned.lower()
                if label not in found:
                    found.append(label)
        return found[:8]


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
            "Return ONLY JSON matching the schema. Rules:\n"
            "1) Extract only facts supported by the buyer's text — never invent suppliers, prices, MOQs, "
            "ratings, stock, or verification.\n"
            "2) product_requirements must be short searchable product phrases buyers would type "
            "(e.g. 'beverages', 'cleaning products', 'olive oil', 'cement') — include plurals as the "
            "common catalog form and split compound asks into separate items.\n"
            "3) categories should be marketplace category labels when clear "
            "(Beverages, Cleaning, Grocery, Construction, etc.).\n"
            "4) If catalog context is provided, use it only to align wording with real catalog "
            "vocabulary — never invent listings from it.\n"
            "5) Put unknowns in missing_information (location, quantities, frequency, budget).\n"
            "6) Prefer concrete product nouns over vague words like 'partners' or 'supplies'."
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
                reqs = ProcurementRequirements.model_validate(data)
                return self._normalize_requirements(reqs, business_description.strip())
        except AIProviderError:
            raise
        except Exception as exc:
            logger.warning("AI extraction failed: %s", exc)
            raise AIProviderError(
                "We couldn't understand your description right now. Please try again or enter your requirements manually."
            ) from exc

    @staticmethod
    def _normalize_requirements(
        reqs: ProcurementRequirements,
        original: str,
    ) -> ProcurementRequirements:
        """Dedupe and trim product lists so catalog search stays precise."""
        products: list[str] = []
        for item in reqs.product_requirements:
            cleaned = re.sub(r"\s+", " ", (item or "").strip())
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key not in {p.lower() for p in products}:
                products.append(cleaned)
        categories: list[str] = []
        for item in reqs.categories:
            cleaned = re.sub(r"\s+", " ", (item or "").strip())
            if len(cleaned) < 2:
                continue
            if cleaned.lower() not in {c.lower() for c in categories}:
                categories.append(cleaned)
        return reqs.model_copy(
            update={
                "business_description": reqs.business_description or original,
                "product_requirements": products[:16],
                "categories": categories[:16],
            }
        )


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
    """Always use the configured LLM provider — no heuristic stub fallback."""
    cfg = settings or get_settings()
    provider = (cfg.ai_provider or "openai").strip().lower()
    has_key = bool(cfg.ai_api_key and cfg.ai_api_key.get_secret_value().strip())

    if provider in {"heuristic", "stub", "none", "off"}:
        # Explicit offline mode for unit tests / local demos without a key.
        if provider in {"heuristic", "stub"}:
            return StubAIProvider()
        raise AIProviderError(
            "AI is disabled. Set AI_PROVIDER=openai and AI_API_KEY to use Ask the Bay."
        )

    if not has_key:
        raise AIProviderError(
            "AI_API_KEY is required. Configure OpenAI on the server to use Ask the Bay."
        )

    return OpenAICompatibleProvider(cfg)