"""Provider contract: one async chat-completion call with full accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol

from antelligence.kernel.canonical import content_hash, plain


class ProviderError(RuntimeError):
    """The provider failed or returned something we refuse to trust."""


class BudgetExceeded(ProviderError):
    """A call would exceed the run's call or token budget."""


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: tuple
    max_tokens: int = 256
    temperature: float = 0.0
    seed: Optional[int] = None
    response_format: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model is required")
        messages = tuple(plain(dict(m)) for m in self.messages)
        for message in messages:
            if message.get("role") not in ("system", "user", "assistant") or not isinstance(message.get("content"), str):
                raise ValueError("messages need role in system/user/assistant and string content")
        object.__setattr__(self, "messages", messages)
        if self.response_format is not None:
            object.__setattr__(self, "response_format", plain(dict(self.response_format)))
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")

    def payload(self) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": list(self.messages),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        if self.response_format is not None:
            body["response_format"] = self.response_format
        return body

    @property
    def request_hash(self) -> str:
        return content_hash(self.payload())


@dataclass(frozen=True)
class ChatResponse:
    content: str
    model: str
    request_hash: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    response_id: Optional[str] = None
    elapsed_s: float = 0.0
    cached: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    def accounting(self) -> Dict[str, Any]:
        """Provenance for the hashed event log.

        Excludes wall-clock time and cache status, so a replay from cache
        reproduces the live run's trace hash exactly.
        """
        return {
            "model": self.model,
            "request_hash": self.request_hash,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "finish_reason": self.finish_reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {**self.accounting(), "cached": self.cached, "content": self.content, "response_id": self.response_id,
                "elapsed_s": self.elapsed_s, "extra": dict(self.extra)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, cached: bool = False) -> "ChatResponse":
        return cls(content=data["content"], model=data["model"], request_hash=data["request_hash"],
                   prompt_tokens=data["prompt_tokens"], completion_tokens=data["completion_tokens"],
                   finish_reason=data["finish_reason"], response_id=data.get("response_id"),
                   elapsed_s=data.get("elapsed_s", 0.0), cached=cached, extra=data.get("extra") or {})


class Provider(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse: ...

    def describe(self) -> Dict[str, Any]: ...


@dataclass
class Usage:
    calls: int = 0
    cached_calls: int = 0
    failed_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_s: float = 0.0
    by_model: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def add(self, response: ChatResponse) -> None:
        self.calls += 1
        self.cached_calls += int(response.cached)
        self.prompt_tokens += response.prompt_tokens
        self.completion_tokens += response.completion_tokens
        self.elapsed_s += response.elapsed_s
        row = self.by_model.setdefault(response.model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
        row["calls"] += 1
        row["prompt_tokens"] += response.prompt_tokens
        row["completion_tokens"] += response.completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {"calls": self.calls, "cached_calls": self.cached_calls, "failed_calls": self.failed_calls,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens, "elapsed_s": round(self.elapsed_s, 6),
                "by_model": {k: dict(v) for k, v in sorted(self.by_model.items())}}


def messages_digest(messages: List[Mapping[str, Any]]) -> str:
    return content_hash([dict(m) for m in messages])
