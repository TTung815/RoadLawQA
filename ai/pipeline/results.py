"""Pipeline outputs: retrieval traces and answers; only verified claims are published."""

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

from ai.agent.citation_verifier import CitationVerification
from ai.agent.support import SupportState
from ai.retrieval.base import RetrievedChunk
from ai.retrieval.neighborhood import LegalScope


class RetrievalResult(BaseModel):
    original_query: str
    standalone_query: str
    chunks: List[RetrievedChunk]


class StructuralExpansionTrace(BaseModel):
    triggered: bool
    reason: str
    scopes: List[LegalScope]
    chunk_ids: List[str]
    citations: List[str]
    lookup_ms: float
    added_characters: int


class RetrievalTimings(BaseModel):
    contextualization_ms: float = 0.0
    retrieval_ms: float = 0.0
    structural_lookup_ms: float = 0.0
    total_ms: float = 0.0


class EvidenceRetrievalResult(RetrievalResult):
    retrieval_queries: List[str]
    retrieval_query: str | None = None
    # Reranked top-k before reference lookup; chunks adds the looked-up sources.
    ranked_chunk_ids: List[str] = Field(default_factory=list)
    structural_expansion: StructuralExpansionTrace | None = None
    timings: RetrievalTimings = Field(default_factory=RetrievalTimings)


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
    routing_ms: float = 0.0
    generation_ms: float = 0.0
    verification_ms: float = 0.0
    total_ms: float = 0.0


class AnswerResult(BaseModel):
    status: Literal["conversational", "out_of_scope", "answered", "partial_answer", "needs_clarification", "insufficient_evidence", "verification_failed"]
    message: str
    retrieval: EvidenceRetrievalResult | None
    evidence_citations: list[EvidenceCitation]
    answer: GroundedAnswer | None = None
    limitations: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    verification: CitationVerification
    repair_attempts: Literal[0, 1] = 0
    timings: AnswerTimings = Field(default_factory=AnswerTimings)

    @model_validator(mode="after")
    def validate_conversational_result(self) -> "AnswerResult":
        if self.status in {"conversational", "out_of_scope"}:
            if (self.retrieval is not None or self.answer is not None
                    or self.evidence_citations or self.verification.status != "not_run"):
                raise ValueError("Conversational replies must not claim legal evidence or verification")
        elif self.retrieval is None:
            raise ValueError("Legal QA results require retrieval diagnostics")
        return self
