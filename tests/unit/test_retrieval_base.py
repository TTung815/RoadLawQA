# -*- coding: utf-8 -*-
"""
Unit Tests for Retrieval Base Abstractions
"""
import pytest
from typing import List
from ai.retrieval.base import RetrievedChunk, Retriever


def test_retrieved_chunk_contract():
    chunk = RetrievedChunk(
        id="test_id_123",
        text="Nội dung điều luật",
        enriched_text="[ARTICLE] Điều 10. Nội dung điều luật",
        citation="Khoản 1 Điều 10 Luật số 36/2024/QH15",
        score=0.895,
        metadata={"law": "Luật 36", "article_no": "10"},
    )
    assert chunk.id == "test_id_123"
    assert chunk.text == "Nội dung điều luật"
    assert chunk.enriched_text.startswith("[ARTICLE]")
    assert chunk.citation == "Khoản 1 Điều 10 Luật số 36/2024/QH15"
    assert chunk.score == 0.895
    assert chunk.metadata["article_no"] == "10"


def test_retriever_is_abstract():
    with pytest.raises(TypeError):
        # Cannot instantiate abstract class without implementing search
        Retriever()  # type: ignore


@pytest.mark.asyncio
async def test_dummy_retriever_implementation():
    class DummyRetriever(Retriever):
        async def search(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
            return [
                RetrievedChunk(
                    id="dummy_1",
                    text=f"Result for: {query}",
                    enriched_text=f"[TEST] {query}",
                    citation="Test Citation",
                    score=1.0,
                )
            ]

    retriever = DummyRetriever()
    results = await retriever.search("giao thông", top_k=1)
    assert len(results) == 1
    assert results[0].text == "Result for: giao thông"

