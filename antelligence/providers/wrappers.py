"""Composable provider wrappers: offline fake, replay cache, budget + accounting.

Typical stack for an experiment::

    Budgeted(Cached(OpenAICompatProvider(...), path), max_calls=..., max_tokens=...)

``Cached`` makes a run replayable: the same request hash returns the same
content, so the event log (and trace hash) can be reproduced without calling
the model again.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from antelligence.kernel.canonical import canonical_json
from antelligence.providers.base import BudgetExceeded, ChatRequest, ChatResponse, Provider, ProviderError, Usage

Responder = Callable[[ChatRequest], Union[str, ChatResponse]]


class FakeProvider:
    """Deterministic offline provider. ``responder`` maps a request to content."""

    def __init__(self, responder: Responder, *, model: Optional[str] = None, latency_s: float = 0.0) -> None:
        self.responder = responder
        self.model = model
        self.latency_s = latency_s
        self.requests: list = []

    def describe(self) -> Dict[str, Any]:
        return {"provider": "fake", "model": self.model}

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        result = self.responder(request)
        if isinstance(result, ChatResponse):
            return result
        if not isinstance(result, str):
            raise ProviderError("fake responder must return str or ChatResponse")
        prompt_chars = sum(len(m["content"]) for m in request.messages)
        return ChatResponse(content=result, model=self.model or request.model, request_hash=request.request_hash,
                            prompt_tokens=max(1, prompt_chars // 4), completion_tokens=max(1, len(result) // 4),
                            finish_reason="stop", response_id=f"fake-{request.request_hash[:12]}")


class Cached:
    """Request-hash keyed cache; optionally persisted as append-only JSONL."""

    def __init__(self, inner: Provider, path: Optional[Union[str, Path]] = None, *, offline: bool = False) -> None:
        self.inner = inner
        self.path = Path(path) if path is not None else None
        self.offline = offline
        self._store: Dict[str, dict] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        if self.path is not None and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._store[row["request_hash"]] = row

    def __len__(self) -> int:
        return len(self._store)

    def describe(self) -> Dict[str, Any]:
        # Transparent: caching changes where content comes from, not what it is,
        # so a cached replay must share the live run's config hash.
        return self.inner.describe()

    async def complete(self, request: ChatRequest) -> ChatResponse:
        key = request.request_hash
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:  # identical concurrent requests hit the model once
            if key in self._store:
                return ChatResponse.from_dict(self._store[key], cached=True)
            if self.offline:
                raise ProviderError(f"cache miss in offline mode ({key[:12]})")
            response = await self.inner.complete(request)
            row = response.to_dict()
            row["cached"] = False
            self._store[key] = row
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(canonical_json(row) + "\n")
            return response


def _reservation(request: ChatRequest) -> int:
    """Worst-case tokens for a call: estimated prompt (~4 chars/token) + max completion."""
    prompt_chars = sum(len(m["content"]) for m in request.messages)
    return -(-prompt_chars // 4) + request.max_tokens


class Budgeted:
    """Hard caps on calls and tokens for one run, plus usage accounting.

    Before each call the wrapper reserves that call's worst case (estimated
    prompt tokens + ``max_tokens``) alongside every call still in flight, and
    refuses the call if the reservations could exceed ``max_tokens``. Concurrent
    calls therefore cannot overshoot the token cap; only a prompt that tokenizes
    worse than the estimate can.
    """

    def __init__(self, inner: Provider, *, max_calls: Optional[int] = None, max_tokens: Optional[int] = None) -> None:
        self.inner = inner
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.usage = Usage()
        self._in_flight = 0
        self._reserved_tokens = 0

    def describe(self) -> Dict[str, Any]:
        # Transparent: a budget only matters when it trips, and every trip is
        # recorded in the event log as a logged fallback or policy failure.
        return self.inner.describe()

    def limits(self) -> Dict[str, Any]:
        return {"max_calls": self.max_calls, "max_tokens": self.max_tokens}

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if self.max_calls is not None and self.usage.calls + self.usage.failed_calls + self._in_flight >= self.max_calls:
            raise BudgetExceeded(f"call budget of {self.max_calls} exhausted")
        reservation = _reservation(request)
        if self.max_tokens is not None and (
                self.usage.total_tokens + self._reserved_tokens + reservation > self.max_tokens):
            raise BudgetExceeded(f"token budget of {self.max_tokens} cannot cover this call "
                                 f"({reservation} reserved, {self.usage.total_tokens} used, "
                                 f"{self._reserved_tokens} in flight)")
        self._in_flight += 1
        self._reserved_tokens += reservation
        try:
            response = await self.inner.complete(request)
        except Exception:
            self.usage.failed_calls += 1
            raise
        finally:
            self._in_flight -= 1
            self._reserved_tokens -= reservation
        self.usage.add(response)
        return response
