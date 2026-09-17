"""Grade whether supplied chunks support the original legal information need."""

import json
from typing import Annotated, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, StrictBool, StringConstraints, model_validator

from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.evidence_grading import EVIDENCE_GRADING_PROMPT
from ai.retrieval.base import RetrievedChunk
from ai.agent.range_coverage import RangeCoverage, range_anchors, range_candidates


class AspectCoverage(BaseModel):
    """Coverage of an aspect required by this question, not a legal answer."""

    aspect: Literal[
        "monetary_penalty", "license_points", "additional_sanction",
        "subject_violation", "threshold_range", "condition_exception",
    ]
    covered: StrictBool
    required: StrictBool = True


class EvidenceGrade(BaseModel):
    range_coverage: Optional[RangeCoverage] = None
    coverage: List[AspectCoverage]
    anchor_chunk_ids: List[str] = Field(default_factory=list)
    sufficient: StrictBool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

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

    async def grade(
        self, question: str, chunks: Sequence[RetrievedChunk],
    ) -> EvidenceGrade:
        if not chunks:
            return EvidenceGrade(
                sufficient=False, reason="No legal chunks were retrieved.", coverage=[],
            )

        evidence = []
        for chunk in chunks:
            item = chunk.model_dump(mode="json", exclude={"score"})
            item["metadata"] = {
                key: value for key, value in item["metadata"].items()
                if key not in ("raw_score", "rerank_score")
            }
            evidence.append(item)
        candidates = range_candidates(question, chunks)
        payload = {"question": question, "chunks": evidence}
        if candidates is not None:
            payload['range_candidates'] = candidates
        result = await self._llm_provider.generate_structured(
            [
                LLMMessage(role="system", content=EVIDENCE_GRADING_PROMPT),
                LLMMessage(role="user", content=json.dumps(
                    payload, ensure_ascii=False,
                )),
            ],
            response_schema=EvidenceGrade, temperature=0.0,
        )
        grade = EvidenceGrade.model_validate(result)
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
            grade.coverage = [AspectCoverage(aspect=aspect, covered=covered)
                              for aspect, covered in values.items()]
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
