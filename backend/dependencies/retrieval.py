"""Lazy composition of the production retrieval service."""

from functools import lru_cache

from ai.agent.contextualizer import QueryContextualizer
from ai.llm.factory import create_provider
from ai.retrieval.runtime import LazyRetriever
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from ai.pipeline.retrieval import HistoryAwareRetrievalService
from ai.pipeline.retrieval import LeanRetrievalService
from configs.settings import LLMSettings


@lru_cache(maxsize=1)
def get_current_retriever() -> LazyRetriever:
    return LazyRetriever()


@lru_cache(maxsize=1)
def get_retrieval_service() -> HistoryAwareRetrievalService:
    settings = LLMSettings()
    provider = create_provider(settings)
    return HistoryAwareRetrievalService(
        QueryContextualizer(provider), get_current_retriever(),
    )


@lru_cache(maxsize=1)
def get_lean_retrieval_service() -> LeanRetrievalService:
    settings = LLMSettings()
    provider = create_provider(settings)
    expander = None
    if settings.structural_expansion_enabled:
        expander = LegalNeighborhoodExpander(
            get_current_retriever().fetch_article,
            combination_lookup=get_current_retriever().fetch_combination_rules)
    return LeanRetrievalService(
        QueryContextualizer(provider), get_current_retriever(),
        structural_expander=expander,
    )
