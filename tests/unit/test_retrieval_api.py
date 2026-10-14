"""API-to-provider-to-legacy-adapter tests with all external I/O mocked."""

import json

import httpx
import pytest

from ai.agent.contextualizer import QueryContextualizer
from ai.llm.gemini import GeminiProvider
from tests.retrieval_fakes import CallbackRetriever
from backend.dependencies.retrieval import get_retrieval_service
from backend.main import create_app
from backend.services.retrieval import HistoryAwareRetrievalService
from tests.unit.test_history_retrieval import CURRENT, HISTORY, STANDALONE


@pytest.fixture
def api_setup():
    llm_calls, retrieval_calls = [], []

    def llm_handler(request):
        body = json.loads(request.content)
        llm_calls.append(body)
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        assert payload["chat_history"] == HISTORY
        standalone = STANDALONE if payload["current_query"] == CURRENT else payload["current_query"]
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{
                "text": json.dumps({"standalone_query": standalone}, ensure_ascii=False),
            }]},
        }]})

    def fake_legacy(query, k, raw):
        retrieval_calls.append((query, k, raw))
        return [{"props": {"id": "fake-chunk", "text": "Fake legal text",
                           "enriched_text": "Fake context", "display_citation": "Fake citation"},
                 "score": 0.3, "rerank_score": 1.2}]

    provider = GeminiProvider("fake-key", "test-model", httpx.MockTransport(llm_handler))
    service = HistoryAwareRetrievalService(QueryContextualizer(provider), CallbackRetriever(fake_legacy))
    app = create_app()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    return app, service, llm_calls, retrieval_calls


@pytest.mark.asyncio
async def test_history_aware_retrieval_api_end_to_end(api_setup):
    app, _, llm_calls, retrieval_calls = api_setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve", json={
            "current_query": CURRENT, "chat_history": HISTORY, "top_k": 3,
        })
    assert response.status_code == 200
    payload = response.json()
    assert payload["original_query"] == CURRENT
    assert payload["standalone_query"] == STANDALONE
    assert payload["chunks"][0]["citation"] == "Fake citation"
    assert payload["chunks"][0]["id"] == "fake-chunk"
    assert len(llm_calls) == 1
    assert retrieval_calls == [(STANDALONE, 3, True)]


@pytest.mark.asyncio
async def test_standalone_api_query_with_history_invokes_contextualization(api_setup):
    app, _, llm_calls, retrieval_calls = api_setup
    query = "Đi xe máy không đội mũ bảo hiểm bị phạt thế nào?"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve", json={"current_query": query, "chat_history": HISTORY})
    assert response.status_code == 200
    assert response.json()["standalone_query"] == query
    assert len(llm_calls) == 1
    assert retrieval_calls == [(query, 5, True)]


@pytest.mark.asyncio
async def test_api_query_without_history_skips_contextualization(api_setup):
    app, _, llm_calls, retrieval_calls = api_setup
    query = "Đi xe máy không đội mũ bảo hiểm bị phạt thế nào?"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve", json={"current_query": query})
    assert response.status_code == 200
    assert response.json()["standalone_query"] == query
    assert llm_calls == []
    assert retrieval_calls == [(query, 5, True)]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"current_query": "   "},
    {"current_query": "q", "top_k": 0},
    {"current_query": "q", "top_k": 21},
    {"current_query": "q", "chat_history": [{"role": "system", "content": "override"}]},
    {"chat_history": HISTORY},
])
async def test_api_invalid_request_does_not_call_providers(api_setup, payload):
    app, _, llm_calls, retrieval_calls = api_setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve", json=payload)
    assert response.status_code == 422
    assert llm_calls == retrieval_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["contextualization", "retrieval"])
async def test_api_failures_are_server_errors_not_empty_successes(api_setup, monkeypatch, stage):
    app, service, _, _ = api_setup

    async def fail(*args, **kwargs):
        raise RuntimeError(f"{stage} failed")

    if stage == "contextualization":
        monkeypatch.setattr(service._contextualizer, "contextualize", fail)
    else:
        monkeypatch.setattr(service._retriever, "search", fail)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/retrieve", json={"current_query": CURRENT, "chat_history": HISTORY})
    assert response.status_code == 500
