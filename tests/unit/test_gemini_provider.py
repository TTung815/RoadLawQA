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


@pytest.mark.asyncio
async def test_multi_key_rotation_on_429_succeeds():
    calls = []

    def handler(request):
        key = request.headers["x-goog-api-key"]
        calls.append(key)
        if key == "key-1":
            return httpx.Response(429, json={"error": {"message": "quota exceeded"}})
        return httpx.Response(200, json=response_body('{"standalone_query":"Success"}'))

    provider = GeminiProvider(
        api_keys=["key-1", "key-2"],
        model_name="test",
        transport=httpx.MockTransport(handler),
    )

    result = await provider.generate_structured(
        [LLMMessage(role="user", content="input")], ContextualizedQuery,
    )
    assert result.standalone_query == "Success"
    assert calls == ["key-1", "key-2"]

    # Subsequent request starts directly with key-2 without retrying key-1
    result2 = await provider.generate_structured(
        [LLMMessage(role="user", content="second input")], ContextualizedQuery,
    )
    assert result2.standalone_query == "Success"
    assert calls == ["key-1", "key-2", "key-2"]


@pytest.mark.asyncio
async def test_multi_key_rotation_all_keys_exhausted():
    calls = []

    def handler(request):
        calls.append(request.headers["x-goog-api-key"])
        return httpx.Response(429, json={"error": {"message": "rate limit"}})

    provider = GeminiProvider(
        api_key="key-A, key-B",
        model_name="test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await provider.generate_structured(
            [LLMMessage(role="user", content="input")], ContextualizedQuery,
        )
    assert calls == ["key-A", "key-B"]



@pytest.fixture
def retry_delays(monkeypatch):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr('ai.llm.gemini.asyncio.sleep', fake_sleep)
    monkeypatch.setattr('ai.llm.gemini.random.uniform', lambda *_: 0.0)
    return delays


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [503, 500, 502, 504, 408, 'timeout', 'network'])
async def test_transient_failure_retries_then_succeeds(failure, retry_delays):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.extensions['timeout']['read'] == 90.0
        if len(calls) == 1:
            if failure == 'timeout':
                raise httpx.ReadTimeout('slow', request=request)
            if failure == 'network':
                raise httpx.ConnectError('offline', request=request)
            return httpx.Response(failure)
        return httpx.Response(200, json=response_body('recovered'))

    result = await GeminiProvider('fake', 'test', httpx.MockTransport(handler)).generate(
        [LLMMessage(role='user', content='input')],
    )
    assert result.content == 'recovered'
    assert len(calls) == 2
    assert retry_delays == [1.0]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [503, 'timeout'])
async def test_persistent_transient_failure_is_bounded_and_propagates(failure, retry_delays):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('slow', request=request)
        return httpx.Response(failure)

    error = httpx.ReadTimeout if failure == 'timeout' else httpx.HTTPStatusError
    with pytest.raises(error):
        await GeminiProvider('fake', 'test', httpx.MockTransport(handler)).generate(
            [LLMMessage(role='user', content='input')],
        )
    assert len(calls) == 3
    assert retry_delays == [1.0, 2.0]


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [400, 401, 403, 404])
async def test_client_errors_are_not_retried(status, retry_delays):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    with pytest.raises(httpx.HTTPStatusError):
        await GeminiProvider('fake', 'test', httpx.MockTransport(handler)).generate(
            [LLMMessage(role='user', content='input')],
        )
    assert len(calls) == 1
    assert retry_delays == []


@pytest.mark.asyncio
async def test_transient_retry_budget_is_shared_across_key_rotation(retry_delays):
    calls = []
    statuses = iter([503, 429, 503, 503])

    def handler(request):
        calls.append(request.headers['x-goog-api-key'])
        return httpx.Response(next(statuses))

    provider = GeminiProvider(api_keys=['first', 'second'], transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError) as exc:
        await provider.generate([LLMMessage(role='user', content='input')])
    assert exc.value.response.status_code == 503
    assert calls == ['first', 'second', 'first', 'first']
    assert retry_delays == [1.0, 2.0]


@pytest.mark.asyncio
async def test_transient_retry_uses_next_configured_key(retry_delays):
    calls = []

    def handler(request):
        key = request.headers['x-goog-api-key']
        calls.append(key)
        if key == 'first':
            return httpx.Response(503)
        return httpx.Response(200, json=response_body('recovered'))

    provider = GeminiProvider(api_keys=['first', 'second'], transport=httpx.MockTransport(handler))
    messages = [LLMMessage(role='user', content='input')]
    assert (await provider.generate(messages)).content == 'recovered'
    assert (await provider.generate(messages)).content == 'recovered'
    assert calls == ['first', 'second', 'second']
    assert retry_delays == [1.0]


@pytest.mark.asyncio
async def test_concurrent_rotation_keeps_quota_failures_attached_to_requested_key(retry_delays):
    import asyncio

    recovered = asyncio.Event()
    first_calls = 0

    async def handler(request):
        nonlocal first_calls
        if request.headers['x-goog-api-key'] == 'second':
            recovered.set()
            return httpx.Response(200, json=response_body('recovered'))
        first_calls += 1
        if first_calls == 1:
            await recovered.wait()
            return httpx.Response(429)
        return httpx.Response(503)

    provider = GeminiProvider(api_keys=['first', 'second'], transport=httpx.MockTransport(handler))
    messages = [LLMMessage(role='user', content='input')]
    results = await asyncio.gather(provider.generate(messages), provider.generate(messages))
    assert [result.content for result in results] == ['recovered', 'recovered']
    assert first_calls == 2
