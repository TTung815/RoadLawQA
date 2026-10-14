"""Compose verified retrieval, grounded generation and fail-safe verification."""

import time
from typing import Mapping, Sequence

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerification, CitationVerifier
from ai.agent.support import publishable_support
from ai.agent.evidence import publishable_chunk
from ai.diagnostics import record, traced
from backend.schemas.answer import (
    AnswerResult, AnswerTimings, EvidenceCitation, GroundedAnswer, VerifiedClaim,
)
from backend.services.agentic_retrieval import AgenticRetrievalService
from backend.services.lean_retrieval import LeanRetrievalService


class AnswerService:
    def __init__(
        self, retrieval: LeanRetrievalService | AgenticRetrievalService, generator: AnswerGenerator,
        verifier: CitationVerifier, max_answer_attempts: int = 2,
    ):
        if type(max_answer_attempts) is not int or max_answer_attempts not in (1, 2):
            raise ValueError("max_answer_attempts must be 1 or 2")
        self._retrieval = retrieval
        self._generator = generator
        self._verifier = verifier
        self._max_answer_attempts = max_answer_attempts

    @traced("answer")
    async def answer(
        self, current_query: str, chat_history: Sequence[Mapping[str, str]] = (),
        top_k: int = 10, *, prepared_query: str | None = None, retrieval_query: str | None = None,
    ) -> AnswerResult:
        started = time.perf_counter()
        timings = AnswerTimings()
        search_options = {"retrieval_query": retrieval_query} if retrieval_query else {}
        if prepared_query is None and not search_options:
            retrieval = await self._retrieval.retrieve(current_query, chat_history, top_k=top_k)
        else:
            retrieval = await self._retrieval.retrieve(
                current_query, chat_history, top_k=top_k, prepared_query=prepared_query, **search_options,
            )
        record("retrieval", event="result", retrieval=retrieval.model_dump(mode="json"))
        citations = [EvidenceCitation(chunk_id=chunk.id, citation=chunk.citation)
                     for chunk in retrieval.chunks]
        grade = retrieval.grade
        usable = any(item.covered and publishable_support(item.support_state)
                     for item in grade.coverage) if grade is not None else bool(retrieval.chunks)
        # An anchor can identify a relevant rule whose applicability still needs
        # a user fact. Let generation explain the rule conditionally; verification
        # and the incomplete-coverage gate still prevent an unsupported conclusion.
        usable = usable or (grade is not None and any(
            c.id in grade.anchor_chunk_ids and publishable_chunk(c) for c in retrieval.chunks))
        if not usable or not any(publishable_chunk(chunk) for chunk in retrieval.chunks):
            timings.total_ms = (time.perf_counter() - started) * 1000
            return AnswerResult(
                status="insufficient_evidence",
                message="Chưa truy xuất đủ căn cứ để trả lời an toàn; điều này không có nghĩa chế tài không tồn tại.",
                retrieval=retrieval, evidence_citations=citations,
                verification=CitationVerification(status="not_run"), timings=timings,
            )

        required = [item.aspect for item in grade.coverage] if grade is not None else []
        range_proof = grade.range_coverage if grade is not None and grade.sufficient else None
        gaps = grade.missing_aspects if grade is not None else []
        reason = grade.reason if grade is not None and not grade.sufficient else ""
        draft, feedback = None, []
        for attempt in range(1, self._max_answer_attempts + 1):
            stage = time.perf_counter()
            draft = await self._generator.generate(
                retrieval.standalone_query, retrieval.chunks, required,
                range_proof,
                coverage_gaps=gaps,
                coverage_reason=reason,
                previous_draft=draft, verification_feedback=feedback,
            )
            timings.generation_ms += (time.perf_counter() - stage) * 1000
            stage = time.perf_counter()
            verification = await self._verifier.verify(
                retrieval.standalone_query, draft, retrieval.chunks, required,
                range_proof,
                coverage_gaps=gaps,
                coverage_reason=reason,
            )
            if grade is not None and not grade.sufficient and draft.response_kind == "complete":
                verification.status = "failed"
                verification.issues.append("Unresolved retrieval gaps require an explicit partial answer")
            timings.verification_ms += (time.perf_counter() - stage) * 1000
            record("verification", event="result", attempt=attempt,
                   verification=verification.model_dump(mode="json"))
            if verification.status == "passed":
                break
            feedback = verification.issues
        answer = None
        if verification.status == "passed" and draft.response_kind != "abstain":
            by_id = {citation.chunk_id: citation for citation in citations}
            claims = [VerifiedClaim(text=claim.text, support_state=claim.support_state,
                                    citations=[by_id[id_] for id_ in claim.chunk_ids])
                      for claim in draft.claims]
            answer = GroundedAnswer(
                text="\n\n".join(claim.text + "\nCăn cứ pháp lý: " + "; ".join(
                    citation.citation for citation in claim.citations) for claim in claims),
                claims=claims,
            )
        timings.total_ms = (time.perf_counter() - started) * 1000
        status = {"complete": "answered", "partial": "partial_answer",
                  "clarification": "needs_clarification", "abstain": "insufficient_evidence"}[draft.response_kind]
        return AnswerResult(
            status=status if verification.status == "passed" else "verification_failed",
            message=(" ".join(draft.limitations) if status == "insufficient_evidence" else
                     "Đáp án đã được kiểm chứng với các căn cứ được dẫn." if status == "answered"
                     else "Mình cần thêm thông tin để trả lời đúng tình huống." if status == "needs_clarification"
                     else "Đã kiểm chứng phần có căn cứ; xem giới hạn và thông tin cần bổ sung.") if verification.status == "passed" else
                    "Không thể công bố đáp án vì kiểm chứng căn cứ/nội dung chưa đạt.",
            retrieval=retrieval, evidence_citations=citations, answer=answer,
            verification=verification, timings=timings,
            repair_attempts=attempt - 1,
            limitations=draft.limitations if verification.status == "passed" else [],
            follow_up_questions=draft.follow_up_questions if verification.status == "passed" else [],
        )
