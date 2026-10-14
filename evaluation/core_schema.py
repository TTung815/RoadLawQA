"""Small evaluation contracts; question inputs never contain reference answers."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from evaluation.dataset_schema import LabelModel, Message, SHA256, Text


Suite = Literal["legacy", "development", "held_out"]
Mode = Literal["end_to_end", "fixed_evidence", "rewrite_probe", "publication_guard_probe"]


class Question(LabelModel):
    id: Text
    current_query: Text
    chat_history: list[Message] = Field(default_factory=list)
    mode: Mode = "end_to_end"
    evidence_batches: list[list[Text]] = Field(default_factory=list)

    @model_validator(mode="after")
    def pool_contract(self):
        replay = self.mode in {"fixed_evidence", "publication_guard_probe"}
        if replay != bool(self.evidence_batches) or any(not batch for batch in self.evidence_batches):
            raise ValueError("only replay modes prescribe nonempty evidence batches")
        if any(len(batch) != len(set(batch)) for batch in self.evidence_batches):
            raise ValueError("duplicate batch source")
        return self


class RunSettings(LabelModel):
    retrieval_backend: Literal["frozen", "structured"] = "frozen"
    hybrid_alpha: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    # Historical receipts omitted these fields; new plans set serving values.
    hybrid_candidate_limit: int = Field(default=20, ge=20, le=40)
    compound_candidate_limit: int = Field(default=20, ge=20, le=40)
    reranker_batch_size: int = Field(default=32, ge=1, le=32)
    # Lock concrete devices; historical receipts were CPU-only.
    embedding_device: Literal["cpu", "mps", "cuda"] = "cpu"
    reranker_device: Literal["cpu", "mps", "cuda"] = "cpu"
    retrieval_corpus_sha256: SHA256 | None = None
    retrieval_index_sha256: SHA256 | None = None
    provider: Literal["gemini", "openai"] = "gemini"
    model: Text
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    request_timeout_seconds: float = Field(default=90.0, gt=0, allow_inf_nan=False)
    max_transient_retries: int = Field(default=2, ge=0, le=5)
    embedding_revision: Text
    reranker_revision: Text
    # Preserve omitted values in historical plans; new plans lock the serving default.
    top_k: int = Field(default=5, ge=1, le=20)
    max_attempts: int = Field(default=2, ge=1, le=2)
    expansion: StrictBool = True
    timeout_seconds: float = Field(default=180, gt=0, allow_inf_nan=False)
    host: Text = "localhost"
    port: int = Field(default=8080, ge=1, le=65535)
    grpc_port: int = Field(default=50051, ge=1, le=65535)
    # No guessed vendor pricing. Explicit prices are recorded in the run lock.
    input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def provider_options(self):
        if self.compound_candidate_limit < self.hybrid_candidate_limit:
            raise ValueError("compound_candidate_limit must be >= hybrid_candidate_limit")
        if self.provider == "openai" and (self.reasoning_effort is None or self.max_output_tokens is None):
            raise ValueError("OpenAI plans must explicitly lock reasoning effort and output token limit")
        if self.provider == "gemini" and (self.reasoning_effort is not None or self.max_output_tokens is not None):
            raise ValueError("OpenAI options cannot be applied to Gemini plans")
        return self


class RunPlan(LabelModel):
    format_version: Literal[1, 2] = 2
    suite: Suite
    dataset_version: Text
    snapshot_id: Literal["roadlawqa-current-law-2026-09-22"] = "roadlawqa-current-law-2026-09-22"
    legal_as_of: Literal["2026-09-22"] = "2026-09-22"
    dataset_binding: SHA256
    snapshot_sha256: SHA256
    code_hashes: dict[str, SHA256]
    settings: RunSettings
    questions: list[Question] = Field(min_length=1)
    owner_reviewed: Literal[True] = True

    @model_validator(mode="after")
    def unique_questions(self):
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate question ID")
        if self.suite != "development" and any(q.mode != "end_to_end" for q in self.questions):
            raise ValueError("legacy/held-out report end-to-end only")
        return self


class SemanticReview(LabelModel):
    id: Text
    result_sha256: SHA256
    reviewer: Text
    facet_scores: dict[str, Literal[0, 0.5, 1]]
    citation_support: StrictBool | None = None
    safe_publication: StrictBool | None = None
    refusal_appropriate: StrictBool | None = None
    rewrite_preserved: StrictBool | None = None
    notes: Text


class SimpleGold(LabelModel):
    """Minimal private held-out gold for manual scoring; not a serving contract."""
    id: Text
    reference_answer: Text
    disposition: Literal["publish", "conditional", "abstain"]
    required_facets: dict[str, Text] = Field(min_length=1)
    expected_citations: list[Text] = Field(default_factory=list)


def unique_records(records):
    if len({r.id for r in records}) != len(records):
        raise ValueError("duplicate record IDs")
    return {r.id: r for r in records}
