"""Orchestration tests using a fake provider and the existing Retriever contract."""

import json
from typing import Any, List, Type

from pydantic import ValidationError
import pytest

from ai.agent.contextualizer import QueryContextualizer
from ai.llm.base import LLMMessage, LLMProvider, LLMResponse, T
from ai.llm.gemini import GeminiProvider
from ai.retrieval.base import RetrievedChunk, Retriever
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter
from backend.services.retrieval import HistoryAwareRetrievalService

CURRENT = "Còn ô tô thì sao?"
STANDALONE = "Người điều khiển ô tô vượt đèn đỏ bị xử phạt bao nhiêu?"
HISTORY = [{"role": "user", "content": "Xe máy vượt đèn đỏ phạt bao nhiêu?"}]


class RecordingProvider(LLMProvider):
    def __init__(self, output=STANDALONE):
        self.output = output
        self.calls = []

    async def generate(self, messages, temperature=0.1, **kwargs) -> LLMResponse:
        pytest.fail("Only structured contextualization should run")

    async def generate_structured(
        self, messages: List[LLMMessage], response_schema: Type[T],
        temperature: float = 0.1, **kwargs: Any,
    ) -> T:
        self.calls.append(json.loads(messages[-1].content))
        return response_schema(standalone_query=self.output)


class RecordingRetriever(Retriever):
    def __init__(self):
        self.calls = []
        self.chunks = [RetrievedChunk(
            id="test", text="Fake legal text", enriched_text="Fake context",
            citation="Fake citation", score=-0.5,
        )]

    async def search(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        self.calls.append((query, top_k))
        return self.chunks


@pytest.mark.asyncio
async def test_follow_up_passes_standalone_query_to_retriever():
    provider, retriever = RecordingProvider(), RecordingRetriever()
    service = HistoryAwareRetrievalService(QueryContextualizer(provider), retriever)
    result = await service.retrieve(CURRENT, HISTORY, top_k=3)
    assert provider.calls == [{"current_query": CURRENT, "chat_history": HISTORY}]
    assert retriever.calls == [(STANDALONE, 3)]
    assert result.original_query == CURRENT
    assert result.standalone_query == STANDALONE
    assert result.chunks == retriever.chunks


@pytest.mark.asyncio
async def test_orchestration_uses_legacy_adapter_without_changing_call_contract():
    calls = []

    def fake_legacy(query, k, raw):
        calls.append((query, k, raw))
        return [{"props": {"text": "Fake text", "enriched_text": "Fake context",
                           "display_citation": "Fake citation"}, "rerank_score": -0.5}]

    service = HistoryAwareRetrievalService(
        QueryContextualizer(RecordingProvider()), LegacyRetrieverAdapter(fake_legacy),
    )
    result = await service.retrieve(CURRENT, HISTORY, top_k=2)
    assert calls == [(STANDALONE, 2, True)]
    assert result.chunks[0].citation == "Fake citation"
    assert result.chunks[0].score == -0.5


@pytest.mark.asyncio
@pytest.mark.parametrize("history", [[], HISTORY])
async def test_standalone_query_is_contextualized_only_when_history_exists(history):
    query = "Người đi bộ vào đường cao tốc bị phạt bao nhiêu?"
    provider, retriever = RecordingProvider(query), RecordingRetriever()
    result = await HistoryAwareRetrievalService(
        QueryContextualizer(provider), retriever,
    ).retrieve(query, history)
    assert provider.calls == ([{"current_query": query, "chat_history": history}] if history else [])
    assert retriever.calls == [(query, 5)]
    assert result.standalone_query == query


@pytest.mark.asyncio
async def test_invalid_contextualization_stops_before_retrieval():
    retriever = RecordingRetriever()
    service = HistoryAwareRetrievalService(QueryContextualizer(RecordingProvider(" ")), retriever)
    with pytest.raises(ValidationError):
        await service.retrieve(CURRENT, HISTORY)
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_contextualization_failure_propagates_before_retrieval(monkeypatch):
    provider, retriever = RecordingProvider(), RecordingRetriever()

    async def fail(*args, **kwargs):
        raise RuntimeError("contextualization failed")

    monkeypatch.setattr(provider, "generate_structured", fail)
    with pytest.raises(RuntimeError, match="contextualization failed"):
        await HistoryAwareRetrievalService(QueryContextualizer(provider), retriever).retrieve(CURRENT, HISTORY)
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_retrieval_failure_propagates_without_using_original_query(monkeypatch):
    retriever = RecordingRetriever()
    calls = []

    async def fail(query, top_k):
        calls.append(query)
        raise RuntimeError("retrieval failed")

    monkeypatch.setattr(retriever, "search", fail)
    with pytest.raises(RuntimeError, match="retrieval failed"):
        await HistoryAwareRetrievalService(
            QueryContextualizer(RecordingProvider()), retriever,
        ).retrieve(CURRENT, HISTORY)
    assert calls == [STANDALONE]


@pytest.mark.asyncio
async def test_invalid_top_k_rejected_before_contextualization():
    provider, retriever = RecordingProvider(), RecordingRetriever()
    with pytest.raises(ValueError, match="top_k"):
        await HistoryAwareRetrievalService(QueryContextualizer(provider), retriever).retrieve(CURRENT, HISTORY, top_k=0)
    assert provider.calls == []
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_no_history_is_executable_without_gemini_credentials():
    query = "Người đi bộ vào đường cao tốc bị phạt bao nhiêu?"
    retriever = RecordingRetriever()
    service = HistoryAwareRetrievalService(
        QueryContextualizer(GeminiProvider(None, "test")), retriever,
    )
    result = await service.retrieve(query)
    assert result.standalone_query == query
    assert retriever.calls == [(query, 5)]


@pytest.mark.asyncio
async def test_nonempty_history_requires_contextualization_even_for_explicit_query():
    query = "Người đi bộ vào đường cao tốc bị phạt bao nhiêu?"
    retriever = RecordingRetriever()
    service = HistoryAwareRetrievalService(
        QueryContextualizer(GeminiProvider(None, "test")), retriever,
    )
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await service.retrieve(query, HISTORY)
    assert retriever.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("previous,current,standalone,required", [
    (
        "Xe máy vượt đèn đỏ có bị tước giấy phép lái xe không?",
        "Ô tô vượt đèn đỏ thì sao?",
        "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?",
        ("ô tô", "vượt đèn đỏ", "tước giấy phép lái xe"),
    ),
    (
        "Xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        "Trẻ em thì sao?",
        "Trẻ em đi xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        ("trẻ em", "xe máy", "không đội mũ bảo hiểm", "phạt"),
    ),
    (
        "Xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        "Người ngồi sau thì sao?",
        "Người ngồi sau xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        ("người ngồi sau", "xe máy", "không đội mũ bảo hiểm", "phạt"),
    ),
    (
        "Người lớn ngồi sau xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        "Xe máy không đội mũ bảo hiểm, trẻ em thì sao?",
        "Trẻ em ngồi sau xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        ("trẻ em", "ngồi sau", "xe máy", "không đội mũ bảo hiểm", "phạt"),
    ),
    (
        "Người điều khiển xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        "Xe máy không đội mũ bảo hiểm, người ngồi sau thì sao?",
        "Người ngồi sau xe máy không đội mũ bảo hiểm bị phạt thế nào?",
        ("người ngồi sau", "xe máy", "không đội mũ bảo hiểm", "phạt"),
    ),
], ids=["license-suspension", "children", "passenger", "explicit-children", "explicit-passenger"])
async def test_follow_up_regressions_preserve_context_before_retrieval(previous, current, standalone, required):
    history = [{"role": "user", "content": previous}]
    provider, retriever = RecordingProvider(standalone), RecordingRetriever()
    result = await HistoryAwareRetrievalService(
        QueryContextualizer(provider), retriever,
    ).retrieve(current, history, top_k=3)
    assert provider.calls == [{"current_query": current, "chat_history": history}]
    assert retriever.calls == [(result.standalone_query, 3)]
    assert result.standalone_query != current
    assert all(term in result.standalone_query.casefold() for term in required)
    assert result.original_query == current
