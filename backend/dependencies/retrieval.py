"""Lazy composition of the production retrieval service."""

from functools import lru_cache

from ai.agent.contextualizer import QueryContextualizer
from ai.llm.gemini import GeminiProvider
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter
from backend.services.retrieval import HistoryAwareRetrievalService
from configs.settings import LLMSettings


@lru_cache(maxsize=1)
def get_retrieval_service() -> HistoryAwareRetrievalService:
    settings = LLMSettings()
    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_model_name)
    return HistoryAwareRetrievalService(
        QueryContextualizer(provider), LegacyRetrieverAdapter(),
    )
