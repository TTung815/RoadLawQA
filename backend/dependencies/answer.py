"""Lazy construction only; no resources are initialized on application import."""

from functools import lru_cache

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerifier
from ai.llm.gemini import GeminiProvider
from backend.dependencies.retrieval import get_agentic_retrieval_service
from backend.services.answer import AnswerService
from configs.settings import LLMSettings


@lru_cache(maxsize=1)
def get_answer_service() -> AnswerService:
    settings = LLMSettings()
    provider = GeminiProvider(
        settings.gemini_api_key, settings.gemini_model_name,
        api_keys=settings.gemini_api_keys,
    )
    return AnswerService(
        get_agentic_retrieval_service(), AnswerGenerator(provider), CitationVerifier(provider),
    )
