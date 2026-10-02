"""One HTTP client for every OpenAI-compatible endpoint.

Covers local llama.cpp servers, a LiteLLM proxy, Nous Portal and similar.
Configuration is explicit (no environment reads here); the caller decides the
base URL, key and model allowlist. Responses are refused, never repaired, when
the served model differs from the requested one, generation was truncated, or
token usage is missing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, FrozenSet, Iterable, Optional

import httpx

from antelligence.providers.base import ChatRequest, ChatResponse, ProviderError

MAX_RESPONSE_BYTES = 2_000_000


class OpenAICompatProvider:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        allowed_models: Optional[Iterable[str]] = None,
        timeout_s: float = 120.0,
        max_concurrency: int = 4,
        require_model_match: bool = True,
        require_stop: bool = True,
        extra_body: Optional[Dict[str, Any]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.allowed_models: Optional[FrozenSet[str]] = None if allowed_models is None else frozenset(allowed_models)
        self.timeout_s = timeout_s
        self.require_model_match = require_model_match
        self.require_stop = require_stop
        self.extra_body = dict(extra_body or {})
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._transport = transport
        self.max_concurrency = max_concurrency

    def describe(self) -> Dict[str, Any]:
        return {"provider": "openai_compat", "base_url": self.base_url,
                "allowed_models": None if self.allowed_models is None else sorted(self.allowed_models)}

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if self.allowed_models is not None and request.model not in self.allowed_models:
            raise ProviderError(f"model {request.model!r} is not allowlisted")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = {**self.extra_body, **request.payload()}
        async with self._semaphore:
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False, trust_env=False,
                                             transport=self._transport) as client:
                    response = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            except httpx.HTTPError as exc:
                raise ProviderError(f"transport error: {type(exc).__name__}: {exc}") from exc
            elapsed = time.monotonic() - start
        if response.status_code != 200:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:200]}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ProviderError("response exceeds size limit")
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage = data["usage"]
            prompt_tokens, completion_tokens = usage["prompt_tokens"], usage["completion_tokens"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"malformed response: {exc}") from exc
        served = data.get("model") or ""
        if self.require_model_match and served != request.model:
            raise ProviderError(f"served model {served!r} differs from requested {request.model!r}")
        finish = choice.get("finish_reason") or "unknown"
        if self.require_stop and finish != "stop":
            raise ProviderError(f"generation did not finish normally ({finish})")
        if not isinstance(content, str):
            raise ProviderError("missing message content")
        for value in (prompt_tokens, completion_tokens):
            if type(value) is not int or value < 0:
                raise ProviderError("token usage missing or invalid")
        return ChatResponse(content=content, model=served or request.model, request_hash=request.request_hash,
                            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, finish_reason=finish,
                            response_id=data.get("id"), elapsed_s=elapsed,
                            extra={"system_fingerprint": data.get("system_fingerprint")})
