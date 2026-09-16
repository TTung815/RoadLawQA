# -*- coding: utf-8 -*-
"""
Core LLM Provider Abstractions
Defines the provider-agnostic interface for generation and structured output.
Suitable for future GeminiProvider, OpenAIProvider, and LocalProvider.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    """Message representation in a chat conversation."""
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Standardized text generation response."""
    content: str
    raw_response: Optional[Any] = None
    usage: Dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    Decouples application logic from specific models (Gemini, OpenAI, Local vLLM).
    """

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Generate a standard text completion response.

        Args:
            messages: List of conversation messages.
            temperature: Sampling temperature (lower = more deterministic).
            **kwargs: Provider-specific additional options.

        Returns:
            An LLMResponse containing the text output and optional usage metadata.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: List[LLMMessage],
        response_schema: Type[T],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> T:
        """
        Generate a structured response adhering strictly to a Pydantic schema.

        Args:
            messages: List of conversation messages.
            response_schema: Target Pydantic model class.
            temperature: Sampling temperature.
            **kwargs: Provider-specific additional options.

        Returns:
            An instance of response_schema parsed from the LLM output.
        """
        pass

