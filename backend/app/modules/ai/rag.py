"""RAG retriever — advisory context only, never marketplace writes.

Indexes catalog text (products + categories) and returns top-k snippets for
the LLM / stub extractor. Matching prices, stock, and verification still come
from Mongo + RecommendationEngine — not from retrieved prose.
"""

from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.db.collections import CollectionName
from app.db.mongodb import mongo_manager
from app.modules.catalog.constants import ProductStatus

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2]


@dataclass(slots=True)
class RagChunk:
    """One retrievable unit of marketplace vocabulary."""

    id: str
    text: str
    source_type: str = "catalog"
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class RagRetriever(ABC):
    @abstractmethod
    async def upsert(self, chunks: list[RagChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def retrieve(self, query: str, *, top_k: int = 8) -> list[RagChunk]:
        raise NotImplementedError

    @property
    def size(self) -> int:
        return 0


class NoOpRagRetriever(RagRetriever):
    """Disabled RAG — always empty context."""

    async def upsert(self, chunks: list[RagChunk]) -> None:
        return None

    async def clear(self) -> None:
        return None

    async def retrieve(self, query: str, *, top_k: int = 8) -> list[RagChunk]:
        return []


class InMemoryLexicalRagRetriever(RagRetriever):
    """TF-IDF-ish lexical retrieval. No external vector DB or embeddings required."""

    def __init__(self) -> None:
        self._chunks: dict[str, RagChunk] = {}
        self._df: dict[str, int] = {}
        self._doc_tokens: dict[str, list[str]] = {}

    @property
    def size(self) -> int:
        return len(self._chunks)

    async def clear(self) -> None:
        self._chunks.clear()
        self._df.clear()
        self._doc_tokens.clear()

    async def upsert(self, chunks: list[RagChunk]) -> None:
        for chunk in chunks:
            old_tokens = self._doc_tokens.pop(chunk.id, None)
            if old_tokens is not None:
                for tok in set(old_tokens):
                    self._df[tok] = max(0, self._df.get(tok, 1) - 1)
                    if self._df[tok] == 0:
                        self._df.pop(tok, None)

            tokens = _tokens(chunk.text)
            self._chunks[chunk.id] = chunk
            self._doc_tokens[chunk.id] = tokens
            for tok in set(tokens):
                self._df[tok] = self._df.get(tok, 0) + 1

    def _tfidf(self, tokens: list[str], *, n_docs: int) -> dict[str, float]:
        if not tokens or n_docs <= 0:
            return {}
        tf: dict[str, int] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        length = len(tokens)
        weights: dict[str, float] = {}
        for tok, count in tf.items():
            df = self._df.get(tok, 0)
            idf = math.log((1 + n_docs) / (1 + df)) + 1.0
            weights[tok] = (count / length) * idf
        return weights

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        shared = 0.0
        for key, av in a.items():
            bv = b.get(key)
            if bv is not None:
                shared += av * bv
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return shared / (na * nb)

    async def retrieve(self, query: str, *, top_k: int = 8) -> list[RagChunk]:
        q = query.strip()
        if not q or top_k <= 0 or not self._chunks:
            return []
        n_docs = len(self._chunks)
        q_vec = self._tfidf(_tokens(q), n_docs=n_docs)
        scored: list[RagChunk] = []
        for chunk_id, tokens in self._doc_tokens.items():
            score = self._cosine(q_vec, self._tfidf(tokens, n_docs=n_docs))
            if score <= 0.0:
                continue
            base = self._chunks[chunk_id]
            scored.append(
                RagChunk(
                    id=base.id,
                    text=base.text,
                    source_type=base.source_type,
                    metadata=dict(base.metadata),
                    score=score,
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


class OpenAIEmbeddingRagRetriever(RagRetriever):
    """In-memory cosine retrieval over OpenAI embedding vectors.

    Falls back to lexical scoring when the embeddings API is unavailable.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        lexical: InMemoryLexicalRagRetriever | None = None,
    ) -> None:
        self._settings = settings
        self._lexical = lexical or InMemoryLexicalRagRetriever()
        self._embeddings: dict[str, list[float]] = {}

    @property
    def size(self) -> int:
        return self._lexical.size

    async def clear(self) -> None:
        await self._lexical.clear()
        self._embeddings.clear()

    async def upsert(self, chunks: list[RagChunk]) -> None:
        await self._lexical.upsert(chunks)
        if not chunks:
            return
        try:
            vectors = await self._embed([c.text for c in chunks])
        except Exception as exc:
            logger.warning("RAG embedding upsert failed; lexical only: %s", exc)
            return
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._embeddings[chunk.id] = vector

    async def retrieve(self, query: str, *, top_k: int = 8) -> list[RagChunk]:
        q = query.strip()
        if not q or top_k <= 0:
            return []
        if not self._embeddings:
            return await self._lexical.retrieve(q, top_k=top_k)
        try:
            q_vec = (await self._embed([q]))[0]
        except Exception as exc:
            logger.warning("RAG query embed failed; lexical fallback: %s", exc)
            return await self._lexical.retrieve(q, top_k=top_k)

        scored: list[RagChunk] = []
        for chunk_id, vector in self._embeddings.items():
            base = self._lexical._chunks.get(chunk_id)
            if base is None:
                continue
            score = _cosine_dense(q_vec, vector)
            if score <= 0.0:
                continue
            scored.append(
                RagChunk(
                    id=base.id,
                    text=base.text,
                    source_type=base.source_type,
                    metadata=dict(base.metadata),
                    score=score,
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        api_key = self._settings.ai_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise RuntimeError("AI_API_KEY required for embedding RAG")
        model = self._settings.ai_embedding_model or "text-embedding-3-small"
        payload = {"model": model, "input": texts}
        async with httpx.AsyncClient(timeout=self._settings.ai_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()["data"]
            data.sort(key=lambda row: row["index"])
            return [row["embedding"] for row in data]


def _cosine_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    shared = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return shared / (na * nb)


def format_rag_context(chunks: list[RagChunk], *, max_chars: int = 3500) -> str:
    """Serialize retrieved chunks for an LLM / stub prompt."""
    if not chunks:
        return ""
    lines = [
        "Retrieved TradeBay catalog vocabulary (advisory only — do not invent prices, "
        "stock, MOQs, or verification from this list):"
    ]
    used = len(lines[0])
    for i, chunk in enumerate(chunks, start=1):
        meta_bits = []
        if chunk.metadata.get("name"):
            meta_bits.append(str(chunk.metadata["name"]))
        if chunk.metadata.get("category"):
            meta_bits.append(f"category={chunk.metadata['category']}")
        header = f"{i}. [{chunk.source_type}] " + (", ".join(meta_bits) if meta_bits else chunk.id)
        body = chunk.text.strip().replace("\n", " ")
        block = f"{header}\n{body}"
        if used + len(block) + 2 > max_chars:
            break
        lines.append(block)
        used += len(block) + 2
    return "\n\n".join(lines)


class CatalogRagIndexer:
    """Build RagChunks from live catalog collections."""

    def __init__(self, *, product_limit: int = 400) -> None:
        self.product_limit = product_limit

    async def build_chunks(self) -> list[RagChunk]:
        products_col = mongo_manager.collection(CollectionName.PRODUCTS)
        categories_col = mongo_manager.collection(CollectionName.CATEGORIES)

        categories = {
            str(c["_id"]): c
            for c in await categories_col.find({"is_active": True}).to_list(length=300)
        }
        products = (
            await products_col.find({"status": ProductStatus.ACTIVE})
            .sort("updated_at", -1)
            .to_list(length=self.product_limit)
        )

        chunks: list[RagChunk] = []
        for cat in categories.values():
            name = str(cat.get("name") or "").strip()
            if not name:
                continue
            desc = str(cat.get("description") or "").strip()
            text = f"Category: {name}. {desc}".strip()
            chunks.append(
                RagChunk(
                    id=f"category:{cat['_id']}",
                    text=text,
                    source_type="category",
                    metadata={"category": name, "category_id": str(cat["_id"])},
                )
            )

        for product in products:
            name = str(product.get("name") or "").strip()
            if not name:
                continue
            cat = categories.get(str(product.get("category_id") or ""))
            cat_name = str(cat.get("name") or "") if cat else ""
            desc = str(product.get("description") or "").strip()
            unit = str(product.get("unit") or "").strip()
            origin = str(product.get("origin") or "").strip()
            bits = [f"Product: {name}."]
            if cat_name:
                bits.append(f"Category: {cat_name}.")
            if unit:
                bits.append(f"Unit: {unit}.")
            if origin:
                bits.append(f"Origin: {origin}.")
            if desc:
                bits.append(desc[:400])
            chunks.append(
                RagChunk(
                    id=f"product:{product['_id']}",
                    text=" ".join(bits),
                    source_type="product",
                    metadata={
                        "name": name,
                        "product_id": str(product["_id"]),
                        "category": cat_name or None,
                    },
                )
            )
        return chunks


_retriever_singleton: RagRetriever | None = None
_index_loaded = False


def reset_rag_cache() -> None:
    global _retriever_singleton, _index_loaded
    _retriever_singleton = None
    _index_loaded = False


def get_rag_retriever(settings: Settings | None = None) -> RagRetriever:
    """Factory — NoOp when disabled; lexical or embedding-backed when enabled."""
    global _retriever_singleton
    if _retriever_singleton is not None:
        return _retriever_singleton

    cfg = settings or get_settings()
    if not cfg.ai_rag_enabled:
        _retriever_singleton = NoOpRagRetriever()
        return _retriever_singleton

    mode = (cfg.ai_rag_mode or "lexical").strip().lower()
    if mode in {"embedding", "openai", "openai_embedding"}:
        _retriever_singleton = OpenAIEmbeddingRagRetriever(cfg)
    else:
        _retriever_singleton = InMemoryLexicalRagRetriever()
    return _retriever_singleton


async def ensure_catalog_rag_index(
    retriever: RagRetriever | None = None,
    *,
    settings: Settings | None = None,
    force: bool = False,
) -> RagRetriever:
    """Lazily load catalog chunks into the process-local retriever once."""
    global _index_loaded
    cfg = settings or get_settings()
    store = retriever or get_rag_retriever(cfg)
    if isinstance(store, NoOpRagRetriever):
        return store
    if _index_loaded and not force and store.size > 0:
        return store
    try:
        chunks = await CatalogRagIndexer(product_limit=cfg.ai_rag_product_limit).build_chunks()
        if force:
            await store.clear()
        await store.upsert(chunks)
        _index_loaded = True
        logger.info("RAG index loaded with %s catalog chunks", len(chunks))
    except Exception as exc:
        logger.warning("RAG catalog index skipped: %s", exc)
    return store
