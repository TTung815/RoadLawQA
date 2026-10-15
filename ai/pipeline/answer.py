"""Compose verified retrieval, grounded generation and fail-safe verification."""

import time
from typing import Mapping, Sequence

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerification, CitationVerifier
from ai.agent.evidence import publishable_chunk
from ai.diagnostics import record, traced
from ai.pipeline.results import AnswerResult, AnswerTimings, EvidenceCitation, GroundedAnswer, VerifiedClaim
from ai.pipeline.retrieval import LeanRetrievalService


STATUS_BY_KIND = {"complete": "answered", "partial": "partial_answer",
                  "clarification": "needs_clarification", "abstain": "insufficient_evidence"}
STATUS_MESSAGES = {
    "answered": "Đáp án đã được kiểm chứng với các căn cứ được dẫn.",
    "needs_clarification": "Mình cần thêm thông tin để trả lời đúng tình huống.",
    "partial_answer": "Đã kiểm chứng phần có căn cứ; xem giới hạn và thông tin cần bổ sung.",
}
FAILED_MESSAGE = "Không thể công bố đáp án vì kiểm chứng căn cứ/nội dung chưa đạt."
NO_EVIDENCE_MESSAGE = "Chưa truy xuất đủ căn cứ để trả lời an toàn; điều này không có nghĩa chế tài không tồn tại."


class AnswerService:
    def __init__(
        self, retrieval: LeanRetrievalService, generator: AnswerGenerator,
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
        # Plain retrieval services accept only (query, history, top_k).
        if prepared_query is None and not search_options:
            retrieval = await self._retrieval.retrieve(current_query, chat_history, top_k=top_k)
        else:
            retrieval = await self._retrieval.retrieve(
                current_query, chat_history, top_k=top_k, prepared_query=prepared_query, **search_options,
            )
        record("retrieval", event="result", retrieval=retrieval.model_dump(mode="json"))
        citations = [EvidenceCitation(chunk_id=chunk.id, citation=chunk.citation)
                     for chunk in retrieval.chunks]
        if not any(publishable_chunk(chunk) for chunk in retrieval.chunks):
            timings.total_ms = (time.perf_counter() - started) * 1000
            return AnswerResult(
                status="insufficient_evidence",
                message=NO_EVIDENCE_MESSAGE,
                retrieval=retrieval, evidence_citations=citations,
                verification=CitationVerification(status="not_run"), timings=timings,
            )

        draft, verification, attempts = await self._draft_and_verify(retrieval, timings)
        timings.total_ms = (time.perf_counter() - started) * 1000
        if verification.status != "passed":
            return AnswerResult(
                status="verification_failed", message=FAILED_MESSAGE,
                retrieval=retrieval, evidence_citations=citations, verification=verification,
                timings=timings, repair_attempts=attempts - 1,
            )
        status = STATUS_BY_KIND[draft.response_kind]
        return AnswerResult(
            status=status,
            message=" ".join(draft.limitations) if status == "insufficient_evidence" else STATUS_MESSAGES[status],
            retrieval=retrieval, evidence_citations=citations,
            answer=None if draft.response_kind == "abstain" else published_answer(draft, citations),
            verification=verification, timings=timings, repair_attempts=attempts - 1,
            limitations=draft.limitations, follow_up_questions=draft.follow_up_questions,
        )

    async def _draft_and_verify(self, retrieval, timings: AnswerTimings):
        """Generate, verify, and repair at most once on the same evidence."""
        draft, feedback = None, []
        for attempt in range(1, self._max_answer_attempts + 1):
            stage = time.perf_counter()
            draft = await self._generator.generate(
                retrieval.standalone_query, retrieval.chunks,
                previous_draft=draft, verification_feedback=feedback,
            )
            timings.generation_ms += (time.perf_counter() - stage) * 1000
            stage = time.perf_counter()
            verification = await self._verifier.verify(retrieval.standalone_query, draft, retrieval.chunks)
            timings.verification_ms += (time.perf_counter() - stage) * 1000
            record("verification", event="result", attempt=attempt,
                   verification=verification.model_dump(mode="json"))
            if verification.status == "passed":
                break
            feedback = verification.issues
        return draft, verification, attempt


def published_answer(draft, citations: list[EvidenceCitation]) -> GroundedAnswer:
    """Verified claims with their server-rendered legal citations."""
    by_id = {citation.chunk_id: citation for citation in citations}
    claims = [VerifiedClaim(text=claim.text, support_state=claim.support_state,
                            citations=[by_id[id_] for id_ in claim.chunk_ids])
              for claim in draft.claims]
    text = "\n\n".join(claim.text + "\nCăn cứ pháp lý: " + "; ".join(c.citation for c in claim.citations)
                        for claim in claims)
    return GroundedAnswer(text=text, claims=claims)
