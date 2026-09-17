# -*- coding: utf-8 -*-
"""
Unit Tests for Pydantic Schemas and Settings
"""
import pytest
import os
from pydantic import ValidationError
from backend.schemas.common import HealthResponse
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.schemas.quiz import QuizQuestion, QuizRequest, QuizResponse
from configs.settings import Settings, get_settings


def test_health_response_schema():
    health = HealthResponse()
    assert health.status == "ok"
    assert health.app == "VietLaw-Agent"
    assert health.version == "2.0.0"

    data = health.model_dump()
    assert data == {"status": "ok", "app": "VietLaw-Agent", "version": "2.0.0"}


def test_chat_request_validation():
    # Valid request
    req = ChatRequest(message="Vượt đèn đỏ phạt bao nhiêu?", top_k=5)
    assert req.message == "Vượt đèn đỏ phạt bao nhiêu?"
    assert req.top_k == 5

    # Invalid empty message
    with pytest.raises(ValidationError):
        ChatRequest(message="", top_k=5)

    # Invalid top_k out of bounds
    with pytest.raises(ValidationError):
        ChatRequest(message="Test", top_k=0)
    with pytest.raises(ValidationError):
        ChatRequest(message="Test", top_k=25)


def test_chat_response():
    resp = ChatResponse(answer="Mức phạt là 800k-1tr", citations=["Điều 6 Nghị định 168"])
    assert resp.answer == "Mức phạt là 800k-1tr"
    assert len(resp.citations) == 1


def test_quiz_schemas():
    # Valid question
    q = QuizQuestion(
        question="Tín hiệu đèn vàng có ý nghĩa gì?",
        options={"A": "Dừng lại", "B": "Đi tiếp", "C": "Tăng tốc", "D": "Rẽ phải"},
        correct_answer="A",
        explanation="Phải dừng lại trước vạch dừng",
        citation="Khoản 3 Điều 10 Luật 36/2024",
    )
    assert q.correct_answer == "A"
    assert len(q.options) == 4

    # Quiz request
    req = QuizRequest(topic="nồng độ cồn", num_questions=3)
    assert req.topic == "nồng độ cồn"
    assert req.num_questions == 3

    # Quiz response
    quiz_resp = QuizResponse(questions=[q])
    assert len(quiz_resp.questions) == 1


def test_settings_does_not_require_gemini_key():
    # Explicitly instantiate settings without GEMINI_API_KEY
    settings = Settings(gemini_api_key=None)
    assert settings.gemini_api_key is None
    assert settings.app_name == "VietLaw-Agent"
    assert settings.weaviate_collection == "LawChunks"
    assert settings.bm25_index_path.name == "bm25_index.pkl"

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


@pytest.mark.parametrize("value", ["0", "3", "invalid"])
def test_agentic_attempt_limit_config_is_bounded(monkeypatch, value):
    from configs.settings import LLMSettings

    monkeypatch.setenv("MAX_RETRIEVAL_ATTEMPTS", value)
    with pytest.raises(ValidationError):
        LLMSettings()


def test_agentic_attempt_limit_can_disable_retry(monkeypatch):
    from configs.settings import LLMSettings

    monkeypatch.setenv("MAX_RETRIEVAL_ATTEMPTS", "1")
    assert LLMSettings().max_retrieval_attempts == 1
