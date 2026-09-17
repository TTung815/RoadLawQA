"""Improve retrieval specificity using a grade's identified evidence gap."""

import json
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from ai.agent.evidence_grader import EvidenceGrade
from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.query_rewrite import QUERY_REWRITE_PROMPT


class RewrittenQuery(BaseModel):
    rewritten_query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QueryRewriter:
    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    async def rewrite(
        self, question: str, retrieval_query: str, grade: EvidenceGrade,
    ) -> RewrittenQuery:
        result = await self._llm_provider.generate_structured(
            [
                LLMMessage(role="system", content=QUERY_REWRITE_PROMPT),
                LLMMessage(role="user", content=json.dumps({
                    "question": question,
                    "retrieval_query": retrieval_query,
                    "evidence_gap": grade.reason,
                    "missing_aspects": grade.missing_aspects,
                }, ensure_ascii=False)),
            ],
            response_schema=RewrittenQuery, temperature=0.0,
        )
        return RewrittenQuery.model_validate(result)
