# -*- coding: utf-8 -*-
"""
Unit Tests for LegacyRetrieverAdapter (Mocked, No Weaviate, No Model Loading)
"""
import pytest
import threading
from types import ModuleType
import sys
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter


@pytest.mark.asyncio
async def test_legacy_retriever_adapter_mocked_results():
    mock_legacy_output = [
        {
            "props": {
                "id": "test_chunk_1",
                "law": "Nghị định số 168/2024/NĐ-CP",
                "chapter": "Chương II",
                "section": "Mục 1",
                "article_no": "6",
                "article_title": "Xử phạt người điều khiển xe mô tô",
                "clause_no": "4",
                "point": "a",
                "clause_head": "Phạt tiền từ 800.000 đồng đến 1.000.000 đồng",
                "text": "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông",
                "enriched_text": "[CHAPTER] Chương II\n[ARTICLE] Điều 6\nKhông chấp hành hiệu lệnh của đèn tín hiệu giao thông",
                "display_citation": "điểm a khoản 4 Điều 6 Nghị định số 168/2024/NĐ-CP",
            },
            "score": 0.85,
            "rerank_score": 4.12,  # Rerank scores from CrossEncoder can be arbitrary real numbers
        }
    ]

    def dummy_retrieve(query, k=5, raw=True):
        assert query == "vượt đèn đỏ"
        assert k == 5
        assert raw is True
        return mock_legacy_output

    adapter = LegacyRetrieverAdapter(retrieve_fn=dummy_retrieve)
    chunks = await adapter.search("vượt đèn đỏ", top_k=5)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.id == "test_chunk_1"
    assert chunk.citation == "điểm a khoản 4 Điều 6 Nghị định số 168/2024/NĐ-CP"
    assert chunk.score == 4.12  # Rerank score preferred
    assert chunk.text == "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông"
    assert chunk.metadata["article_no"] == "6"
    assert chunk.metadata["law"] == "Nghị định số 168/2024/NĐ-CP"


@pytest.mark.asyncio
async def test_legacy_retriever_adapter_empty_results():
    def empty_retrieve(query, k=5, raw=True):
        return []

    adapter = LegacyRetrieverAdapter(retrieve_fn=empty_retrieve)
    chunks = await adapter.search("câu hỏi không có kết quả", top_k=3)
    assert chunks == []


@pytest.mark.asyncio
async def test_first_use_resolution_and_retrieval_run_in_worker(monkeypatch):
    loop_thread = threading.get_ident()
    calls = []
    fake_legacy = ModuleType("backend.retriever_custom")

    def retrieve(query, k, raw):
        calls.append(("retrieve", threading.get_ident()))
        assert (query, k, raw) == ("query", 3, True)
        return []

    fake_legacy.retrieve = retrieve
    monkeypatch.setitem(sys.modules, "backend.retriever_custom", fake_legacy)
    adapter = LegacyRetrieverAdapter()
    resolve = adapter._resolve_retrieve_fn

    def tracked_resolve():
        calls.append(("resolve", threading.get_ident()))
        return resolve()

    monkeypatch.setattr(adapter, "_resolve_retrieve_fn", tracked_resolve)
    assert adapter._retrieve_fn is None
    assert calls == []
    assert await adapter.search("query", top_k=3) == []
    assert [name for name, _ in calls] == ["resolve", "retrieve"]
    assert all(thread != loop_thread for _, thread in calls)
    assert adapter._retrieve_fn is retrieve


@pytest.mark.asyncio
async def test_fallback_ids_are_stable_across_rank_and_distinguish_content():
    first = {"props": {"law": "Law", "display_citation": "Article 1",
                       "text": "First content", "enriched_text": "Context"}, "score": 1.0}
    second = {"props": {**first["props"], "text": "Different content"}, "score": 0.5}
    forward = await LegacyRetrieverAdapter(lambda *a, **kw: [first, second]).search("q")
    reverse = await LegacyRetrieverAdapter(lambda *a, **kw: [second, first]).search("q")
    assert forward[0].id == reverse[1].id
    assert forward[1].id == reverse[0].id
    assert forward[0].id != forward[1].id


@pytest.mark.asyncio
async def test_integration_implementation_errors_fail(monkeypatch):
    from tests.integration import test_weaviate_retrieval_smoke as smoke

    monkeypatch.setattr(smoke, "is_weaviate_reachable", lambda *a: True)

    async def broken_search(self, *args, **kwargs):
        raise TypeError("Implementation failure")

    monkeypatch.setattr(smoke.LegacyRetrieverAdapter, "search", broken_search)
    with pytest.raises(TypeError, match="Implementation failure"):
        await smoke.test_live_weaviate_retrieval_smoke()


@pytest.mark.asyncio
async def test_integration_missing_prerequisite_skips_without_retrieval(monkeypatch):
    from tests.integration import test_weaviate_retrieval_smoke as smoke

    probes = []

    def reachable(host, port):
        probes.append((host, port))
        return port == 8080

    async def unexpected_search(self, *args, **kwargs):
        pytest.fail("Retrieval must not run without prerequisites")

    monkeypatch.setattr(smoke, "is_weaviate_reachable", reachable)
    monkeypatch.setattr(smoke.LegacyRetrieverAdapter, "search", unexpected_search)
    with pytest.raises(pytest.skip.Exception, match="prerequisite is unavailable"):
        await smoke.test_live_weaviate_retrieval_smoke()
    assert probes == [("localhost", 8080), ("localhost", 50051)]
