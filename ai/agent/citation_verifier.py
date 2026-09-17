"""Deterministic provenance checks followed by claim-level semantic verification."""

import json
import re
from typing import Annotated, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from ai.agent.answer_generator import (
    DraftAnswer, NonEmptyText, evidence_payload, required_range_branches,
)
from ai.agent.range_coverage import RangeCoverage
from ai.agent.support import SupportState, publishable_support
from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.citation_verification import CITATION_VERIFICATION_PROMPT
from ai.retrieval.base import RetrievedChunk


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_index: Annotated[StrictInt, Field(ge=0)]
    supported: StrictBool
    reason: NonEmptyText
    support_state: SupportState = "unknown"


class RangeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_index: Annotated[StrictInt, Field(ge=0)]
    addressed: StrictBool
    reason: NonEmptyText


class VerifiedRangeAssessment(RangeAssessment):
    chunk_id: str


class SemanticVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessments: list[ClaimAssessment]
    answer_complete: StrictBool
    completeness_reason: NonEmptyText
    range_assessments: list[RangeAssessment] = Field(default_factory=list)


class CitationVerification(BaseModel):
    status: Literal["not_run", "passed", "failed"]
    provenance_valid: bool | None = None
    semantic_valid: bool | None = None
    answer_complete: bool | None = None
    issues: list[str] = Field(default_factory=list)
    assessments: list[ClaimAssessment] = Field(default_factory=list)
    range_assessments: list[VerifiedRangeAssessment] = Field(default_factory=list)


# Legal reference strings must come from server-owned citation metadata only.
_INLINE_REFERENCE = re.compile(
    r"\b(?:điều|khoản)\s+\d|\bđiểm\s+[a-zđ]\b|"
    r"\b(?:nghị định|luật)\s+(?:số\s+)?\d", re.IGNORECASE,
)


class CitationVerifier:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def verify(
        self, question: str, draft: DraftAnswer, chunks: Sequence[RetrievedChunk],
        required_aspects: Sequence[str] = (),
        range_coverage: RangeCoverage | None = None,
    ) -> CitationVerification:
        by_id = {chunk.id: chunk for chunk in chunks}
        if len(by_id) != len(chunks):
            raise ValueError("Final evidence must have unique chunk IDs")
        issues = []
        if not draft.claims:
            issues.append("Generator returned no grounded claims")
        for index, claim in enumerate(draft.claims):
            if len(set(claim.chunk_ids)) != len(claim.chunk_ids):
                issues.append(f"Claim {index}: duplicate citation IDs")
            if _INLINE_REFERENCE.search(claim.text):
                issues.append(f"Claim {index}: inline legal references are not permitted")
            for identifier in claim.chunk_ids:
                chunk = by_id.get(identifier)
                if chunk is None:
                    issues.append(f"Claim {index}: citation ID outside final evidence: {identifier}")
                elif not chunk.citation.strip():
                    issues.append(f"Claim {index}: missing citation metadata: {identifier}")
        if issues:
            return CitationVerification(status="failed", provenance_valid=False, issues=issues)

        support_issues = [f"Claim {index}: {claim.support_state} cannot authorize publication"
                          for index, claim in enumerate(draft.claims)
                          if not publishable_support(claim.support_state)]
        if support_issues:
            return CitationVerification(status="failed", provenance_valid=True,
                                        semantic_valid=False, issues=support_issues)

        required_range = required_range_branches(question, chunks, range_coverage)
        required_ids = ({item["chunk_id"] for item in required_range["branches"]}
                        if required_range is not None else set())
        cited_ids = {id_ for claim in draft.claims for id_ in claim.chunk_ids}
        if required_ids - cited_ids:
            return CitationVerification(
                status="failed", provenance_valid=True, answer_complete=False,
                issues=["Missing citations for required range branches: " +
                        ", ".join(sorted(required_ids - cited_ids))],
            )

        result = await self._provider.generate_structured(
            [LLMMessage(role="system", content=CITATION_VERIFICATION_PROMPT),
             LLMMessage(role="user", content=json.dumps({
                 "question": question, "required_aspects": list(required_aspects),
                 "claims": [{"claim_index": index, "text": claim.text,
                             "cited_chunks": evidence_payload([by_id[id_] for id_ in claim.chunk_ids])}
                            for index, claim in enumerate(draft.claims)],
                 "final_evidence": evidence_payload(chunks),
                 "required_range": required_range,
             }, ensure_ascii=False))],
            response_schema=SemanticVerification, temperature=0.0,
        )
        semantic = SemanticVerification.model_validate(result)
        indices = [item.claim_index for item in semantic.assessments]
        if sorted(indices) != list(range(len(draft.claims))):
            return CitationVerification(
                status="failed", provenance_valid=True,
                issues=["Verifier did not assess every claim exactly once"],
            )
        branches = required_range["branches"] if required_range is not None else []
        range_indices = [item.branch_index for item in semantic.range_assessments]
        if sorted(range_indices) != list(range(len(branches))):
            return CitationVerification(
                status="failed", provenance_valid=True,
                issues=["Verifier did not assess every required range branch exactly once"],
            )
        # A semantic 'supported=true' cannot override unknown/negative support.
        for item in semantic.assessments:
            if not publishable_support(item.support_state):
                item.supported = False
                item.support_state = "unknown"
                issues.append(f"Claim {item.claim_index}: no publishable legal support")
        supported = all(item.supported for item in semantic.assessments)
        for item in semantic.assessments:
            if not item.supported:
                issues.append(f"Claim {item.claim_index}: {item.reason}")
        range_complete = all(item.addressed for item in semantic.range_assessments)
        for item in semantic.range_assessments:
            if not item.addressed:
                issues.append(f"Range branch {item.branch_index}: {item.reason}")
        if not semantic.answer_complete:
            issues.append("Incomplete answer: " + semantic.completeness_reason)
        return CitationVerification(
            status="passed" if supported and semantic.answer_complete and range_complete else "failed",
            provenance_valid=True, semantic_valid=supported,
            answer_complete=semantic.answer_complete and range_complete, issues=issues,
            assessments=semantic.assessments,
            range_assessments=[VerifiedRangeAssessment(
                **item.model_dump(), chunk_id=branches[item.branch_index]["chunk_id"],
            ) for item in semantic.range_assessments],
        )
