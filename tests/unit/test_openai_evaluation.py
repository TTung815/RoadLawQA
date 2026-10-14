"""Provider locks, preflight gates, token accounting and historical receipt compatibility."""

import json

import httpx
import pytest
from pydantic import ValidationError

from ai.llm.measurement import MeasuredProvider
from ai.llm.openai import OpenAIProvider
from ai.llm.usage import normalize_usage
from evaluation import core_runner as runner
from evaluation import llm_preflight as preflight
from evaluation.core_runtime import create_evaluation_provider
from evaluation.core_schema import RunSettings
from evaluation.snapshot import digest
from tests.unit.test_core_evaluation import write_run
from tests.unit.test_openai_provider import response_body


def settings(**kwargs):
    return RunSettings(provider="openai", model="gpt-6-luna", reasoning_effort="medium",
                       max_output_tokens=16384, embedding_revision="fixture", reranker_revision="fixture", **kwargs)


def test_openai_options_must_be_explicit_and_not_applied_to_gemini():
    with pytest.raises(ValidationError):
        RunSettings(provider="openai", model="gpt-6-luna", embedding_revision="fixture", reranker_revision="fixture")
    with pytest.raises(ValidationError):
        RunSettings(model="gemini", reasoning_effort="medium", embedding_revision="fixture", reranker_revision="fixture")


def test_openai_usage_does_not_double_count_reasoning_and_cached_cost_is_unknown():
    usage = normalize_usage("openai", response_body()["usage"])
    measured = runner.summarize_usage([{"completed": True, "usage": usage}],
                                      settings(input_usd_per_million=1, output_usd_per_million=2))
    assert measured["input_tokens"] == 100 and measured["output_tokens"] == 70
    assert measured["cost_usd"] == pytest.approx(.00024)
    for key in ("cached_input_tokens", "cache_write_input_tokens"):
        cached = {**usage, key: 10}
        assert runner.summarize_usage([{"completed": True, "usage": cached}], settings())["cost_usd"] is None
    missing = normalize_usage("openai", {"input_tokens": 100, "output_tokens": 70})
    assert runner.summarize_usage([{"completed": True, "usage": missing}],
                                 settings(input_usd_per_million=1, output_usd_per_million=2))["cost_usd"] is None


def test_historical_v1_run_digest_uses_original_representation(tmp_path):
    directory, gold, _ = write_run(tmp_path, error={"type": "FixtureError"})
    path = directory / "run.json"
    receipt = json.loads(path.read_text())
    receipt["plan"]["format_version"] = 1
    for field in ("provider", "reasoning_effort", "max_output_tokens", "request_timeout_seconds", "max_transient_retries"):
        receipt["plan"]["settings"].pop(field)
    receipt["plan_sha256"] = digest(receipt["plan"])
    path.write_text(json.dumps(receipt))
    plan, records = runner.verify_run(directory)
    assert plan.format_version == 1 and plan.settings.provider == "gemini"
    assert len(records) == 1
    from evaluation.core_scoring import score_run
    assert score_run(directory, private_gold=gold)["run_settings"]["provider"] == "gemini"
    receipt["plan"]["settings"]["model"] = "tampered"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="digest"):
        runner.verify_run(directory)


def test_evaluation_provider_uses_locked_behavior_and_selected_credentials(monkeypatch):
    from configs import settings as config
    from ai.llm import factory
    monkeypatch.setattr(config, "dotenv_values", lambda path: {"OPENAI_API_KEY": "fake"})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_MODEL_NAME", "wrong-model")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "max")
    captured = []
    def capture(configuration):
        captured.append(configuration)
        return OpenAIProvider("fake")
    monkeypatch.setattr(factory, "create_provider", capture)
    create_evaluation_provider(settings(request_timeout_seconds=45, max_transient_retries=1))
    actual = captured[0]
    assert actual.llm_provider == "openai" and actual.model_name == "gpt-6-luna"
    assert actual.openai_reasoning_effort == "medium" and actual.openai_api_key == "fake"
    assert actual.llm_request_timeout_seconds == 45 and actual.llm_max_transient_retries == 1


@pytest.mark.asyncio
async def test_preflight_checks_plain_and_every_real_pipeline_schema():
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        text = body["input"][-1]["content"] if "text" in body else "OK"
        return httpx.Response(200, json=response_body(text))
    provider = MeasuredProvider(OpenAIProvider("fake", transport=httpx.MockTransport(handler)))
    checks = await preflight.check_provider(provider, 10)
    assert len(checks) == 6 and all(c["passed"] for c in checks)
    assert len(requests) == 6 and len(provider.observations) == 6


@pytest.mark.asyncio
async def test_failed_plain_preflight_does_not_spend_structured_requests():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(401)
    provider = MeasuredProvider(OpenAIProvider("fake", transport=httpx.MockTransport(handler)))
    checks = await preflight.check_provider(provider, 10)
    assert checks == [{"name": "plain", "passed": False, "error_type": "HTTPStatusError"}]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_failed_schema_preflight_stops_at_first_failure():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response_body("OK"))
    provider = MeasuredProvider(OpenAIProvider("fake", transport=httpx.MockTransport(handler)))
    checks = await preflight.check_provider(provider, 10)
    assert len(checks) == 2 and checks[-1]["passed"] is False
    assert len(requests) == 2


def test_preflight_receipt_is_bound_to_plan_and_cannot_pass_with_missing_checks(monkeypatch, tmp_path):
    directory, _, _ = write_run(tmp_path, error={"type": "FixtureError"})
    plan = runner.verify_run(directory)[0]
    monkeypatch.setattr(runner, "load_plan", lambda path: plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"plan_sha256": "a" * 64}))
    path = tmp_path / "preflight.json"
    result = {"format_version": 1, "kind": "llm_compatibility_preflight", "plan_sha256": "a" * 64,
              "provider": "gemini", "model": plan.settings.model, "passed": True,
              "checks": [{"name": name, "passed": True} for name in
                         ["plain"] + [s.__name__ for s, _ in preflight.schema_fixtures()]]}
    def save():
        result["receipt_sha256"] = digest({k: v for k, v in result.items() if k != "receipt_sha256"})
        path.write_text(json.dumps(result))
    save()
    preflight.verify_preflight(path, plan_path)
    result["plan_sha256"] = "b" * 64
    save()
    with pytest.raises(ValueError, match="exact locked plan"):
        preflight.verify_preflight(path, plan_path)
    result["plan_sha256"] = "a" * 64
    result["checks"].pop()
    save()
    with pytest.raises(ValueError):
        preflight.verify_preflight(path, plan_path)


@pytest.mark.asyncio
async def test_runner_requires_preflight_before_creating_live_runtime(monkeypatch, tmp_path):
    directory, _, _ = write_run(tmp_path, error={"type": "FixtureError"})
    plan = runner.verify_run(directory)[0]
    monkeypatch.setattr(runner, "load_plan", lambda path: plan)
    from evaluation import core_runtime
    monkeypatch.setattr(core_runtime, "create_live_runtime", lambda *a, **k: pytest.fail("must not initialize resources"))
    with pytest.raises(ValueError, match="--preflight"):
        await runner.execute_plan(tmp_path / "plan.json", tmp_path / "new-run")
    assert not (tmp_path / "new-run").exists()


@pytest.mark.asyncio
async def test_missing_credentials_preflight_writes_failure_without_calling_network(monkeypatch, tmp_path):
    directory, _, _ = write_run(tmp_path, error={"type": "FixtureError"})
    plan = runner.verify_run(directory)[0]
    plan.settings = settings()
    monkeypatch.setattr(runner, "load_plan", lambda path: plan)
    from configs import settings as config
    monkeypatch.setattr(config, "dotenv_values", lambda path: {})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(httpx.AsyncClient, "post", lambda *a, **k: pytest.fail("no network call"))
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"plan_sha256": "a" * 64}))
    result = await preflight.run_preflight(plan_path, tmp_path / "preflight.json")
    assert result["passed"] is False and result["usage"]["llm_calls"] == 0
    assert result["checks"][0]["name"] == "credentials"
    assert "OPENAI_API_KEY" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,status", [("valid", "answered"), ("negative", "verification_failed"),
                                        ("unsupported", "verification_failed")])
async def test_openai_adapter_runs_v2_answer_pipeline_and_preserves_publication_guards(mode, status):
    from ai.agent.answer_generator import AnswerGenerator
    from ai.agent.citation_verifier import CitationVerifier
    from ai.agent.contextualizer import QueryContextualizer
    from ai.agent.evidence_grader import EvidenceGrader
    from ai.agent.query_rewriter import QueryRewriter
    from backend.services.agentic_retrieval import AgenticRetrievalService
    from backend.services.answer import AnswerService
    from tests.unit.test_agentic_retrieval import ScriptedRetriever, chunk
    from tests.unit.test_grounded_answer import COMPLETE, DRAFT, QUESTION, semantic
    draft = json.loads(json.dumps(DRAFT))
    if mode == "negative":
        draft["claims"][0]["support_state"] = "negative_support"
    outputs = {"EvidenceGrade": COMPLETE, "GeneratedAnswer": {"answer": draft},
               "SemanticVerification": semantic(2, supported=mode != "unsupported")}
    calls = []
    def handler(request):
        body = json.loads(request.content)
        name = body["text"]["format"]["name"]
        calls.append(name)
        assert "temperature" not in body
        return httpx.Response(200, json=response_body(json.dumps(outputs[name])))
    provider = MeasuredProvider(OpenAIProvider("fake", transport=httpx.MockTransport(handler)))
    retrieval = AgenticRetrievalService(QueryContextualizer(provider),
                ScriptedRetriever([[chunk("money"), chunk("points")]]), EvidenceGrader(provider),
                QueryRewriter(provider), max_attempts=1)
    service = AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider))
    result = await service.answer(QUESTION)
    assert result.status == status
    expected = ["EvidenceGrade", "GeneratedAnswer"]
    if mode != "negative":
        expected.append("SemanticVerification")
    if mode != "valid":
        expected.append("GeneratedAnswer")
        if mode != "negative":
            expected.append("SemanticVerification")
    assert calls == expected
    assert result.repair_attempts == (0 if mode == "valid" else 1)
    if mode != "valid":
        assert result.answer is None
    else:
        assert result.answer.claims[0].citations[0].chunk_id == "money"
