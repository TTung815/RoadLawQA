"""Lazy construction only; no resources are initialized on application import."""

from functools import lru_cache

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerifier
from ai.agent.conversation_router import ConversationRouter
from ai.llm.factory import create_provider
from backend.dependencies.retrieval import get_agentic_retrieval_service
from backend.services.answer import AnswerService
from backend.services.chat import ChatService
from configs.settings import LLMSettings


def get_chat_service() -> ChatService:
    return ChatService(get_answer_service, get_conversation_router)


@lru_cache(maxsize=1)
def get_conversation_router() -> ConversationRouter:
    return ConversationRouter(create_provider(LLMSettings()))


@lru_cache(maxsize=1)
def get_answer_service() -> AnswerService:
    settings = LLMSettings()
    provider = create_provider(settings)
    return AnswerService(
        get_agentic_retrieval_service(), AnswerGenerator(provider), CitationVerifier(provider),
    )
