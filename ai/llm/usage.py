"""Normalize vendor token counters without inventing missing usage or prices."""

from typing import Any


def _counter(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def normalize_usage(provider: str, usage: Any) -> dict | None:
    if not isinstance(usage, dict) or not usage:
        return None
    if provider == "gemini":
        input_tokens = _counter(usage.get("promptTokenCount"))
        visible = _counter(usage.get("candidatesTokenCount"))
        reasoning = _counter(usage.get("thoughtsTokenCount", 0))
        output_tokens = visible + reasoning if visible is not None and reasoning is not None else None
        cached = _counter(usage.get("cachedContentTokenCount", 0))
        cache_write = 0
    elif provider == "openai":
        input_tokens = _counter(usage.get("input_tokens"))
        # OpenAI output_tokens already includes reasoning_tokens; do not add it twice.
        output_tokens = _counter(usage.get("output_tokens"))
        inputs = usage.get("input_tokens_details") or {}
        outputs = usage.get("output_tokens_details") or {}
        cached = _counter(inputs.get("cached_tokens")) if isinstance(inputs, dict) else None
        cache_write = _counter(inputs.get("cache_write_tokens")) if isinstance(inputs, dict) else None
        reasoning = _counter(outputs.get("reasoning_tokens")) if isinstance(outputs, dict) else None
    else:
        raise ValueError("Unknown token usage provider")
    return {"input_tokens": input_tokens, "output_tokens": output_tokens,
            "reasoning_tokens": reasoning, "cached_input_tokens": cached,
            "cache_write_input_tokens": cache_write}
