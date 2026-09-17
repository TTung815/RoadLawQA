"""Lazy composition of the production retrieval service."""

from functools import lru_cache

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter
from ai.llm.gemini import GeminiProvider
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from ai.retrieval.weaviate_lookup import WeaviateArticleLookup
from backend.services.retrieval import HistoryAwareRetrievalService
from backend.services.agentic_retrieval import AgenticRetrievalService
from configs.settings import LLMSettings, Settings


@lru_cache(maxsize=1)
def get_retrieval_service() -> HistoryAwareRetrievalService:
    settings = LLMSettings()
    provider = GeminiProvider(
        settings.gemini_api_key, settings.gemini_model_name,
        api_keys=settings.gemini_api_keys,
    )
    return HistoryAwareRetrievalService(
        QueryContextualizer(provider), LegacyRetrieverAdapter(),
    )


@lru_cache(maxsize=1)
def get_agentic_retrieval_service() -> AgenticRetrievalService:
    settings = LLMSettings()
    provider = GeminiProvider(
        settings.gemini_api_key, settings.gemini_model_name,
        api_keys=settings.gemini_api_keys,
    )
    expander = None
    if settings.structural_expansion_enabled:
        resources = Settings()
        lookup = WeaviateArticleLookup(
            resources.weaviate_host, resources.weaviate_port,
            resources.weaviate_grpc_port, resources.weaviate_collection,
        )
        expander = LegalNeighborhoodExpander(lookup.fetch_article)
    return AgenticRetrievalService(
        QueryContextualizer(provider), LegacyRetrieverAdapter(),
        EvidenceGrader(provider), QueryRewriter(provider),
        max_attempts=settings.max_retrieval_attempts,
        structural_expander=expander,
    )
