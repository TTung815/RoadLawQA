"""History-aware retrieval orchestration, independent of concrete providers."""

from typing import List, Mapping, Sequence

from pydantic import BaseModel

from ai.agent.contextualizer import QueryContextualizer
from ai.retrieval.base import RetrievedChunk, Retriever


class RetrievalResult(BaseModel):
    original_query: str
    standalone_query: str
    chunks: List[RetrievedChunk]


class HistoryAwareRetrievalService:
    def __init__(self, contextualizer: QueryContextualizer, retriever: Retriever):
        self._contextualizer = contextualizer
        self._retriever = retriever

    async def retrieve(
        self, current_query: str, chat_history: Sequence[Mapping[str, str]] = (),
        top_k: int = 5,
    ) -> RetrievalResult:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query = await self._contextualizer.contextualize(current_query, chat_history)
        chunks = await self._retriever.search(query.standalone_query, top_k=top_k)
        return RetrievalResult(
            original_query=current_query, standalone_query=query.standalone_query,
            chunks=chunks,
        )
