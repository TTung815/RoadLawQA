"""Minimal Gemini REST provider. No SDK configuration or import-time I/O."""

from typing import Any, Dict, List, Optional, Type
from urllib.parse import quote

import httpx

from ai.llm.base import LLMMessage, LLMProvider, LLMResponse, T


class GeminiProvider(LLMProvider):
    """Use the GenerateContent API; caller supplies credentials and model.

    Credentials are required only when generation is requested. Each call owns
    its HTTP client, so there is no shared client lifecycle or global SDK state.
    """

    def __init__(
        self, api_key: Optional[str], model_name: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._api_key = api_key
        self._model_name = model_name
        self._transport = transport

    async def _generate(
        self, messages: List[LLMMessage], temperature: float,
        response_schema: Optional[Type[T]] = None,
    ) -> LLMResponse:
        if not self._api_key or not self._api_key.strip():
            raise ValueError("GEMINI_API_KEY is required for contextualization")
        if not self._model_name.strip():
            raise ValueError("Gemini model_name must not be empty")

        contents = []
        system_parts = []
        for message in messages:
            part = {"text": message.content}
            if message.role == "system":
                system_parts.append(part)
            elif message.role in ("user", "assistant"):
                contents.append({
                    "role": "model" if message.role == "assistant" else "user",
                    "parts": [part],
                })
            else:
                raise ValueError(f"Unsupported message role: {message.role}")
        if not contents:
            raise ValueError("At least one user/assistant message is required")

        config: Dict[str, Any] = {"temperature": temperature}
        if response_schema is not None:
            config.update({
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema.model_json_schema(),
            })
        body: Dict[str, Any] = {"contents": contents, "generationConfig": config}
        if system_parts:
            body["systemInstruction"] = {"parts": system_parts}

        model = quote(self._model_name.removeprefix("models/"), safe="")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            response = await client.post(
                url, headers={"x-goog-api-key": self._api_key}, json=body,
            )
            response.raise_for_status()
            raw = response.json()

        candidates = raw.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates (possibly blocked)")
        candidate = candidates[0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError("Gemini generation did not finish successfully")
        text = "".join(
            part["text"] for part in candidate.get("content", {}).get("parts", [])
            if "text" in part and not part.get("thought", False)
        )
        if not text.strip():
            raise ValueError("Gemini returned no text")
        return LLMResponse(
            content=text, raw_response=raw, usage=raw.get("usageMetadata") or {},
        )

    async def generate(
        self, messages: List[LLMMessage], temperature: float = 0.1, **kwargs: Any,
    ) -> LLMResponse:
        if kwargs:
            raise TypeError("Additional generation options are not supported yet")
        return await self._generate(messages, temperature)

    async def generate_structured(
        self, messages: List[LLMMessage], response_schema: Type[T],
        temperature: float = 0.1, **kwargs: Any,
    ) -> T:
        if kwargs:
            raise TypeError("Additional generation options are not supported yet")
        response = await self._generate(messages, temperature, response_schema)
        return response_schema.model_validate_json(response.content)
