"""Lazy construction only; no resources are initialized on application import."""

from functools import lru_cache

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerifier
from ai.agent.conversation_router import ConversationRouter
from ai.llm.factory import create_provider
from backend.dependencies.retrieval import get_lean_retrieval_service
from backend.services.answer import AnswerService
from backend.services.chat import ChatService
from configs.settings import LLMSettings


def get_chat_service() -> ChatService:
    return ChatService(get_answer_service, get_conversation_router)


def router_settings(settings: LLMSettings) -> LLMSettings:
    """Router-specific reasoning effort; generation/verification keep theirs."""
    if settings.llm_provider != "openai" or settings.router_reasoning_effort is None:
        return settings
    return settings.model_copy(update={"openai_reasoning_effort": settings.router_reasoning_effort})


@lru_cache(maxsize=1)
def get_conversation_router() -> ConversationRouter:
    return ConversationRouter(create_provider(router_settings(LLMSettings())))


@lru_cache(maxsize=1)
def get_answer_service() -> AnswerService:
    settings = LLMSettings()
    provider = create_provider(settings)
    return AnswerService(
        get_lean_retrieval_service(), AnswerGenerator(provider), CitationVerifier(provider),
    )
