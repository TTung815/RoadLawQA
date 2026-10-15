"""History-aware query contextualization through the LLM abstraction."""

import json
from typing import Annotated, Mapping, Sequence

from pydantic import BaseModel, StringConstraints

from ai.llm.base import LLMMessage, LLMProvider
from ai.prompts.contextualization import CONTEXTUALIZATION_PROMPT
from ai.diagnostics import traced


class ContextualizedQuery(BaseModel):
    """A single nonempty query ready for a later retrieval step."""

    standalone_query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ]


class QueryContextualizer:
    """Resolve conversational references without retrieving or answering.

    History contains user/assistant role and content dictionaries in chronological
    order. Provider selection belongs to the caller.
    Empty history bypasses generation; all nonempty history is sent to the provider,
    which determines relevance using the contextualization prompt.
    Provider failures propagate; this milestone introduces no retry policy.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm_provider = llm_provider

    @traced("contextualization")
    async def contextualize(
        self,
        current_query: str,
        chat_history: Sequence[Mapping[str, str]] = (),
    ) -> ContextualizedQuery:
        query = current_query.strip()
        if not query:
            raise ValueError("current_query must not be empty")

        if not chat_history:
            return ContextualizedQuery(standalone_query=query)

        history = []
        for turn in chat_history:
            role, content = turn["role"], turn["content"]
            if role not in ("user", "assistant") or not isinstance(content, str):
                raise ValueError("History must contain user/assistant text messages")
            history.append({"role": role, "content": content})

        messages = [
            LLMMessage(role="system", content=CONTEXTUALIZATION_PROMPT),
            LLMMessage(
                role="user",
                content=json.dumps(
                    {"current_query": query, "chat_history": history},
                    ensure_ascii=False,
                ),
            ),
        ]
        result = await self._llm_provider.generate_structured(
            messages, response_schema=ContextualizedQuery, temperature=0.0
        )
        return ContextualizedQuery.model_validate(result)
