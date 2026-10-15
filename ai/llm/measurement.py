"""Observe logical calls through the public provider interface, including errors."""

from typing import Any

from ai.llm.base import LLMProvider


class MeasuredProvider(LLMProvider):
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.observations: list[dict] = []

    async def _call(self, method: str, *args: Any, **kwargs: Any):
        try:
            result = await getattr(self.provider, method)(*args, **kwargs)
        except BaseException:
            self.observations.append({"completed": False, "usage": self.provider.last_usage})
            raise
        self.observations.append({"completed": True, "usage": self.provider.last_usage})
        return result

    async def generate(self, *args: Any, **kwargs: Any):
        return await self._call("generate", *args, **kwargs)

    async def generate_structured(self, *args: Any, **kwargs: Any):
        return await self._call("generate_structured", *args, **kwargs)
