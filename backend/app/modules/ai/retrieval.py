
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from bson import ObjectId
from pymongo import UpdateOne

from app.core.config import Settings, get_settings
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.ai.observability import log_ai_event
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.catalog.constants import ProductStatus

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_PRODUCT_PROJECTION = {
    "name": 1,
    "description": 1,
    "sku": 1,
    "status": 1,
    "moq": 1,
    "unit": 1,
    "origin": 1,
    "category_id": 1,
    "business_account_id": 1,
    "image_url": 1,
    "updated_at": 1,
}

@dataclass
class CatalogCandidate:
    product: dict[str, Any]
    supplier: dict[str, Any]
    inventory: dict[str, Any] | None
    prices: list[dict[str, Any]]
    category_name: str | None
    verified: bool
    lexical_score: float | None = None
    semantic_score: float | None = None
    sources: set[str] = field(default_factory=set)

    @property
    def product_id(self) -> str:
        return str(self.product.get("_id") or "")

class CatalogRetriever(Protocol):
    async def retrieve(
        self,
        requirements: ProcurementRequirements,
        *,
        limit: int,
    ) -> list[CatalogCandidate]:
        ...

def normalize_query_terms(requirements: ProcurementRequirements) -> list[str]:
    raw: list[str] = [
        *requirements.product_requirements,
        *requirements.categories,
        *[qty.product for qty in requirements.quantities if qty.product],
    ]
    if requirements.business_type:
        raw.append(requirements.business_type)
    seen: set[str] = set()
    terms: list[str] = []
    for item in raw:
        cleaned = re.sub(r"\s+", " ", item).strip()
        key = cleaned.lower()
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        terms.append(cleaned)
    return terms[:24]

def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 2]

def content_hash(product: dict[str, Any], category_name: str | None) -> str:
    blob = "|".join(
        [
            str(product.get("name") or ""),
            category_name or "",
            str(product.get("description") or "")[:400],
            str(product.get("unit") or ""),
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

_category_cache: tuple[float, dict[str, dict[str, Any]]] | None = None

async def load_active_categories(ttl_seconds: int) -> dict[str, dict[str, Any]]:
    global _category_cache
    now = time.monotonic()
    if ttl_seconds > 0 and _category_cache is not None:
        cached_at, cached = _category_cache
        if now - cached_at < ttl_seconds:
            return cached
    col = mongo_manager.collection(CollectionName.CATEGORIES)
    rows = await col.find({"is_active": True}, {"name": 1, "description": 1}).to_list(length=300)
    categories = {str(row["_id"]): row for row in rows}
    _category_cache = (now, categories)
    return categories

def reset_category_cache() -> None:
    global _category_cache
    _category_cache = None

def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)

class MongoHybridRetriever:

    def __init__(self, settings: Settings | None = None, *, embedder: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._embedder = embedder

    async def retrieve(
        self,
        requirements: ProcurementRequirements,
        *,
        limit: int,
    ) -> list[CatalogCandidate]:
        cap = max(1, min(limit, self._settings.ai_max_candidates))
        terms = normalize_query_terms(requirements)
        categories = await self._categories()
        category_ids = self._matching_category_ids(terms, categories)

        lexical = await self._lexical(terms, limit=cap)
        structured = await self._structured(category_ids, limit=cap)
        ordered_ids = _union_ids(lexical, structured)
        semantic_scores: dict[str, float] = {}
        semantic_ids = await self._semantic(
            requirements,
            category_ids=category_ids,
            lexical_ids=list(lexical),
            limit=cap,
        )
        for pid, score in semantic_ids:
            semantic_scores[pid] = score
            if pid not in ordered_ids:
                ordered_ids.append(pid)

        ordered_ids = ordered_ids[:cap]
        if not ordered_ids:
            log_ai_event(logger, "retrieval_empty", feature="catalog", candidate_count=0)
            return []

        products = await self._products(ordered_ids)
        hydrated = await self._hydrate(products, categories, lexical, semantic_scores)
        log_ai_event(
            logger,
            "retrieval",
            feature="catalog",
            lexical_count=len(lexical),
            structured_count=len(structured),
            semantic_count=len(semantic_scores),
            candidate_count=len(hydrated),
        )
        return hydrated

    async def _categories(self) -> dict[str, dict[str, Any]]:
        return await load_active_categories(self._settings.ai_category_cache_seconds)

    def _matching_category_ids(
        self,
        terms: list[str],
        categories: dict[str, dict[str, Any]],
    ) -> list[ObjectId]:
        ids: list[ObjectId] = []
        needles = [term.lower() for term in terms]
        for key, cat in categories.items():
            name = str(cat.get("name") or "").lower()
            if not name:
                continue
            if any(needle in name or name in needle for needle in needles):
                try:
                    ids.append(ObjectId(key))
                except Exception:
                    continue
        return ids

    async def _lexical(self, terms: list[str], *, limit: int) -> dict[str, float]:
        if not terms:
            return {}
        col = mongo_manager.collection(CollectionName.PRODUCTS)
        search = " ".join(_tokens(" ".join(terms)))[:240]
        scores: dict[str, float] = {}
        if search:
            try:
                cursor = col.find(
                    {"status": ProductStatus.ACTIVE, "$text": {"$search": search}},
                    {**_PRODUCT_PROJECTION, "score": {"$meta": "textScore"}},
                ).sort([("score", {"$meta": "textScore"})]).limit(limit)
                rows = await cursor.to_list(length=limit)
                for row in rows:
                    scores[str(row["_id"])] = float(row.get("score") or 0.0)
            except Exception as exc:
                logger.warning("Text search unavailable, using bounded name match: %s", exc)
        if scores:
                                                                                
                                           
            return scores
                                                                                     
        clauses = []
        for term in terms[:8]:
            escaped = re.escape(term)
            if len(term) < 2:
                continue
            clauses.append({"name": {"$regex": escaped, "$options": "i"}})
        if not clauses:
            return scores
        rows = await col.find(
            {"status": ProductStatus.ACTIVE, "$or": clauses},
            _PRODUCT_PROJECTION,
        ).limit(limit).to_list(length=limit)
        for row in rows:
            scores.setdefault(str(row["_id"]), 0.5)
        return scores

    async def _structured(self, category_ids: list[ObjectId], *, limit: int) -> list[str]:
        if not category_ids:
            return []
        cap = max(1, limit // 2)
        col = mongo_manager.collection(CollectionName.PRODUCTS)
        rows = await (
            col.find(
                {"status": ProductStatus.ACTIVE, "category_id": {"$in": category_ids}},
                {"_id": 1},
            )
            .sort([("updated_at", -1)])
            .limit(cap)
            .to_list(length=cap)
        )
        return [str(row["_id"]) for row in rows]

    async def _semantic(
        self,
        requirements: ProcurementRequirements,
        *,
        category_ids: list[ObjectId],
        lexical_ids: list[str],
        limit: int,
    ) -> list[tuple[str, float]]:
        query = " ".join(normalize_query_terms(requirements))
        if not query or self._embedder is None:
            return []
        try:
            vectors = await self._embedder.embed([query])
        except Exception as exc:
            logger.warning("Query embedding failed; semantic retrieval skipped: %s", exc)
            return []
        if not vectors:
            return []
        query_vector = vectors[0]
        if self._settings.ai_vector_search_enabled:
            hits = await self._vector_search(query_vector, limit=limit)
            if hits:
                return hits
        return await self._bounded_cosine(
            query_vector,
            category_ids=category_ids,
            lexical_ids=lexical_ids,
            limit=limit,
        )

    async def _vector_search(self, vector: list[float], *, limit: int) -> list[tuple[str, float]]:
        col = mongo_manager.collection(CollectionName.CATALOG_EMBEDDINGS)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self._settings.ai_vector_index_name,
                    "path": "embedding",
                    "queryVector": vector,
                    "numCandidates": max(limit * 4, 40),
                    "limit": limit,
                }
            },
            {"$project": {"product_id": 1, "score": {"$meta": "vectorSearchScore"}}},
        ]
        try:
            rows = await col.aggregate(pipeline).to_list(length=limit)
        except Exception as exc:
            logger.info("Vector search unavailable, using stored embeddings: %s", exc)
            return []
        hits: list[tuple[str, float]] = []
        for row in rows:
            pid = row.get("product_id")
            if pid is None:
                continue
            hits.append((str(pid), float(row.get("score") or 0.0)))
        return hits

    async def _bounded_cosine(
        self,
        vector: list[float],
        *,
        category_ids: list[ObjectId],
        lexical_ids: list[str],
        limit: int,
    ) -> list[tuple[str, float]]:
        col = mongo_manager.collection(CollectionName.CATALOG_EMBEDDINGS)
        clauses: list[dict[str, Any]] = []
        if category_ids:
            clauses.append({"category_id": {"$in": category_ids}})
        lexical_oids = []
        for pid in lexical_ids:
            try:
                lexical_oids.append(ObjectId(pid))
            except Exception:
                continue
        if lexical_oids:
            clauses.append({"product_id": {"$in": lexical_oids}})
        if not clauses:
            return []
        rows = await col.find(
            {"$or": clauses},
            {"product_id": 1, "embedding": 1},
        ).limit(max(limit * 5, 40)).to_list(length=max(limit * 5, 40))
        scored: list[tuple[str, float]] = []
        for row in rows:
            embedding = row.get("embedding")
            if not isinstance(embedding, list):
                continue
            score = cosine(vector, embedding)
            if score <= 0:
                continue
            scored.append((str(row["product_id"]), score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    async def _products(self, ids: list[str]) -> list[dict[str, Any]]:
        oids: list[ObjectId] = []
        for pid in ids:
            try:
                oids.append(ObjectId(pid))
            except Exception:
                continue
        if not oids:
            return []
        col = mongo_manager.collection(CollectionName.PRODUCTS)
        rows = await col.find(
            {"_id": {"$in": oids}, "status": ProductStatus.ACTIVE},
            _PRODUCT_PROJECTION,
        ).to_list(length=len(oids))
        order = {pid: index for index, pid in enumerate(ids)}
        rows.sort(key=lambda row: order.get(str(row["_id"]), 10_000))
        return rows

    async def _hydrate(
        self,
        products: list[dict[str, Any]],
        categories: dict[str, dict[str, Any]],
        lexical: dict[str, float],
        semantic_scores: dict[str, float],
    ) -> list[CatalogCandidate]:
        if not products:
            return []
        product_ids = [row["_id"] for row in products]
        business_ids = list({row["business_account_id"] for row in products if row.get("business_account_id")})
        profiles = mongo_manager.collection(CollectionName.SUPPLIER_PROFILES)
        businesses = mongo_manager.collection(CollectionName.BUSINESS_ACCOUNTS)
        inventories = mongo_manager.collection(CollectionName.INVENTORIES)
        prices = mongo_manager.collection(CollectionName.PRODUCT_PRICES)

        verified: set[str] = set()
        suppliers: dict[str, dict[str, Any]] = {}
        if business_ids:
            profile_rows = await profiles.find(
                {"business_account_id": {"$in": business_ids}, "verification_status": "verified"},
                {"business_account_id": 1},
            ).to_list(length=len(business_ids))
            verified = {str(row["business_account_id"]) for row in profile_rows}
            biz_rows = await businesses.find(
                {"_id": {"$in": business_ids}},
                {"name": 1, "type": 1},
            ).to_list(length=len(business_ids))
            suppliers = {str(row["_id"]): row for row in biz_rows}

        inv_map: dict[str, dict[str, Any]] = {}
        price_map: dict[str, list[dict[str, Any]]] = {}
        inv_rows = await inventories.find({"product_id": {"$in": product_ids}}).to_list(length=len(product_ids))
        for row in inv_rows:
            inv_map[str(row["product_id"])] = row
        price_rows = await prices.find(
            {"product_id": {"$in": product_ids}, "is_active": True},
            {"product_id": 1, "unit_price": 1, "currency": 1, "is_active": 1, "min_quantity": 1},
        ).to_list(length=max(len(product_ids) * 8, 1))
        for row in price_rows:
            price_map.setdefault(str(row["product_id"]), []).append(row)

        candidates: list[CatalogCandidate] = []
        for product in products:
            pid = str(product["_id"])
            business_id = str(product.get("business_account_id") or "")
            cat = categories.get(str(product.get("category_id") or ""))
            sources: set[str] = set()
            if pid in lexical:
                sources.add("lexical")
            if pid in semantic_scores:
                sources.add("semantic")
            if not sources:
                sources.add("structured")
            candidates.append(
                CatalogCandidate(
                    product=product,
                    supplier=suppliers.get(business_id) or {},
                    inventory=inv_map.get(pid),
                    prices=price_map.get(pid) or [],
                    category_name=str(cat.get("name")) if cat else None,
                    verified=business_id in verified,
                    lexical_score=lexical.get(pid),
                    semantic_score=semantic_scores.get(pid),
                    sources=sources,
                )
            )
        return candidates

def _union_ids(*groups: dict[str, float] | list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        keys = group.keys() if isinstance(group, dict) else group
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            ordered.append(key)
    return ordered

_background_syncs: set[asyncio.Task[Any]] = set()

def schedule_embedding_sync(
    products: list[dict[str, Any]],
    *,
    categories_by_id: dict[str, dict[str, Any]],
    embedder: Any,
    settings: Settings | None = None,
) -> None:
    if not products or embedder is None:
        return

    async def _run() -> None:
        try:
            await sync_embeddings_for_products(
                products,
                categories_by_id=categories_by_id,
                embedder=embedder,
                settings=settings,
            )
        except Exception:
            logger.warning("Background embedding sync failed", exc_info=True)

    try:
        task = asyncio.create_task(_run())
    except RuntimeError:
                                                                                 
        return
    _background_syncs.add(task)
    task.add_done_callback(_background_syncs.discard)

async def drain_embedding_syncs(grace_seconds: float = 5.0) -> None:
    if not _background_syncs:
        return
    pending = list(_background_syncs)
    _done, still_running = await asyncio.wait(pending, timeout=grace_seconds)
    for task in still_running:
        task.cancel()

async def sync_embeddings_for_products(
    products: list[dict[str, Any]],
    *,
    categories_by_id: dict[str, dict[str, Any]],
    embedder: Any,
    settings: Settings | None = None,
) -> int:
    cfg = settings or get_settings()
    if not products or embedder is None:
        return 0
    col = mongo_manager.collection(CollectionName.CATALOG_EMBEDDINGS)
    batch = products[: cfg.ai_embedding_sync_batch]
    existing_rows = await col.find(
        {"product_id": {"$in": [product["_id"] for product in batch]}},
        {"product_id": 1, "content_hash": 1},
    ).to_list(length=len(batch) or 1)
    hashes = {str(row["product_id"]): row.get("content_hash") for row in existing_rows}
    pending: list[tuple[dict[str, Any], str, str]] = []
    for product in batch:
        cat = categories_by_id.get(str(product.get("category_id") or ""))
        cat_name = str(cat.get("name")) if cat else None
        digest = content_hash(product, cat_name)
        if hashes.get(str(product["_id"])) == digest:
            continue
        text = " ".join(
            bit
            for bit in (
                str(product.get("name") or ""),
                cat_name or "",
                str(product.get("description") or "")[:400],
            )
            if bit
        )
        pending.append((product, digest, text))
    if not pending:
        return 0
    try:
        vectors = await embedder.embed([item[2] for item in pending])
    except Exception as exc:
        logger.warning("Embedding sync skipped: %s", exc)
        return 0
    from app.shared.utils.datetime import utc_now

    now = utc_now()
    operations = [
        UpdateOne(
            {"product_id": product["_id"]},
            {
                "$set": {
                    "product_id": product["_id"],
                    "category_id": product.get("category_id"),
                    "business_account_id": product.get("business_account_id"),
                    "content_hash": digest,
                    "embedding": vector,
                    "model": cfg.ai_embedding_model or "text-embedding-3-small",
                    "embedded_at": now,
                }
            },
            upsert=True,
        )
        for (product, digest, _text), vector in zip(pending, vectors, strict=False)
    ]
    if not operations:
        return 0
    await col.bulk_write(operations, ordered=False)
    return len(operations)
