"""Provider selection shared by serving dependencies and isolated evaluation."""

from ai.llm.base import LLMProvider
from configs.settings import LLMSettings


def create_provider(settings: LLMSettings) -> LLMProvider:
    if settings.llm_provider == "gemini":
        from ai.llm.gemini import GeminiProvider
        return GeminiProvider(api_keys=settings.gemini_api_keys, model_name=settings.model_name,
                              request_timeout=settings.llm_request_timeout_seconds,
                              max_transient_retries=settings.llm_max_transient_retries)
    if settings.llm_provider == "openai":
        from ai.llm.openai import OpenAIProvider
        return OpenAIProvider(settings.openai_api_key, settings.model_name,
                              reasoning_effort=settings.openai_reasoning_effort,
                              max_output_tokens=settings.openai_max_output_tokens,
                              request_timeout=settings.llm_request_timeout_seconds,
                              max_transient_retries=settings.llm_max_transient_retries)
    raise ValueError("Unsupported LLM provider")
