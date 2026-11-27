"""Retry policy for provider outages: send the SAME request again, never a different one.

Only :class:`ProviderUnavailable` (HTTP 401/429/5xx or a transport error) is retried. An invalid reply, a spent
budget or a truncated generation is raised untouched on the first try. After ``max_wait_s`` of waiting the last
outage error is raised. ``sleep`` and ``clock`` are injectable so tests run instantly.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict

from antelligence.providers.base import ChatRequest, ChatResponse, Provider, ProviderUnavailable


@dataclass
class RetryPolicy:
    max_wait_s: float = 600.0
    initial_backoff_s: float = 15.0
    factor: float = 2.0
    max_backoff_s: float = 120.0
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep
    clock: Callable[[], float] = time.monotonic
    retries: int = field(default=0, init=False)
    waited_s: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if (self.max_wait_s < 0 or self.initial_backoff_s <= 0 or self.factor < 1
                or self.max_backoff_s < self.initial_backoff_s):
            raise ValueError("retry policy needs max_wait_s >= 0, initial_backoff_s > 0, factor >= 1, "
                             "max_backoff_s >= initial_backoff_s")


class Retrying:
    """Provider wrapper that waits out outages according to a :class:`RetryPolicy`."""

    def __init__(self, inner: Provider, policy: RetryPolicy | None = None) -> None:
        self.inner = inner
        self.policy = policy or RetryPolicy()

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()  # transparent, like Cached and Budgeted

    async def complete(self, request: ChatRequest) -> ChatResponse:
        policy = self.policy
        started = policy.clock()
        delay = policy.initial_backoff_s
        while True:
            try:
                return await self.inner.complete(request)
            except ProviderUnavailable:
                remaining = policy.max_wait_s - (policy.clock() - started)
                if remaining <= 0:
                    raise
                wait = min(delay, remaining)
                policy.retries += 1
                policy.waited_s += wait
                await policy.sleep(wait)
                delay = min(delay * policy.factor, policy.max_backoff_s)
