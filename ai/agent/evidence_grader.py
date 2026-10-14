"""Grade whether supplied chunks support the original legal information need."""

import json
from typing import Annotated, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, StrictBool, StrictInt, StringConstraints, model_validator

from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.evidence_grading import EVIDENCE_GRADING_PROMPT
from ai.retrieval.base import RetrievedChunk
from ai.agent.range_coverage import RangeCoverage, range_anchors, range_candidates
from ai.agent.support import SupportState, publishable_support
from ai.agent.evidence import SourceReferences, evidence_payload
from ai.diagnostics import record, traced


class AspectCoverage(BaseModel):
    """Coverage of an aspect required by this question, not a legal answer."""

    aspect: Literal[
        "monetary_penalty", "license_points", "additional_sanction",
        "subject_violation", "threshold_range", "condition_exception",
    ]
    covered: StrictBool
    required: StrictBool = True
    support_state: SupportState = "unknown"

    @model_validator(mode="after")
    def check_support(self):
        if not self.covered or not publishable_support(self.support_state):
            self.covered = False
            self.support_state = "unknown"
        return self


class RangeDecision(BaseModel):
    candidate_index: Annotated[StrictInt, Field(ge=0)]
    compatible: StrictBool


class EvidenceGrade(BaseModel):
    range_coverage: Optional[RangeCoverage] = None
    coverage: List[AspectCoverage]
    anchor_chunk_ids: List[str] = Field(default_factory=list)
    sufficient: StrictBool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    range_decisions: list[RangeDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_coverage(self):
        aspects = [item.aspect for item in self.coverage]
        if len(aspects) != len(set(aspects)):
            raise ValueError("Coverage aspects must be unique")
        # Irrelevant aspects are omitted, as in the original coverage contract.
        # Older providers default to required=True, preserving conservative gates.
        self.coverage = [item for item in self.coverage if item.required]
        if self.sufficient and not self.coverage:
            raise ValueError("Sufficient evidence requires explicit coverage")
        # A provider's optimistic boolean cannot override an identified gap.
        if any(not item.covered for item in self.coverage):
            self.sufficient = False
        return self

    @property
    def missing_aspects(self) -> List[str]:
        return [item.aspect for item in self.coverage if not item.covered]


class EvidenceGrader:
    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    @traced("coverage_grading")
    async def grade(
        self, question: str, chunks: Sequence[RetrievedChunk],
    ) -> EvidenceGrade:
        if not chunks:
            return EvidenceGrade(
                sufficient=False, reason="No legal chunks were retrieved.", coverage=[],
            )

        evidence = evidence_payload(chunks)
        refs = SourceReferences(chunks)
        candidates = range_candidates(question, chunks)
        payload = {"question": question, "chunks": evidence}
        if candidates is not None:
            candidates = {**candidates, "leaves": [dict(item, candidate_index=i)
                          for i, item in enumerate(candidates["leaves"])]}
            payload['range_candidates'] = candidates
        result = await self._llm_provider.generate_structured(
            [
                LLMMessage(role="system", content=EVIDENCE_GRADING_PROMPT),
                LLMMessage(role="user", content=json.dumps(
                    refs.translate(payload), ensure_ascii=False,
                )),
            ],
            response_schema=EvidenceGrade, temperature=0.0,
        )
        grade = EvidenceGrade.model_validate(result)
        grade = EvidenceGrade.model_validate(refs.translate(grade.model_dump(), decode=True))
        record("coverage_grading", event="assessment", grade=grade.model_dump(mode="json"))
        if grade.range_decisions:
            decisions = {item.candidate_index: item.compatible for item in grade.range_decisions}
            if (candidates is None or len(decisions) != len(grade.range_decisions)
                    or set(decisions) != set(range(len(candidates["leaves"])))):
                raise ValueError("Range decisions must assess every supplied candidate exactly once")
            # Quotes, units and IDs originate on the server; the model only judges
            # semantic compatibility. No long-ID or legal-boundary transcription.
            grade.range_coverage = RangeCoverage(
                question_quote=candidates["question_quote"], unit=candidates["unit"],
                leaves=[dict(chunk_id=item["chunk_id"], range_quote=item["range_quote"],
                             compatible=decisions[i]) for i, item in enumerate(candidates["leaves"])],
            )
        known_ids = {chunk.id for chunk in chunks}
        if any(identifier not in known_ids for identifier in grade.anchor_chunk_ids):
            raise ValueError("Grader returned an anchor ID outside supplied evidence")
        if candidates is not None:
            if grade.range_coverage is None:
                raise ValueError('Range proof must assess every supplied range candidate')
            expected = {(item['chunk_id'], ' '.join(item['range_quote'].casefold().split()))
                        for item in candidates['leaves']}
            actual = {(item.chunk_id, ' '.join(item.range_quote.casefold().split()))
                      for item in grade.range_coverage.leaves}
            if actual != expected or len(grade.range_coverage.leaves) != len(expected):
                raise ValueError('Range proof must assess every supplied range candidate without additions')
        if grade.range_coverage is not None:
            anchors = range_anchors(question, chunks, grade.range_coverage)
            values = {item.aspect: item.covered for item in grade.coverage}
            # Numeric support cannot override uncertain semantic applicability.
            proven = bool(anchors) and values.get('subject_violation', False)
            repaired = proven and values.get('threshold_range') is False
            values['threshold_range'] = proven
            grade = grade.model_copy(deep=True)
            states = {item.aspect: item.support_state for item in grade.coverage}
            grade.coverage = [AspectCoverage(
                aspect=aspect, covered=covered,
                support_state=("positive_support" if aspect == "threshold_range" and proven
                               else states.get(aspect, "unknown")),
            ) for aspect, covered in values.items()]
            grade.anchor_chunk_ids = anchors if proven else []
            grade.sufficient = (grade.sufficient or repaired) and all(values.values())
            if repaired or not proven:
                missing = [aspect for aspect, covered in values.items() if not covered]
                grade.reason = (
                    'Compatible evidence jointly covers the requested range.' if proven
                    else 'No grounded compatible anchor set covers the complete requested range.'
                ) + (' Unresolved coverage: ' + ', '.join(missing) + '.' if missing else '')
            grade = EvidenceGrade.model_validate(grade.model_dump())
        return grade
