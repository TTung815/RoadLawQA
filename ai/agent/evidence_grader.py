"""Grade whether supplied chunks support the original legal information need."""

import json
from typing import Annotated, List, Literal, Sequence

from pydantic import BaseModel, StrictBool, StringConstraints, model_validator

from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.evidence_grading import EVIDENCE_GRADING_PROMPT
from ai.retrieval.base import RetrievedChunk


class AspectCoverage(BaseModel):
    """Coverage of an aspect required by this question, not a legal answer."""

    aspect: Literal[
        "monetary_penalty", "license_points", "additional_sanction",
        "subject_violation", "threshold_range", "condition_exception",
    ]
    covered: StrictBool


class EvidenceGrade(BaseModel):
    sufficient: StrictBool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    coverage: List[AspectCoverage]

    @model_validator(mode="after")
    def check_coverage(self):
        aspects = [item.aspect for item in self.coverage]
        if len(aspects) != len(set(aspects)):
            raise ValueError("Coverage aspects must be unique")
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
        result = await self._llm_provider.generate_structured(
            [
                LLMMessage(role="system", content=EVIDENCE_GRADING_PROMPT),
                LLMMessage(role="user", content=json.dumps(
                    {"question": question, "chunks": evidence}, ensure_ascii=False,
                )),
            ],
            response_schema=EvidenceGrade, temperature=0.0,
        )
        return EvidenceGrade.model_validate(result)
