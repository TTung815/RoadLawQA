"""OpenAI protocol and fail-closed behavior with an in-memory HTTP transport."""

import json

import httpx
from pydantic import BaseModel, ValidationError
import pytest

from ai.agent.contextualizer import ContextualizedQuery
from ai.llm.base import LLMMessage
from ai.llm.measurement import MeasuredProvider
from ai.llm.openai import OpenAIProvider, strict_json_schema
from evaluation.llm_preflight import schema_fixtures


MESSAGES = [LLMMessage(role="system", content="Instruction"),
            LLMMessage(role="user", content="Input"), LLMMessage(role="assistant", content="History"),
            LLMMessage(role="user", content="Current")]


def response_body(text="OK"):
    return {"status": "completed", "error": None, "incomplete_details": None,
            "output": [{"type": "reasoning", "summary": []},
                       {"type": "message", "status": "completed", "role": "assistant",
                        "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 100, "output_tokens": 70,
                      "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 20}}}


@pytest.mark.asyncio
async def test_responses_request_maps_messages_and_omits_sampling_for_reasoning():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer fake-key"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6-luna" and body["input"] == [m.model_dump() for m in MESSAGES]
        assert body["reasoning"] == {"effort": "medium"}
        assert body["max_output_tokens"] == 16384 and body["store"] is False
        assert "temperature" not in body and "text" not in body
        return httpx.Response(200, json=response_body())
    provider = OpenAIProvider("fake-key", transport=httpx.MockTransport(handler))
    output = await provider.generate(MESSAGES, temperature=0.0)
    assert output.content == "OK"
    assert provider.last_usage["output_tokens"] == 70
    assert provider.last_usage["reasoning_tokens"] == 20


@pytest.mark.asyncio
async def test_structured_request_and_none_effort_sampling():
    def handler(request):
        body = json.loads(request.content)
        assert body["temperature"] == 0.0
        format_ = body["text"]["format"]
        assert format_["strict"] is True and format_["type"] == "json_schema"
        assert format_["schema"]["additionalProperties"] is False
        assert format_["schema"]["required"] == ["standalone_query"]
        return httpx.Response(200, json=response_body('{"standalone_query":"Query"}'))
    provider = OpenAIProvider("fake", reasoning_effort="none", transport=httpx.MockTransport(handler))
    parsed = await provider.generate_structured(MESSAGES, ContextualizedQuery, temperature=0.0)
    assert parsed.standalone_query == "Query"


@pytest.mark.parametrize("schema,value", schema_fixtures())
def test_all_pipeline_schemas_are_strict_without_mutating_business_models(schema, value):
    original = schema.model_json_schema()
    strict = strict_json_schema(schema)

    def check(node):
        if isinstance(node, list):
            for item in node:
                check(item)
        if isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node.get("properties", {}))
            for item in node.values():
                check(item)
    check(strict)
    assert schema.model_json_schema() == original
    assert schema.model_validate(value) is not None


def test_open_dictionary_schema_is_rejected_without_losing_its_semantics():
    class Dictionary(BaseModel):
        values: dict[str, str]
    with pytest.raises(ValueError, match="Open dictionaries"):
        strict_json_schema(Dictionary)


def test_a_field_named_default_is_not_removed_as_schema_metadata():
    class HasDefaultField(BaseModel):
        default: str
    schema = strict_json_schema(HasDefaultField)
    assert schema["required"] == ["default"] and "default" in schema["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["incomplete", "failed", "refusal", "empty", "message_incomplete"])
async def test_incomplete_refused_or_empty_output_fails_closed(failure):
    raw = response_body()
    if failure in {"incomplete", "failed"}:
        raw["status"] = failure
    elif failure == "refusal":
        raw["output"][1]["content"] = [{"type": "refusal", "refusal": "Refused"}]
    elif failure == "empty":
        raw["output"] = []
    else:
        raw["output"][1]["status"] = "in_progress"
    provider = OpenAIProvider("fake", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=raw)))
    with pytest.raises(ValueError, match="OpenAI"):
        await provider.generate(MESSAGES)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["not JSON", '{"standalone_query":" "}', '{"wrong":"value"}'])
async def test_invalid_structured_output_propagates_validation_failure(text):
    provider = OpenAIProvider("fake", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response_body(text))))
    with pytest.raises(ValidationError):
        await provider.generate_structured(MESSAGES, ContextualizedQuery)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(400, "bad_request"), (401, "invalid_api_key"),
                                         (403, "forbidden"), (404, "model_not_found"), (429, "insufficient_quota")])
async def test_permanent_errors_are_not_retried(status, code):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"code": code}})
    provider = OpenAIProvider("fake", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.generate(MESSAGES)
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503, "timeout"])
async def test_transient_retries_are_bounded_and_one_logical_call_is_observed(monkeypatch, status):
    requests = []
    async def no_sleep(delay):
        pass
    monkeypatch.setattr("ai.llm.openai.asyncio.sleep", no_sleep)
    def handler(request):
        requests.append(request)
        if status == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(status, json={"error": {"code": "rate_limit_exceeded"}})
    provider = MeasuredProvider(OpenAIProvider("fake", max_transient_retries=2, transport=httpx.MockTransport(handler)))
    with pytest.raises((httpx.HTTPStatusError, httpx.ReadTimeout)):
        await provider.generate(MESSAGES)
    assert len(requests) == 3
    assert provider.observations == [{"completed": False, "usage": None}]


@pytest.mark.asyncio
async def test_transient_error_then_success_and_structured_usage_is_measured(monkeypatch):
    calls = []
    async def no_sleep(delay):
        pass
    monkeypatch.setattr("ai.llm.openai.asyncio.sleep", no_sleep)
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=response_body('{"standalone_query":"Query"}'))
    provider = MeasuredProvider(OpenAIProvider("fake", transport=httpx.MockTransport(handler)))
    await provider.generate_structured(MESSAGES, ContextualizedQuery)
    assert len(calls) == 2 and len(provider.observations) == 1
    assert provider.observations[0]["usage"]["input_tokens"] == 100


@pytest.mark.asyncio
async def test_key_and_options_validation_happen_before_any_request():
    def forbidden(request):
        raise AssertionError("Network must not be called")
    provider = OpenAIProvider(None, transport=httpx.MockTransport(forbidden))
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        await provider.generate(MESSAGES)
    with pytest.raises(TypeError):
        await provider.generate(MESSAGES, unknown_option=True)
