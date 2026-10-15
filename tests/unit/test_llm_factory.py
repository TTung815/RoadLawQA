"""Selection and dependency wiring, without credentials or live resources."""

import pytest
from pydantic import ValidationError

from ai.llm.factory import create_provider
from ai.llm.gemini import GeminiProvider
from ai.llm.openai import OpenAIProvider
from configs.settings import LLMSettings


@pytest.fixture
def isolated_config(monkeypatch):
    from configs import settings
    monkeypatch.setattr(settings, "dotenv_values", lambda path: {})
    for name in LLMSettings._env_fields.values():
        monkeypatch.delenv(name, raising=False)


def test_gemini_environment_remains_compatible(isolated_config, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_NAME", "legacy-model")
    monkeypatch.setenv("GEMINI_API_KEYS", "first,second")
    settings = LLMSettings()
    provider = create_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider._model_name == "legacy-model" and provider.api_keys == ["first", "second"]


def test_openai_selection_precedence_and_credentials_do_not_require_gemini(isolated_config, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL_NAME", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "irrelevant")
    provider = create_provider(LLMSettings())
    assert isinstance(provider, OpenAIProvider) and provider._model_name == "gpt-6-luna"
    assert provider._api_key == "fake-openai"
    assert LLMSettings(llm_model_name="explicit-model").model_name == "explicit-model"


def test_missing_keys_do_not_prevent_provider_construction(isolated_config):
    assert isinstance(create_provider(LLMSettings(llm_provider="openai")), OpenAIProvider)


def test_unknown_provider_is_rejected(isolated_config):
    with pytest.raises(ValidationError):
        LLMSettings(llm_provider="unknown")


def test_backend_dependencies_use_shared_factory(isolated_config, monkeypatch):
    from backend.dependencies import retrieval, answer
    fake = object()
    seen = []
    def factory(settings):
        seen.append(settings.llm_provider)
        return fake
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("STRUCTURAL_EXPANSION_ENABLED", "false")
    monkeypatch.setattr(retrieval, "create_provider", factory)
    monkeypatch.setattr(answer, "create_provider", factory)
    retrieval.get_retrieval_service.cache_clear()
    retrieval.get_lean_retrieval_service.cache_clear()
    answer.get_answer_service.cache_clear()
    try:
        retrieval.get_retrieval_service()
        answer.get_answer_service()
        assert seen == ["openai", "openai", "openai"]
    finally:
        retrieval.get_retrieval_service.cache_clear()
        retrieval.get_lean_retrieval_service.cache_clear()
        answer.get_answer_service.cache_clear()


@pytest.mark.parametrize("router_effort, expected", [(None, "medium"), ("low", "low"), ("none", "none")])
def test_router_uses_its_own_reasoning_effort_without_changing_answer_stages(monkeypatch, router_effort, expected):
    from backend.dependencies.answer import router_settings
    from configs.settings import LLMSettings
    settings = LLMSettings(llm_provider="openai", openai_api_key="fake", openai_reasoning_effort="medium",
                           router_reasoning_effort=router_effort)
    assert router_settings(settings).openai_reasoning_effort == expected
    # Generation and verification keep the shared setting.
    assert settings.openai_reasoning_effort == "medium"


def test_router_effort_defaults_to_low_and_is_ignored_for_gemini(monkeypatch):
    from backend.dependencies.answer import router_settings
    from configs.settings import LLMSettings
    monkeypatch.delenv("ROUTER_REASONING_EFFORT", raising=False)
    assert LLMSettings(llm_provider="openai", openai_api_key="fake").router_reasoning_effort == "low"
    gemini = LLMSettings(llm_provider="gemini", gemini_api_key="fake")
    assert router_settings(gemini) is gemini
