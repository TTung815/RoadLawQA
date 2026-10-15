# -*- coding: utf-8 -*-
"""
Unit Tests for Pydantic Schemas and Settings
"""
import pytest
import os
from pydantic import ValidationError
from backend.schemas.common import HealthResponse
from configs.settings import Settings, get_settings


def test_health_response_schema():
    health = HealthResponse()
    assert health.status == "ok"
    assert health.app == "VietLaw-Agent"
    assert health.version == "2.0.0"

    data = health.model_dump()
    assert data == {"status": "ok", "app": "VietLaw-Agent", "version": "2.0.0"}


def test_retrieval_request_validation():
    from backend.schemas.retrieval import RetrievalRequest

    assert RetrievalRequest(current_query="Quy tắc giao thông?").top_k == 10
    with pytest.raises(ValidationError):
        RetrievalRequest(current_query="")


def test_settings_does_not_require_gemini_key():
    # Explicitly instantiate settings without GEMINI_API_KEY
    settings = Settings(gemini_api_key=None)
    assert settings.gemini_api_key is None
    assert settings.app_name == "VietLaw-Agent"
    assert settings.weaviate_collection == "LawStructured20260922V2"

    global_s = get_settings()
    assert global_s is not None


def test_settings_env_file_is_anchored_nonmutating_and_optional(monkeypatch, tmp_path):
    from configs import settings as config

    monkeypatch.chdir(tmp_path)
    for key in ("GEMINI_API_KEY", "WEAVIATE_HOST", "WEAVIATE_PORT", "WEAVIATE_GRPC_PORT"):
        monkeypatch.delenv(key, raising=False)
    paths = []

    def file_values(path):
        paths.append(path)
        return {"WEAVIATE_HOST": "from-file", "WEAVIATE_PORT": "1234"}

    monkeypatch.setattr(config, "dotenv_values", file_values)
    before = dict(os.environ)
    settings = Settings()
    assert paths == [config.PROJECT_ROOT / ".env"]
    assert settings.weaviate_host == "from-file"
    assert settings.weaviate_port == 1234
    assert settings.gemini_api_key is None
    assert dict(os.environ) == before
    monkeypatch.setenv("WEAVIATE_PORT", "2345")
    assert Settings().weaviate_port == 2345
    assert Settings(weaviate_port=3456).weaviate_port == 3456


def test_invalid_resource_settings_validate_only_on_instantiation(monkeypatch):
    monkeypatch.setenv("WEAVIATE_PORT", "invalid")
    with pytest.raises(ValidationError):
        Settings()


def test_llm_settings_ignore_invalid_retrieval_config(monkeypatch):
    from configs.settings import LLMSettings

    monkeypatch.setenv("WEAVIATE_PORT", "invalid")
    monkeypatch.setenv("WEAVIATE_GRPC_PORT", "invalid")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "chosen-model")
    settings = LLMSettings(gemini_api_key=None)
    assert settings.gemini_api_key is None
    assert settings.gemini_model_name == "chosen-model"


def test_llm_settings_multi_key_parsing(monkeypatch):
    from configs.settings import LLMSettings

    monkeypatch.setattr("configs.settings.dotenv_values", lambda _: {})

    # Comma-separated GEMINI_API_KEYS
    monkeypatch.setenv("GEMINI_API_KEYS", "key-1, key-2, key-3")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = LLMSettings()
    assert s.gemini_api_keys == ["key-1", "key-2", "key-3"]
    assert s.gemini_api_key == "key-1"

    # Single GEMINI_API_KEY fallback
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "single-key")
    s2 = LLMSettings()
    assert s2.gemini_api_keys == ["single-key"]
    assert s2.gemini_api_key == "single-key"
