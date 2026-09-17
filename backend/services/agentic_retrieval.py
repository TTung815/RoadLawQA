"""Bounded retrieve/grade/rewrite orchestration with an inspectable attempt trace."""

from typing import List, Mapping, Optional, Sequence

from pydantic import BaseModel, Field
import time

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter
from ai.agent.state import AgentState
from ai.retrieval.base import Retriever
from ai.retrieval.neighborhood import LegalNeighborhoodExpander, LegalScope
from backend.services.retrieval import HistoryAwareRetrievalService, RetrievalResult


class RetrievalAttempt(BaseModel):
    attempt: int
    query: str
    grade: EvidenceGrade
    chunk_ids: List[str]
    citations: List[str]
    evidence_chunk_ids: List[str]


class StructuralExpansionTrace(BaseModel):
    after_attempt: int
    triggered: bool
    reason: str
    missing_aspects: List[str]
    scopes: List[LegalScope]
    chunk_ids: List[str]
    citations: List[str]
    evidence_chunk_ids: List[str]
    grade_before: EvidenceGrade
    grade_after: EvidenceGrade
    lookup_ms: float
    regrade_ms: float
    added_characters: int


class AgenticRetrievalResult(RetrievalResult):
    retrieval_queries: List[str]
    retrieval_attempts: int
    rewritten_query: Optional[str]
    grade: EvidenceGrade
    selected_attempt: int
    attempts: List[RetrievalAttempt]
    structural_expansion_enabled: bool = False
    structural_expansions: List[StructuralExpansionTrace] = Field(default_factory=list)


class AgenticRetrievalService(HistoryAwareRetrievalService):
    """Grade and return deduplicated evidence accumulated over bounded retrievals.

    selected_attempt identifies the accumulated snapshot used for the final grade,
    not an exclusive source of chunks. Empty/duplicate retries reuse that snapshot.
    All provider and retriever failures propagate; retry only follows a weak grade.
    """

    def __init__(
        self, contextualizer: QueryContextualizer, retriever: Retriever,
        grader: EvidenceGrader, rewriter: QueryRewriter, max_attempts: int = 2,
        structural_expander: Optional[LegalNeighborhoodExpander] = None,
    ):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
            raise ValueError("max_attempts must be 1 or 2")
        super().__init__(contextualizer, retriever)
        self._grader = grader
        self._rewriter = rewriter
        self._max_attempts = max_attempts
        self._structural_expander = structural_expander

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
        expansions: List[StructuralExpansionTrace] = []
        expansion_used = False

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

            if not grade.sufficient and self._structural_expander is not None and not expansion_used:
                coverage = {item.aspect: item.covered for item in grade.coverage}
                reliable = coverage.get("subject_violation", False) and all(
                    coverage.get(aspect, True) for aspect in ("threshold_range", "condition_exception")
                )
                anchor_ids = set(grade.anchor_chunk_ids) if reliable else set()
                anchors = [chunk for chunk in evidence if chunk.id in anchor_ids]
                selection = await self._structural_expander.expand(anchors, grade.missing_aspects, evidence)
                expansion_used = selection.triggered
                before = grade
                for chunk in selection.chunks:
                    evidence_by_id.setdefault(chunk.id, chunk)
                state["retrieved_chunks"] = list(evidence_by_id.values())
                regrade_ms = 0.0
                if selection.chunks:
                    started = time.perf_counter()
                    grade = await self._grader.grade(standalone, state["retrieved_chunks"])
                    regrade_ms = round((time.perf_counter() - started) * 1000, 2)
                    selected_grade, selected_attempt = grade, number
                    state["evidence_sufficient"] = grade.sufficient
                    state["evidence_reason"] = grade.reason
                expansions.append(StructuralExpansionTrace(
                    after_attempt=number, triggered=selection.triggered, reason=selection.reason,
                    missing_aspects=selection.missing_aspects, scopes=selection.scopes,
                    chunk_ids=[chunk.id for chunk in selection.chunks],
                    citations=[chunk.citation for chunk in selection.chunks],
                    evidence_chunk_ids=list(evidence_by_id), grade_before=before, grade_after=grade,
                    lookup_ms=selection.lookup_ms, regrade_ms=regrade_ms,
                    added_characters=selection.added_characters,
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
            structural_expansion_enabled=self._structural_expander is not None,
            structural_expansions=expansions,
        )
