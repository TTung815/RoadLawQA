# -*- coding: utf-8 -*-
"""
Unit Tests for LLM Base Abstractions
"""
import pytest
from typing import List, Type, TypeVar
from pydantic import BaseModel
from ai.llm.base import LLMMessage, LLMResponse, LLMProvider

T = TypeVar("T", bound=BaseModel)


def test_llm_models():
    msg = LLMMessage(role="user", content="Chào bạn")
    assert msg.role == "user"
    assert msg.content == "Chào bạn"

    resp = LLMResponse(content="Xin chào", usage={"tokens": 10})
    assert resp.content == "Xin chào"
    assert resp.usage["tokens"] == 10


def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore


@pytest.mark.asyncio
async def test_dummy_llm_provider():
    class DummyTargetSchema(BaseModel):
        summary: str

    class DummyProvider(LLMProvider):
        async def generate(
            self, messages: List[LLMMessage], temperature: float = 0.1, **kwargs
        ) -> LLMResponse:
            return LLMResponse(content=f"Echo: {messages[-1].content}")

        async def generate_structured(
            self, messages: List[LLMMessage], response_schema: Type[T], temperature: float = 0.1, **kwargs
        ) -> T:
            return response_schema(summary=f"Structured: {messages[-1].content}")

    provider = DummyProvider()
    res = await provider.generate([LLMMessage(role="user", content="Test")])
    assert res.content == "Echo: Test"

    structured_res = await provider.generate_structured(
        [LLMMessage(role="user", content="Law")], DummyTargetSchema
    )
    assert structured_res.summary == "Structured: Law"

