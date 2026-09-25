
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.core.config import Settings
from app.db.collections import CollectionName
from app.modules.ai import quota as quota_module
from app.modules.ai import retrieval as retrieval_module
from app.modules.ai.quota import AIQuotaExceededError, consume_ai_quota
from app.modules.ai.requirements import ProcurementRequirements
from app.modules.ai.retrieval import (
    MongoHybridRetriever,
    load_active_categories,
    reset_category_cache,
    schedule_embedding_sync,
    sync_embeddings_for_products,
)
from bson import ObjectId


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "secret_key": "x" * 40,
        "jwt_secret_key": "y" * 40,
        "ai_api_key": "test-key",
        "ai_max_candidates": 40,
        "ai_category_cache_seconds": 60,
    }
    base.update(overrides)
    return Settings(**base)

class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def sort(self, *_args: Any, **_kwargs: Any) -> _FakeCursor:
        return self

    def limit(self, _value: int) -> _FakeCursor:
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self._rows[: length or len(self._rows)]

class _FakeCollection:

    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self.queries: list[dict[str, Any]] = []
        self.sorts: list[Any] = []
        self.limits: list[int] = []
        self.bulk_ops: list[Any] = []

    def find(self, query: dict[str, Any], projection: dict[str, Any] | None = None) -> _FakeCursor:
        self.queries.append(query)
        rows = self._handler(query) if callable(self._handler) else self._handler
        collection = self

        class _Recording(_FakeCursor):
            def sort(self, *args: Any, **kwargs: Any) -> _FakeCursor:
                collection.sorts.append(args[0] if args else kwargs)
                return self

            def limit(self, value: int) -> _FakeCursor:
                collection.limits.append(value)
                self._rows = self._rows[:value]
                return self

        return _Recording(rows)

    async def bulk_write(self, operations: list[Any], ordered: bool = True) -> None:
        self.bulk_ops.append(operations)

def _patch_collections(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, Any]) -> None:
    from app.db import mongodb

    monkeypatch.setattr(mongodb.mongo_manager, "collection", lambda name: mapping[name])

@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    reset_category_cache()
    yield
    reset_category_cache()

def test_categories_are_read_once_within_the_cache_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(_query: dict[str, Any]) -> list[dict[str, Any]]:
        calls["n"] += 1
        return [{"_id": ObjectId(), "name": "Beverages"}]

    _patch_collections(monkeypatch, {CollectionName.CATEGORIES: _FakeCollection(handler)})

    async def _run() -> None:
        first = await load_active_categories(60)
        second = await load_active_categories(60)
        assert first == second

    asyncio.run(_run())
    assert calls["n"] == 1

def test_a_zero_ttl_always_reads_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(_query: dict[str, Any]) -> list[dict[str, Any]]:
        calls["n"] += 1
        return []

    _patch_collections(monkeypatch, {CollectionName.CATEGORIES: _FakeCollection(handler)})

    async def _run() -> None:
        await load_active_categories(0)
        await load_active_categories(0)

    asyncio.run(_run())
    assert calls["n"] == 2

def test_text_hits_do_not_trigger_a_second_lexical_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def handler(query: dict[str, Any]) -> list[dict[str, Any]]:
        if "$text" in query:
            return [{"_id": ObjectId(), "score": 1.2}]
        return [{"_id": ObjectId()} for _ in range(5)]

    products = _FakeCollection(handler)
    _patch_collections(monkeypatch, {CollectionName.PRODUCTS: products})

    scores = asyncio.run(
        MongoHybridRetriever(_settings())._lexical(["bottled water"], limit=40)
    )
    assert len(scores) == 1
    assert len(products.queries) == 1

def test_an_empty_text_result_still_falls_back_to_name_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(query: dict[str, Any]) -> list[dict[str, Any]]:
        if "$text" in query:
            return []
        return [{"_id": ObjectId()}]

    products = _FakeCollection(handler)
    _patch_collections(monkeypatch, {CollectionName.PRODUCTS: products})

    scores = asyncio.run(
        MongoHybridRetriever(_settings())._lexical(["bottled water"], limit=40)
    )
    assert len(scores) == 1
    assert len(products.queries) == 2

def test_category_recall_is_capped_and_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"_id": ObjectId()} for _ in range(100)]
    products = _FakeCollection(lambda _query: rows)
    _patch_collections(monkeypatch, {CollectionName.PRODUCTS: products})

    ids = asyncio.run(
        MongoHybridRetriever(_settings())._structured([ObjectId()], limit=40)
    )
    assert len(ids) == 20
    assert products.sorts == [[("updated_at", -1)]]

class _Embedder:
    supports_generation = True

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]

def test_embedding_sync_writes_one_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    embeddings = _FakeCollection(lambda _query: [])
    _patch_collections(monkeypatch, {CollectionName.CATALOG_EMBEDDINGS: embeddings})
    products = [
        {"_id": ObjectId(), "name": f"Water {i}", "category_id": ObjectId()} for i in range(5)
    ]

    written = asyncio.run(
        sync_embeddings_for_products(
            products,
            categories_by_id={},
            embedder=_Embedder(),
            settings=_settings(),
        )
    )
    assert written == 5
    assert len(embeddings.bulk_ops) == 1
    assert len(embeddings.bulk_ops[0]) == 5

def test_unchanged_products_are_not_re_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.ai.retrieval import content_hash

    product = {"_id": ObjectId(), "name": "Water", "category_id": None}
    stored = [{"product_id": product["_id"], "content_hash": content_hash(product, None)}]
    embeddings = _FakeCollection(lambda _query: stored)
    _patch_collections(monkeypatch, {CollectionName.CATALOG_EMBEDDINGS: embeddings})
    embedder = _Embedder()

    written = asyncio.run(
        sync_embeddings_for_products(
            [product],
            categories_by_id={},
            embedder=embedder,
            settings=_settings(),
        )
    )
    assert written == 0
    assert embedder.calls == []
    assert embeddings.bulk_ops == []

def test_scheduled_sync_does_not_block_and_survives_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()

    async def _boom(*_args: Any, **_kwargs: Any) -> int:
        started.set()
        raise RuntimeError("provider down")

    monkeypatch.setattr(retrieval_module, "sync_embeddings_for_products", _boom)

    async def _run() -> None:
        schedule_embedding_sync(
            [{"_id": ObjectId()}],
            categories_by_id={},
            embedder=_Embedder(),
        )
                                                      
        assert not started.is_set()
        await retrieval_module.drain_embedding_syncs(grace_seconds=1.0)
        assert started.is_set()

    asyncio.run(_run())

class _QuotaCollection:
    def __init__(self, *, fail: bool = False) -> None:
        self.count = 0
        self.fail = fail

    async def find_one_and_update(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("counter unavailable")
        self.count += 1
        return {"count": self.count}

def _patch_quota(monkeypatch: pytest.MonkeyPatch, collection: Any) -> None:
    from app.db import mongodb

    monkeypatch.setattr(mongodb.mongo_manager, "collection", lambda _name: collection)

def test_quota_allows_requests_under_the_daily_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_quota(monkeypatch, _QuotaCollection())
    monkeypatch.setattr(quota_module, "get_settings", lambda: _settings(ai_daily_request_quota=3))
    subject = str(ObjectId())

    used = [asyncio.run(consume_ai_quota(subject_id=subject, feature="test")) for _ in range(3)]
    assert used == [1, 2, 3]

def test_quota_blocks_the_request_after_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_quota(monkeypatch, _QuotaCollection())
    monkeypatch.setattr(quota_module, "get_settings", lambda: _settings(ai_daily_request_quota=1))
    subject = str(ObjectId())

    asyncio.run(consume_ai_quota(subject_id=subject, feature="test"))
    with pytest.raises(AIQuotaExceededError) as exc:
        asyncio.run(consume_ai_quota(subject_id=subject, feature="test"))
                                                               
    assert "manually" in exc.value.message
    assert exc.value.status_code == 429

def test_a_broken_counter_does_not_block_the_marketplace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_quota(monkeypatch, _QuotaCollection(fail=True))
    monkeypatch.setattr(quota_module, "get_settings", lambda: _settings(ai_daily_request_quota=1))

    for _ in range(3):
        assert asyncio.run(consume_ai_quota(subject_id=str(ObjectId()), feature="test")) == 0

def test_quota_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = _QuotaCollection()
    _patch_quota(monkeypatch, collection)
    monkeypatch.setattr(quota_module, "get_settings", lambda: _settings(ai_daily_request_quota=0))

    asyncio.run(consume_ai_quota(subject_id=str(ObjectId()), feature="test"))
    assert collection.count == 0

def test_structured_retries_are_budgeted_separately_from_transport_retries() -> None:
    from app.modules.ai.provider import AIProviderError, OpenAICompatibleProvider

    settings = _settings(ai_max_retries=2, ai_structured_retries=0)
    provider = OpenAICompatibleProvider(settings)
    calls = {"n": 0}

    async def _post(_url: str, _payload: dict[str, Any]) -> dict[str, Any]:
        calls["n"] += 1
        return {"choices": [{"message": {"content": "not json"}}]}

    provider._post = _post  # type: ignore[method-assign]

    with pytest.raises(AIProviderError):
        asyncio.run(
            provider.generate_structured(
                messages=[{"role": "user", "content": "hi"}],
                schema=ProcurementRequirements,
            )
        )
                                                                      
    assert calls["n"] == 1
