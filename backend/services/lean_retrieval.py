"""One hybrid search plus bounded source lookup; no LLM coverage/rewrite loop."""

import time
from typing import Mapping, Sequence

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence import publishable_chunk
from ai.diagnostics import traced
from ai.retrieval.base import Retriever
from ai.retrieval.query_expansion import checked_expansion
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from backend.services.agentic_retrieval import (
    AgenticRetrievalResult, RetrievalAttempt, RetrievalTimings, StructuralExpansionTrace,
)
from backend.services.retrieval import HistoryAwareRetrievalService


class LeanRetrievalService(HistoryAwareRetrievalService):
    def __init__(self, contextualizer: QueryContextualizer, retriever: Retriever,
                 structural_expander: LegalNeighborhoodExpander | None = None):
        super().__init__(contextualizer, retriever)
        self._structural_expander = structural_expander

    @traced("retrieval")
    async def retrieve(self, current_query: str,
                       chat_history: Sequence[Mapping[str, str]] = (),
                       top_k: int = 10, *, prepared_query: str | None = None,
                       retrieval_query: str | None = None) -> AgenticRetrievalResult:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        total = time.perf_counter()
        timings = RetrievalTimings()
        started = time.perf_counter()
        query = prepared_query
        if query is None:
            query = (await self._contextualizer.contextualize(current_query, chat_history)).standalone_query
        if not query.strip():
            raise ValueError("prepared query must not be empty")
        timings.contextualization_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        expansion, _ = checked_expansion(query, retrieval_query)
        search_options = {"retrieval_query": expansion} if expansion else {}
        found = await self._retriever.search(query, top_k=top_k, **search_options)
        timings.retrieval_ms = (time.perf_counter() - started) * 1000
        evidence = {}
        for chunk in found:
            if publishable_chunk(chunk):
                evidence.setdefault(chunk.id, chunk)
        initial = list(evidence.values())
        expansions = []
        if self._structural_expander is not None and initial:
            selection = await self._structural_expander.expand_references(initial, question=query)
            for chunk in selection.chunks:
                evidence.setdefault(chunk.id, chunk)
            timings.structural_lookup_ms = selection.lookup_ms
            expansions.append(StructuralExpansionTrace(
                after_attempt=1, triggered=selection.triggered, reason=selection.reason,
                missing_aspects=[], scopes=selection.scopes,
                chunk_ids=[c.id for c in selection.chunks],
                citations=[c.citation for c in selection.chunks],
                evidence_chunk_ids=list(evidence), lookup_ms=selection.lookup_ms,
                regrade_ms=0, added_characters=selection.added_characters,
            ))
        timings.total_ms = (time.perf_counter() - total) * 1000
        return AgenticRetrievalResult(
            original_query=current_query, standalone_query=query, chunks=list(evidence.values()),
            retrieval_queries=[query, expansion] if expansion else [query],
            retrieval_query=expansion, retrieval_attempts=1, rewritten_query=None,
            selected_attempt=1, attempts=[RetrievalAttempt(
                attempt=1, query=query, chunk_ids=[c.id for c in initial],
                citations=[c.citation for c in initial], evidence_chunk_ids=[c.id for c in initial],
            )], structural_expansion_enabled=self._structural_expander is not None,
            structural_expansions=expansions, timings=timings,
        )
