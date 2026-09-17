import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Sequence, Type, Union
from urllib.parse import quote

import httpx

from ai.llm.base import LLMMessage, LLMProvider, LLMResponse, T

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Use the GenerateContent API; caller supplies credentials and model.

    Credentials are required only when generation is requested. Each call owns
    its HTTP client, so there is no shared client lifecycle or global SDK state.
    Rotate configured keys on HTTP 429 and during bounded transient retries.
    The transient retry budget is shared across all keys for each generation.
    """

    def __init__(
        self,
        api_key: Optional[Union[str, Sequence[str]]] = None,
        model_name: str = "gemini-2.5-flash",
        transport: Optional[httpx.AsyncBaseTransport] = None,
        api_keys: Optional[Sequence[str]] = None,
        request_timeout: float = 90.0,
        max_transient_retries: int = 2,
    ):
        if request_timeout <= 0 or max_transient_retries < 0:
            raise ValueError("Timeout must be positive and retry limit nonnegative")
        raw_keys = api_keys if api_keys is not None else api_key
        keys: List[str] = []
        if isinstance(raw_keys, str):
            keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        elif isinstance(raw_keys, (list, tuple)):
            keys = [k.strip() for k in raw_keys if isinstance(k, str) and k.strip()]

        self._api_keys = keys
        self._current_index = 0
        self._model_name = model_name
        self._transport = transport
        self._request_timeout = request_timeout
        self._max_transient_retries = max_transient_retries

    @property
    def _api_key(self) -> Optional[str]:
        if self._api_keys:
            return self._api_keys[self._current_index]
        return None

    @property
    def api_keys(self) -> List[str]:
        return list(self._api_keys)

    async def _generate(
        self, messages: List[LLMMessage], temperature: float,
        response_schema: Optional[Type[T]] = None,
    ) -> LLMResponse:
        if not self._api_keys:
            raise ValueError("GEMINI_API_KEY is required for LLM generation")
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

        total_keys = len(self._api_keys)
        exhausted_keys = set()
        transient_retries = 0
        last_error_response = None
        raw = None
        key_index = self._current_index

        def advance_key():
            nonlocal key_index
            for offset in range(1, total_keys + 1):
                index = (key_index + offset) % total_keys
                if index not in exhausted_keys:
                    key_index = index
                    self._current_index = index
                    return

        while len(exhausted_keys) < total_keys:
            current_key = self._api_keys[key_index]
            retry_error = None
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(self._request_timeout, connect=10.0),
            ) as client:
                try:
                    response = await client.post(
                        url, headers={"x-goog-api-key": current_key}, json=body,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    retry_error = exc
                if retry_error is None and response.status_code in (408, 500, 502, 503, 504):
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        retry_error = exc
                if retry_error is not None:
                    if transient_retries >= self._max_transient_retries:
                        raise retry_error
                    delay = 2 ** transient_retries + random.uniform(0, 0.25)
                    transient_retries += 1
                    advance_key()
                    logger.warning(
                        "Transient Gemini error (%s); retry %s/%s in %.2fs",
                        type(retry_error).__name__, transient_retries,
                        self._max_transient_retries, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if response.status_code == 429:
                    exhausted_keys.add(key_index)
                    last_error_response = response
                    logger.warning(
                        "Gemini API key %s/%s hit quota/rate limit (HTTP 429). Rotating to next key...",
                        key_index + 1, total_keys,
                    )
                    advance_key()
                    continue
                response.raise_for_status()
                raw = response.json()
                self._current_index = key_index
                break
        else:
            if last_error_response is not None:
                last_error_response.raise_for_status()
            raise httpx.HTTPStatusError(
                f"All {total_keys} Gemini API keys exhausted their quota (HTTP 429)",
                request=response.request,
                response=response,
            )

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
