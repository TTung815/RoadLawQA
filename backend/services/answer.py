"""Compose verified retrieval, grounded generation and fail-safe verification."""

import time
from typing import Mapping, Sequence

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerification, CitationVerifier
from ai.agent.support import publishable_support
from backend.schemas.answer import (
    AnswerResult, AnswerTimings, EvidenceCitation, GroundedAnswer, VerifiedClaim,
)
from backend.services.agentic_retrieval import AgenticRetrievalService


class AnswerService:
    def __init__(
        self, retrieval: AgenticRetrievalService, generator: AnswerGenerator,
        verifier: CitationVerifier,
    ):
        self._retrieval = retrieval
        self._generator = generator
        self._verifier = verifier

    async def answer(
        self, current_query: str, chat_history: Sequence[Mapping[str, str]] = (),
        top_k: int = 5,
    ) -> AnswerResult:
        started = time.perf_counter()
        timings = AnswerTimings()
        retrieval = await self._retrieval.retrieve(current_query, chat_history, top_k=top_k)
        citations = [EvidenceCitation(chunk_id=chunk.id, citation=chunk.citation)
                     for chunk in retrieval.chunks]
        if (not retrieval.grade.sufficient or not retrieval.grade.coverage or
                any(not publishable_support(item.support_state)
                    for item in retrieval.grade.coverage)):
            timings.total_ms = (time.perf_counter() - started) * 1000
            return AnswerResult(
                status="insufficient_evidence",
                message="Chưa truy xuất đủ căn cứ để trả lời an toàn; điều này không có nghĩa chế tài không tồn tại.",
                retrieval=retrieval, evidence_citations=citations,
                verification=CitationVerification(status="not_run"), timings=timings,
            )

        required = [item.aspect for item in retrieval.grade.coverage]
        stage = time.perf_counter()
        draft = await self._generator.generate(
            retrieval.standalone_query, retrieval.chunks, required, retrieval.grade.range_coverage,
        )
        timings.generation_ms = (time.perf_counter() - stage) * 1000
        stage = time.perf_counter()
        verification = await self._verifier.verify(
            retrieval.standalone_query, draft, retrieval.chunks, required, retrieval.grade.range_coverage,
        )
        timings.verification_ms = (time.perf_counter() - stage) * 1000
        answer = None
        if verification.status == "passed":
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
        return AnswerResult(
            status="answered" if answer else "verification_failed",
            message="Đáp án đã được kiểm chứng với các căn cứ được dẫn." if answer else
                    "Không thể công bố đáp án vì kiểm chứng căn cứ/nội dung chưa đạt.",
            retrieval=retrieval, evidence_citations=citations, answer=answer,
            verification=verification, timings=timings,
        )
