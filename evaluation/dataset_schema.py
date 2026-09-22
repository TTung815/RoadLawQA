"""Versioned evaluation labels; independent of serving contracts and models."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
FAILURE_CATEGORIES = (
    "retrieval_miss", "evidence_incomplete", "grade_false_sufficient",
    "grade_false_insufficient", "rewrite_no_recovery", "rewrite_drift",
    "expansion_irrelevant", "expansion_missed_consequence", "accumulation_loss",
    "answer_incorrect", "answer_incomplete", "citation_invalid",
    "citation_unsupported", "verification_false_accept", "verification_false_reject",
    "unsafe_publication", "unnecessary_abstention", "expected_abstention",
    "provider_or_pipeline_error", "dataset_issue",
)


class LabelModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRow(LabelModel):
    file: Text
    sha256: SHA256
    csv_record: int = Field(ge=2)
    historical_id: Text
    raw_fields: dict[str, str]


class Message(LabelModel):
    role: Literal["user", "assistant"]
    content: Text


class EvidenceReference(LabelModel):
    processed_id: Text
    runtime_id: Text
    uuid: Text
    citation: Text
    law: Text
    article: Text
    clause: str | None
    point: str | None
    text_sha256: SHA256
    role: Literal["support", "context", "contradicts_legacy"] = "support"


class EvidenceGroup(LabelModel):
    id: Text
    description: Text
    # any = interchangeable support; all = jointly necessary leaves.
    match: Literal["all", "any"] = "all"
    references: list[EvidenceReference] = Field(min_length=1)


class AnswerFacet(LabelModel):
    id: Text
    kind: Literal["rule", "definition", "money", "license_points", "additional_sanction",
                  "condition", "exception", "reasoning", "temporal", "uncertainty"]
    description: Text
    required: bool = True
    support_state: Literal["positive_support", "negative_support", "unknown"] = "unknown"
    evidence_group_ids: list[Text] = Field(default_factory=list)


class Review(LabelModel):
    status: Literal["needs_review", "approved", "excluded"] = "needs_review"
    reviewer: Text | None = None
    reviewed_on: date | None = None
    notes: list[Text] = Field(default_factory=list)


class HistoricalRun(LabelModel):
    """Observed legacy run data; never treated as gold or rerun measurement."""
    model_answer: Text | None = None
    model_citations_raw: str | None = None
    retriever_sources_raw: str | None = None
    legal_accuracy: float | None = Field(default=None, ge=0, le=1)
    legal_citation: float | None = Field(default=None, ge=0, le=1)
    relevance: float | None = Field(default=None, ge=0, le=1)
    total_score: float | None = Field(default=None, ge=0, le=1)


class PublicationExpectation(LabelModel):
    disposition: Literal["unassigned", "publish", "abstain", "conditional"] = "unassigned"
    # Empty while unresolved: never infer success or a specific service path.
    allowed_statuses: list[Literal["answered", "insufficient_evidence", "verification_failed"]] = Field(default_factory=list)
    rationale: Text


class TechnicalAudit(LabelModel):
    status: Literal["pass", "needs_revision", "conditional", "external_source_needed"]
    citation_status: Literal["supported", "partially_supported", "unsupported", "external_source_needed"]
    audited_on: date
    scope: Text
    recommended_answer: Text
    recommended_coverage: Literal["sufficient", "insufficient", "conditional"]
    recommended_publication: PublicationExpectation
    findings: list[Text] = Field(default_factory=list)
    external_sources: list[Text] = Field(default_factory=list)


class GoldLabels(LabelModel):
    review: Review = Field(default_factory=Review)
    reference_answer: Text | None = None
    temporal_basis: Literal["unresolved", "frozen_corpus", "explicit_date"] = "unresolved"
    as_of_date: date | None = None
    evidence_groups: list[EvidenceGroup] = Field(default_factory=list)
    required_facets: list[AnswerFacet] = Field(default_factory=list)
    expected_coverage: Literal["unassigned", "sufficient", "insufficient", "conditional"] = "unassigned"
    publication: PublicationExpectation
    external_evidence_needed: list[Text] = Field(default_factory=list)
    failure_categories: list[Text] = Field(default_factory=list)
    technical_audit: TechnicalAudit | None = None

    @model_validator(mode="after")
    def label_consistency(self):
        groups = [group.id for group in self.evidence_groups]
        facets = [facet.id for facet in self.required_facets]
        if len(groups) != len(set(groups)) or len(facets) != len(set(facets)):
            raise ValueError("Gold group/facet IDs must be unique")
        for group in self.evidence_groups:
            ids = [ref.runtime_id for ref in group.references]
            if len(ids) != len(set(ids)):
                raise ValueError("Evidence references must be distinct within a group")
        for facet in self.required_facets:
            if len(facet.evidence_group_ids) != len(set(facet.evidence_group_ids)):
                raise ValueError("Duplicate facet group reference")
            if not set(facet.evidence_group_ids) <= set(groups):
                raise ValueError("Facet references an unknown evidence group")
        if not set(self.failure_categories) <= set(FAILURE_CATEGORIES):
            raise ValueError("Unknown failure category")
        statuses = self.publication.allowed_statuses
        if len(statuses) != len(set(statuses)):
            raise ValueError("Duplicate publication status")
        disposition = self.publication.disposition
        if disposition == "unassigned" and statuses:
            raise ValueError("Unassigned publication cannot prescribe statuses")
        if disposition == "publish" and statuses != ["answered"]:
            raise ValueError("Publication requires answered status")
        if disposition == "abstain" and (not statuses or "answered" in statuses):
            raise ValueError("Abstention must prescribe a non-publication status")
        if disposition == "conditional" and not statuses:
            raise ValueError("Conditional publication requires explicit allowed statuses")
        if self.temporal_basis == "explicit_date" and self.as_of_date is None:
            raise ValueError("Explicit temporal basis needs a date")
        if self.temporal_basis != "explicit_date" and self.as_of_date is not None:
            raise ValueError("Date requires explicit temporal basis")
        if self.review.status == "approved":
            if not self.review.reviewer or not self.review.reviewed_on:
                raise ValueError("Approval needs a reviewer and review date")
            if self.temporal_basis == "unresolved" or disposition == "unassigned" or self.expected_coverage == "unassigned":
                raise ValueError("Approved gold cannot retain unresolved expectations")
            if not self.required_facets:
                raise ValueError("Approved gold needs required facets")
            if "answered" in statuses:
                if not self.reference_answer or self.external_evidence_needed:
                    raise ValueError("Publishable gold needs a reference answer and complete corpus support")
                for facet in self.required_facets:
                    if facet.required and (facet.support_state != "positive_support" or not facet.evidence_group_ids):
                        raise ValueError("Baseline publication requires positive supported facets")
                    if facet.required and not any(
                        all(ref.role == "support" for ref in group.references)
                        for group in self.evidence_groups if group.id in facet.evidence_group_ids
                    ):
                        raise ValueError("Context/contradiction references cannot establish a publishable facet")
        if self.review.status == "excluded" and not self.review.notes:
            raise ValueError("Exclusion requires a documented reason")
        return self


class EvaluationCase(LabelModel):
    schema_version: Literal[1] = 1
    id: Text
    split: Literal["legacy", "regression", "held_out"]
    exposure: Literal["historically_used", "known_regression", "unseen", "unknown"]
    query_type: Literal["factual", "penalty", "scenario"]
    query: Text
    chat_history: list[Message] = Field(default_factory=list)
    source: SourceRow
    legacy_answer: Text
    legacy_gold_citations_raw: str | None = None
    legacy_gold_citations: list[Text] = Field(default_factory=list)
    historical_run: HistoricalRun | None = None
    gold: GoldLabels
    audit_flags: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def split_consistency(self):
        if self.split == "held_out" and self.exposure != "unseen":
            raise ValueError("Held-out cases must be unseen")
        if self.exposure == "historically_used" and self.split != "legacy":
            raise ValueError("Historical cases remain in the legacy split")
        if self.exposure == "known_regression" and self.split != "regression":
            raise ValueError("Known regressions belong to the regression split")
        return self


def require_scoring_gold(cases: list[EvaluationCase]) -> None:
    """Fail closed until a selected scoring subset is approved, with unique IDs."""
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Scoring needs a nonempty subset with unique case IDs")
    pending = [case.id for case in cases if case.gold.review.status != "approved"]
    if pending:
        raise ValueError(f"Gold is not approved: {', '.join(pending)}")
