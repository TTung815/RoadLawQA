"""Bounded retrieve/grade/rewrite orchestration with an inspectable attempt trace."""

from typing import List, Mapping, Optional, Sequence

from pydantic import BaseModel

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter
from ai.agent.state import AgentState
from ai.retrieval.base import Retriever
from backend.services.retrieval import HistoryAwareRetrievalService, RetrievalResult


class RetrievalAttempt(BaseModel):
    attempt: int
    query: str
    grade: EvidenceGrade
    chunk_ids: List[str]
    citations: List[str]
    evidence_chunk_ids: List[str]


class AgenticRetrievalResult(RetrievalResult):
    retrieval_queries: List[str]
    retrieval_attempts: int
    rewritten_query: Optional[str]
    grade: EvidenceGrade
    selected_attempt: int
    attempts: List[RetrievalAttempt]


class AgenticRetrievalService(HistoryAwareRetrievalService):
    """Grade and return deduplicated evidence accumulated over bounded retrievals.

    selected_attempt identifies the accumulated snapshot used for the final grade,
    not an exclusive source of chunks. Empty/duplicate retries reuse that snapshot.
    All provider and retriever failures propagate; retry only follows a weak grade.
    """

    def __init__(
        self, contextualizer: QueryContextualizer, retriever: Retriever,
        grader: EvidenceGrader, rewriter: QueryRewriter, max_attempts: int = 2,
    ):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
            raise ValueError("max_attempts must be 1 or 2")
        super().__init__(contextualizer, retriever)
        self._grader = grader
        self._rewriter = rewriter
        self._max_attempts = max_attempts

    async def retrieve(
        self, current_query: str, chat_history: Sequence[Mapping[str, str]] = (),
        top_k: int = 5,
    ) -> AgenticRetrievalResult:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        contextualized = await self._contextualizer.contextualize(current_query, chat_history)
        standalone = contextualized.standalone_query
        state: AgentState = {
            "user_query": current_query,
            "chat_history": [dict(turn) for turn in chat_history],
            "standalone_query": standalone,
            "retrieved_chunks": [],
            "retrieval_attempts": 0,
            "retrieval_queries": [],
            "rewritten_query": None,
        }
        attempts: List[RetrievalAttempt] = []
        selected_grade: Optional[EvidenceGrade] = None
        selected_attempt = 0
        query = standalone

        for number in range(1, self._max_attempts + 1):
            chunks = await self._retriever.search(query, top_k=top_k)
            # Preserve first occurrence and order; never compare cross-query scores.
            evidence_by_id = {chunk.id: chunk for chunk in state["retrieved_chunks"]}
            previous_size = len(evidence_by_id)
            for chunk in chunks:
                evidence_by_id.setdefault(chunk.id, chunk)
            evidence = list(evidence_by_id.values())
            # Always grade the combined context against the original legal need.
            # No new evidence means no new basis for a different LLM judgment.
            if selected_grade is None or len(evidence) > previous_size:
                selected_grade = await self._grader.grade(standalone, evidence)
                selected_attempt = number
            elif not evidence:
                selected_attempt = number
            grade = selected_grade
            state["retrieved_chunks"] = evidence
            state["evidence_sufficient"] = grade.sufficient
            state["evidence_reason"] = grade.reason
            state["retrieval_attempts"] = number
            state["retrieval_queries"].append(query)
            attempts.append(RetrievalAttempt(
                attempt=number, query=query, grade=grade,
                chunk_ids=[chunk.id for chunk in chunks],
                citations=[chunk.citation for chunk in chunks],
                evidence_chunk_ids=[chunk.id for chunk in evidence],
            ))

            if grade.sufficient:
                break
            if number < self._max_attempts:
                rewritten = await self._rewriter.rewrite(standalone, query, grade)
                query = rewritten.rewritten_query
                state["rewritten_query"] = query

        # The validated positive attempt bound guarantees a selected grade.
        assert selected_grade is not None
        return AgenticRetrievalResult(
            original_query=state["user_query"], standalone_query=standalone,
            chunks=state["retrieved_chunks"],
            retrieval_queries=state["retrieval_queries"],
            retrieval_attempts=state["retrieval_attempts"],
            rewritten_query=state["rewritten_query"], grade=selected_grade,
            selected_attempt=selected_attempt, attempts=attempts,
        )
