"""Agentic endpoint wire-format tests using in-memory Gemini and legacy mocks."""

import json

import httpx
import pytest

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter
from ai.llm.gemini import GeminiProvider
from tests.retrieval_fakes import CallbackRetriever
from backend.dependencies.retrieval import get_agentic_retrieval_service
from backend.main import create_app
from backend.services.agentic_retrieval import AgenticRetrievalService
from tests.unit.test_agentic_retrieval import GAP, QUESTION, REWRITTEN, chunk, make_service


@pytest.mark.asyncio
async def test_api_with_history_contextualizes_grades_rewrites_and_returns_trace():
    llm_calls, retrieval_calls = [], []
    current = "Ô tô vượt đèn đỏ thì sao?"
    history = [{"role": "user", "content": "Xe máy vượt đèn đỏ có bị tước giấy phép lái xe không?"}]
    responses = [
        {"standalone_query": QUESTION},
        {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]},
        {"rewritten_query": REWRITTEN},
        {"sufficient": True, "reason": "Requested sanction is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]},
    ]

    def handler(request):
        body = json.loads(request.content)
        llm_calls.append(body)
        index = len(llm_calls) - 1
        assert index < len(responses)
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        if index == 0:
            assert payload == {"current_query": current, "chat_history": history}
        else:
            assert payload["question"] == QUESTION
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": json.dumps(responses[index])}]},
        }]})

    def legacy(query, k, raw):
        retrieval_calls.append((query, k, raw))
        return [{"props": {"id": f"chunk-{len(retrieval_calls)}", "text": "Test evidence",
                           "enriched_text": "Test context", "display_citation": f"Test citation {len(retrieval_calls)}"},
                 "rerank_score": 0.5}]

    provider = GeminiProvider("fake-key", "test-model", httpx.MockTransport(handler))
    service = AgenticRetrievalService(
        QueryContextualizer(provider), CallbackRetriever(legacy),
        EvidenceGrader(provider), QueryRewriter(provider),
    )
    app = create_app()
    app.dependency_overrides[get_agentic_retrieval_service] = lambda: service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve/agentic", json={
            "current_query": current, "chat_history": history, "top_k": 3,
        })
    assert response.status_code == 200
    payload = response.json()
    assert payload["original_query"] == current
    assert payload["standalone_query"] == QUESTION
    assert payload["retrieval_queries"] == [QUESTION, REWRITTEN]
    assert payload["retrieval_attempts"] == 2
    assert payload["rewritten_query"] == REWRITTEN
    assert payload["selected_attempt"] == 2
    assert payload["grade"]["sufficient"] is True
    assert [item["id"] for item in payload["chunks"]] == ["chunk-1", "chunk-2"]
    assert payload["chunks"][1]["citation"] == "Test citation 2"
    assert payload["attempts"][1]["evidence_chunk_ids"] == ["chunk-1", "chunk-2"]
    assert payload["attempts"][0]["grade"]["sufficient"] is False
    assert payload["attempts"][0]["chunk_ids"] == ["chunk-1"]
    assert retrieval_calls == [(QUESTION, 3, True), (REWRITTEN, 3, True)]
    assert len(llm_calls) == 4


@pytest.mark.asyncio
async def test_api_empty_evidence_at_limit_is_explicit_insufficient_success():
    service, provider, retriever, _ = make_service([], [[]], max_attempts=1)
    app = create_app()
    app.dependency_overrides[get_agentic_retrieval_service] = lambda: service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/retrieve/agentic", json={"current_query": QUESTION})
    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"]["sufficient"] is False
    assert payload["chunks"] == []
    assert payload["retrieval_attempts"] == 1
    assert provider.calls == []
    assert len(retriever.calls) == 1


@pytest.mark.asyncio
async def test_api_grader_failure_is_server_error_not_insufficient_success():
    service, _, retriever, _ = make_service([
        (EvidenceGrade, RuntimeError("provider unavailable")),
    ], [[chunk("first")]])
    app = create_app()
    app.dependency_overrides[get_agentic_retrieval_service] = lambda: service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/retrieve/agentic", json={"current_query": QUESTION})
    assert response.status_code == 500
    assert len(retriever.calls) == 1
