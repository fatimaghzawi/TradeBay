
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from app.core.config import Settings
from app.modules.ai import provider as provider_module
from app.modules.ai.provider import (
    AIProviderError,
    OpenAICompatibleProvider,
    get_http_client,
)
from app.modules.ai.requirements import ProcurementRequirements


def _settings(**overrides) -> Settings:
    base = {
        "secret_key": "x" * 40,
        "jwt_secret_key": "y" * 40,
        "ai_api_key": "test-key",
        "ai_base_url": "https://provider.test/v1",
        "ai_chat_model": "test-chat",
        "ai_embedding_model": "test-embed",
        "ai_timeout_seconds": 5,
        "ai_max_retries": 1,
    }
    base.update(overrides)
    return Settings(**base)

def _use_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(_record))
    monkeypatch.setattr(provider_module, "get_http_client", lambda: client)
    return seen

def test_shared_client_is_usable() -> None:
    client = get_http_client()
    assert isinstance(client, httpx.AsyncClient)
    assert get_http_client() is client

def test_chat_sends_auth_and_model_and_parses_body(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = ProcurementRequirements(
        business_description="Need 500 cases of sparkling water in Beirut",
        product_requirements=["sparkling water"],
    ).model_dump()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    seen = _use_transport(monkeypatch, handler)
    result = asyncio.run(
        OpenAICompatibleProvider(_settings()).generate_structured(
            messages=[{"role": "user", "content": "extract"}],
            schema=ProcurementRequirements,
        )
    )
    assert result.product_requirements == ["sparkling water"]
    request = seen[0]
    assert str(request.url) == "https://provider.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "test-chat"
    assert body["response_format"]["type"] == "json_schema"

def test_rate_limit_returns_a_marketplace_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_transport(
        monkeypatch,
        lambda _r: httpx.Response(429, json={"error": {"type": "rate_limit_exceeded"}}),
    )
    with pytest.raises(AIProviderError) as caught:
        asyncio.run(OpenAICompatibleProvider(_settings()).embed(["water"]))
    assert "busy" in caught.value.message.lower()
    assert "429" not in caught.value.message

def test_exhausted_quota_does_not_tell_the_buyer_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_transport(
        monkeypatch,
        lambda _r: httpx.Response(
            429,
            json={
                "error": {
                    "type": "insufficient_quota",
                    "code": "credit_balance_exhausted",
                    "message": "You have no credits remaining.",
                }
            },
        ),
    )
    with pytest.raises(AIProviderError) as caught:
        asyncio.run(OpenAICompatibleProvider(_settings()).embed(["water"]))
    message = caught.value.message.lower()
    assert "unavailable" in message
    assert "try again" not in message
    assert "credit" not in message and "quota" not in message

def test_json_schema_rejection_falls_back_to_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = ProcurementRequirements(business_description="Need cleaning products").model_dump()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(400, json={"error": "response_format not supported"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    seen = _use_transport(monkeypatch, handler)
    result = asyncio.run(
        OpenAICompatibleProvider(_settings()).generate_structured(
            messages=[{"role": "user", "content": "extract"}],
            schema=ProcurementRequirements,
        )
    )
    assert result.business_description == "Need cleaning products"
    assert len(seen) == 2
    assert json.loads(seen[1].content)["response_format"]["type"] == "json_object"

def test_server_error_is_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "upstream"})
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
        )

    _use_transport(monkeypatch, handler)
    vectors = asyncio.run(OpenAICompatibleProvider(_settings()).embed(["sparkling water"]))
    assert vectors == [[0.1, 0.2]]
    assert calls["n"] == 2

def test_timeout_exhausts_retries_and_stays_user_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out", request=request)

    _use_transport(monkeypatch, handler)
    with pytest.raises(AIProviderError) as caught:
        asyncio.run(OpenAICompatibleProvider(_settings()).embed(["water"]))
    assert calls["n"] == 2
    assert "unavailable" in caught.value.message.lower()
    assert "timeout" not in caught.value.message.lower()

def test_embeddings_are_returned_in_request_order(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.9]},
                    {"index": 0, "embedding": [0.1]},
                ]
            },
        )

    _use_transport(monkeypatch, handler)
    vectors = asyncio.run(OpenAICompatibleProvider(_settings()).embed(["first", "second"]))
    assert vectors == [[0.1], [0.9]]

def test_internal_client_fault_is_not_reported_as_bad_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    def _broken() -> httpx.AsyncClient:
        raise AttributeError("'function' object has no attribute 'is_closed'")

    monkeypatch.setattr(provider_module, "get_http_client", _broken)
    with pytest.raises(AIProviderError) as caught:
        asyncio.run(
            OpenAICompatibleProvider(_settings()).generate_structured(
                messages=[{"role": "user", "content": "extract"}],
                schema=ProcurementRequirements,
            )
        )
    assert "unavailable" in caught.value.message.lower()
