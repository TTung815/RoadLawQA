"""Lazy composition of the production retrieval service."""

from functools import lru_cache

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter
from ai.llm.gemini import GeminiProvider
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter
from backend.services.retrieval import HistoryAwareRetrievalService
from backend.services.agentic_retrieval import AgenticRetrievalService
from configs.settings import LLMSettings


@lru_cache(maxsize=1)
def get_retrieval_service() -> HistoryAwareRetrievalService:
    settings = LLMSettings()
    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_model_name)
    return HistoryAwareRetrievalService(
        QueryContextualizer(provider), LegacyRetrieverAdapter(),
    )


@lru_cache(maxsize=1)
def get_agentic_retrieval_service() -> AgenticRetrievalService:
    settings = LLMSettings()
    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_model_name)
    return AgenticRetrievalService(
        QueryContextualizer(provider), LegacyRetrieverAdapter(),
        EvidenceGrader(provider), QueryRewriter(provider),
        max_attempts=settings.max_retrieval_attempts,
    )
