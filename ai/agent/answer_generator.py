"""Generate cited claims through the provider-neutral LLM contract."""

import json
from typing import Annotated, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.answer_generation import ANSWER_GENERATION_PROMPT
from ai.retrieval.base import RetrievedChunk
from ai.agent.range_coverage import RangeCoverage, range_anchors, range_candidates
from ai.agent.support import SupportState
from ai.agent.evidence import SourceReferences, evidence_payload
from ai.diagnostics import record, traced

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnswerClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: NonEmptyText
    chunk_ids: list[NonEmptyText] = Field(min_length=1)
    support_state: SupportState = "unknown"


class DraftAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[AnswerClaim]
    response_kind: Literal["complete", "partial", "clarification", "abstain"] = "complete"
    limitations: list[NonEmptyText] = Field(default_factory=list)
    follow_up_questions: list[NonEmptyText] = Field(default_factory=list)


def required_range_branches(
    question: str, chunks: Sequence[RetrievedChunk], proof: RangeCoverage | None,
) -> dict | None:
    """Carry the retrieval's proven boundary branches into answer coverage checks."""
    if proof is None:
        return None
    anchors = range_anchors(question, chunks, proof)
    candidates = range_candidates(question, chunks)
    if not anchors or candidates is None:
        raise ValueError("Sufficient retrieval must supply a grounded range proof")
    compatible = {(leaf.chunk_id, " ".join(leaf.range_quote.casefold().split()))
                  for leaf in proof.leaves if leaf.compatible}
    branches = [item for item in candidates["leaves"] if item["chunk_id"] in anchors
                and (item["chunk_id"], " ".join(item["range_quote"].casefold().split())) in compatible
                and item["requested_intersection"] is not None]
    branches = [dict(item, branch_index=index) for index, item in enumerate(branches)]
    return {"question_quote": candidates["question_quote"], "unit": candidates["unit"],
            "branches": branches}


class AnswerGenerator:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    @traced("generation")
    async def generate(
        self, question: str, chunks: Sequence[RetrievedChunk],
        required_aspects: Sequence[str] = (),
        range_coverage: RangeCoverage | None = None,
        *, coverage_gaps: Sequence[str] = (), coverage_reason: str = "",
        previous_draft: DraftAnswer | None = None, verification_feedback: Sequence[str] = (),
    ) -> DraftAnswer:
        refs = SourceReferences(chunks)
        payload = refs.translate({
            "question": question, "required_aspects": list(required_aspects),
            "chunks": evidence_payload(chunks),
            "required_range": required_range_branches(question, chunks, range_coverage),
            "coverage_gaps": list(coverage_gaps),
            "coverage_reason": coverage_reason,
            "previous_draft": previous_draft.model_dump(mode="json") if previous_draft else None,
            "verification_feedback": list(verification_feedback),
        })
        result = await self._provider.generate_structured(
            [LLMMessage(role="system", content=ANSWER_GENERATION_PROMPT),
             LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
            response_schema=DraftAnswer, temperature=0.0,
        )
        draft = DraftAnswer.model_validate(result)
        draft = DraftAnswer.model_validate(refs.translate(draft.model_dump(), decode=True))
        record("generation", event="draft", draft=draft.model_dump(mode="json"))
        return draft
