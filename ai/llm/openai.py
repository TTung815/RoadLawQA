"""OpenAI Responses adapter using the existing asynchronous HTTPX dependency."""

import asyncio
from copy import deepcopy
import random
from typing import Any, List, Optional, Type

import httpx

from ai.llm.base import LLMMessage, LLMProvider, LLMResponse, T
from ai.llm.usage import normalize_usage


def strict_json_schema(response_schema: Type[T]) -> dict:
    """Convert Pydantic schemas to the strict object contract of Structured Outputs.

    Defaults become required fields; optional/null types retain their type.
    Keep numeric/string constraints and the original models' validators intact.
    Open dictionaries cannot be faithfully represented by this contract.
    """
    schema = deepcopy(response_schema.model_json_schema())

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                if node.get("additionalProperties") not in (None, False):
                    raise ValueError("Open dictionaries are not supported by strict Structured Outputs")
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            # Walk schema nodes, not property-name maps (a field may be named 'default').
            for key in ("properties", "$defs", "definitions"):
                for value in node.get(key, {}).values():
                    visit(value)
            for key in ("items", "anyOf", "oneOf", "allOf", "prefixItems", "not"):
                if key in node:
                    visit(node[key])

    visit(schema)
    return schema


class OpenAIProvider(LLMProvider):
    """No credential/client initialization until generation; bounded retries only."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-6-luna", *,
                 reasoning_effort: str = "medium", max_output_tokens: int = 16384,
                 request_timeout: float = 90.0, max_transient_retries: int = 2,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        if reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("Unsupported OpenAI reasoning effort")
        if request_timeout <= 0 or max_transient_retries < 0 or max_output_tokens < 1:
            raise ValueError("Invalid OpenAI request limits")
        self._api_key = api_key.strip() if api_key else None
        self._model_name = model_name
        self._reasoning_effort = reasoning_effort
        self._max_output_tokens = max_output_tokens
        self._request_timeout = request_timeout
        self._max_transient_retries = max_transient_retries
        self._transport = transport
        self._last_usage = None

    @property
    def last_usage(self):
        return self._last_usage

    async def _generate(self, messages: List[LLMMessage], temperature: float,
                        response_schema: Optional[Type[T]] = None) -> LLMResponse:
        self._last_usage = None
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM generation")
        if not self._model_name.strip():
            raise ValueError("OpenAI model_name must not be empty")
        if not messages or not any(m.role in {"user", "assistant"} for m in messages):
            raise ValueError("At least one user/assistant message is required")
        if any(m.role not in {"system", "user", "assistant"} for m in messages):
            raise ValueError("Unsupported message role")
        body: dict[str, Any] = {
            "model": self._model_name,
            "input": [m.model_dump() for m in messages],
            "reasoning": {"effort": self._reasoning_effort},
            "max_output_tokens": self._max_output_tokens,
            "store": False,
        }
        # GPT-6 rejects sampling parameters while reasoning is enabled.
        if self._reasoning_effort == "none":
            body["temperature"] = temperature
        if response_schema is not None:
            body["text"] = {"format": {"type": "json_schema", "name": response_schema.__name__,
                                      "strict": True, "schema": strict_json_schema(response_schema)}}
        for attempt in range(self._max_transient_retries + 1):
            retry_error = None
            async with httpx.AsyncClient(transport=self._transport,
                                        timeout=httpx.Timeout(self._request_timeout, connect=10.0)) as client:
                try:
                    response = await client.post("https://api.openai.com/v1/responses",
                                                 headers={"Authorization": f"Bearer {self._api_key}"}, json=body)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    retry_error = exc
                if retry_error is None:
                    retryable = response.status_code in {408, 429, 500, 502, 503, 504}
                    if response.status_code == 429:
                        try:
                            error = response.json().get("error", {})
                            if error.get("code") == "insufficient_quota" or error.get("type") == "insufficient_quota":
                                retryable = False
                        except (ValueError, AttributeError):
                            pass
                    if retryable:
                        try:
                            response.raise_for_status()
                        except httpx.HTTPStatusError as exc:
                            retry_error = exc
                if retry_error is None:
                    response.raise_for_status()
                    raw = response.json()
                    break
            if attempt == self._max_transient_retries:
                raise retry_error
            await asyncio.sleep(2 ** attempt + random.uniform(0, .25))

        self._last_usage = normalize_usage("openai", raw.get("usage"))
        if raw.get("status") != "completed" or raw.get("error") or raw.get("incomplete_details"):
            raise ValueError("OpenAI generation did not finish successfully")
        text = []
        for item in raw.get("output") or []:
            if item.get("type") != "message":
                continue  # Reasoning output is never returned as answer text.
            if item.get("role") != "assistant" or item.get("status") != "completed":
                raise ValueError("OpenAI returned an incomplete output message")
            for part in item.get("content") or []:
                if part.get("type") == "refusal":
                    raise ValueError("OpenAI refused generation")
                if part.get("type") == "output_text":
                    text.append(part["text"])
        content = "".join(text)
        if not content.strip():
            raise ValueError("OpenAI returned no text")
        return LLMResponse(content=content, raw_response=raw, usage=raw.get("usage") or {})

    async def generate(self, messages: List[LLMMessage], temperature: float = .1, **kwargs: Any) -> LLMResponse:
        if kwargs:
            raise TypeError("Additional generation options are not supported")
        return await self._generate(messages, temperature)

    async def generate_structured(self, messages: List[LLMMessage], response_schema: Type[T],
                                  temperature: float = .1, **kwargs: Any) -> T:
        if kwargs:
            raise TypeError("Additional generation options are not supported")
        response = await self._generate(messages, temperature, response_schema)
        return response_schema.model_validate_json(response.content)
