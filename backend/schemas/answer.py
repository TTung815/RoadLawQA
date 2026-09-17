"""Observable QA results; only verified claims are published as an answer."""

from typing import Literal

from pydantic import BaseModel, Field

from ai.agent.citation_verifier import CitationVerification
from ai.agent.support import SupportState
from backend.services.agentic_retrieval import AgenticRetrievalResult


class EvidenceCitation(BaseModel):
    chunk_id: str
    citation: str


class VerifiedClaim(BaseModel):
    text: str
    support_state: SupportState
    citations: list[EvidenceCitation]


class GroundedAnswer(BaseModel):
    text: str
    claims: list[VerifiedClaim]


class AnswerTimings(BaseModel):
    generation_ms: float = 0.0
    verification_ms: float = 0.0
    total_ms: float = 0.0


class AnswerResult(BaseModel):
    status: Literal["answered", "insufficient_evidence", "verification_failed"]
    message: str
    retrieval: AgenticRetrievalResult
    evidence_citations: list[EvidenceCitation]
    answer: GroundedAnswer | None = None
    verification: CitationVerification
    repair_attempts: Literal[0] = 0
    timings: AnswerTimings = Field(default_factory=AnswerTimings)
