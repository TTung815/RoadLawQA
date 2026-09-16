"""Provider wire-format and failure tests using HTTPX's in-memory transport."""

import json

import httpx
from pydantic import BaseModel, ValidationError
import pytest

from ai.agent.contextualizer import ContextualizedQuery
from ai.llm.base import LLMMessage
from ai.llm.gemini import GeminiProvider


def response_body(text):
    return {
        "candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": "private reasoning", "thought": True}, {"text": text}],
        }}],
        "usageMetadata": {"totalTokenCount": 12},
    }


@pytest.mark.asyncio
async def test_structured_generation_sends_schema_and_maps_messages():
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == (
            "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
        )
        assert request.url.query == b""
        assert request.headers["x-goog-api-key"] == "fake-key"
        body = json.loads(request.content)
        assert body["systemInstruction"] == {"parts": [{"text": "Rewrite only"}]}
        assert body["contents"] == [
            {"role": "user", "parts": [{"text": "Prior query"}]},
            {"role": "model", "parts": [{"text": "Prior answer"}]},
            {"role": "user", "parts": [{"text": "Current query"}]},
        ]
        assert body["generationConfig"] == {
            "temperature": 0.0, "responseMimeType": "application/json",
            "responseJsonSchema": ContextualizedQuery.model_json_schema(),
        }
        return httpx.Response(200, json=response_body('{"standalone_query":"Standalone"}'))

    provider = GeminiProvider("fake-key", "models/test-model", httpx.MockTransport(handler))
    result = await provider.generate_structured([
        LLMMessage(role="system", content="Rewrite only"),
        LLMMessage(role="user", content="Prior query"),
        LLMMessage(role="assistant", content="Prior answer"),
        LLMMessage(role="user", content="Current query"),
    ], ContextualizedQuery, temperature=0.0)
    assert result.standalone_query == "Standalone"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_generate_returns_text_and_usage_without_structured_options():
    def handler(request):
        assert json.loads(request.content)["generationConfig"] == {"temperature": 0.1}
        return httpx.Response(200, json=response_body("text output"))

    provider = GeminiProvider("fake", "test", httpx.MockTransport(handler))
    result = await provider.generate([LLMMessage(role="user", content="input")])
    assert result.content == "text output"
    assert result.usage == {"totalTokenCount": 12}


@pytest.mark.asyncio
async def test_structured_provider_is_not_specific_to_contextualization_schema():
    class OtherSchema(BaseModel):
        count: int

    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json=response_body('{"count":3}'),
    ))
    result = await GeminiProvider("fake", "test", transport).generate_structured(
        [LLMMessage(role="user", content="input")], OtherSchema,
    )
    assert isinstance(result, OtherSchema)
    assert result.count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
])
async def test_missing_blocked_or_incomplete_output_fails(body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ValueError, match="Gemini"):
        await GeminiProvider("fake", "test", transport).generate_structured(
            [LLMMessage(role="user", content="input")], ContextualizedQuery,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["not JSON", '{"standalone_query":"   "}', '{"wrong_field":"value"}'])
async def test_invalid_structured_response_fails_validation(text):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response_body(text)))
    with pytest.raises(ValidationError):
        await GeminiProvider("fake", "test", transport).generate_structured(
            [LLMMessage(role="user", content="input")], ContextualizedQuery,
        )


@pytest.mark.asyncio
async def test_http_error_propagates_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with pytest.raises(httpx.HTTPStatusError):
        await GeminiProvider("fake", "test", httpx.MockTransport(handler)).generate_structured(
            [LLMMessage(role="user", content="input")], ContextualizedQuery,
        )
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_missing_key_fails_only_when_generation_is_requested():
    def unexpected_request(request):
        pytest.fail("Missing credentials must fail before network I/O")

    provider = GeminiProvider(None, "test", httpx.MockTransport(unexpected_request))
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await provider.generate_structured(
            [LLMMessage(role="user", content="input")], ContextualizedQuery,
        )
