"""Usage ledger: one JSONL row per physical model call, plus prices and a chat wrapper.

Run context (run/arm/world/seed/condition) is set with :func:`ledger_context`;
the role ("worker", "queen", "escalation", "every_agent", "calibration") is
fixed per wrapper instance. Cache hits make no physical call and write no row.
The writer never sees an API key; ``redact`` strings are scrubbed from error
text anyway. Default path ``ledger/v4-pilot-usage.jsonl`` is gitignored.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple, Union

from antelligence.providers.base import ChatRequest, ChatResponse, Provider, ProviderError

DEFAULT_LEDGER_PATH = Path("ledger/v4-pilot-usage.jsonl")
ROLES = ("worker", "queen", "escalation", "every_agent", "calibration")
CONTEXT_TAGS = ("run", "arm", "world", "seed", "condition")
ROW_FIELDS = ("utc", *CONTEXT_TAGS, "role", "backend", "model", "served_model", "request_hash",
              "input_tokens", "output_tokens", "latency_s", "cost_usd")

# USD per million (input, output) tokens. Laya is local; vLLM pod calls cost $0 per call
# (the pod script bills pod time separately). Jev output is free.
PRICES: Dict[str, Tuple[float, float]] = {
    "deepseek/deepseek-v4.1-flash": (0.106, 0.513),
    "jev-1.13.0": (0.042, 0.0),
    "convaiinnovations/laya-typed-decisions": (0.0, 0.0),
    "laya-rl-agent": (0.0, 0.0),
}

_CONTEXT: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("ledger_context", default={})


@contextlib.contextmanager
def ledger_context(**tags: Any) -> Iterator[Dict[str, Any]]:
    """Tag every ledger row written inside the block (nests; inner tags override)."""
    unknown = set(tags) - set(CONTEXT_TAGS)
    if unknown:
        raise ValueError(f"unknown ledger tags: {sorted(unknown)}")
    merged = {**_CONTEXT.get(), **tags}
    token = _CONTEXT.set(merged)
    try:
        yield merged
    finally:
        _CONTEXT.reset(token)


def current_tags() -> Dict[str, Any]:
    return dict(_CONTEXT.get())


def price_for(model: str) -> Tuple[float, float]:
    """(input, output) USD per million tokens; unknown models raise rather than cost $0 silently."""
    try:
        return PRICES[model]
    except KeyError:
        raise KeyError(f"no price for model {model!r}; pass an explicit price") from None


def cost_usd(input_tokens: int, output_tokens: int, price: Tuple[float, float]) -> float:
    return round((input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 10)


class LedgerWriter:
    """Append-only JSONL ledger. Thread-safe; one row per physical call."""

    def __init__(self, path: Union[str, Path] = DEFAULT_LEDGER_PATH, *, redact: Iterable[str] = ()) -> None:
        self.path = Path(path)
        self._redact = tuple(s for s in redact if s)
        self._lock = threading.Lock()

    def add_redaction(self, *secrets: str) -> None:
        """Scrub more strings from error text (keys that are only read once an arm needs them)."""
        self._redact += tuple(s for s in secrets if s)

    def _clean(self, text: str) -> str:
        for secret in self._redact:
            text = text.replace(secret, "***")
        return text

    def write(self, *, role: str, backend: str, model: str, served_model: Optional[str], request_hash: str,
              input_tokens: int = 0, output_tokens: int = 0, latency_s: float = 0.0, cost_usd: float = 0.0,
              error: Optional[str] = None) -> Dict[str, Any]:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        tags = _CONTEXT.get()
        row: Dict[str, Any] = {"utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
        row.update({tag: tags.get(tag) for tag in CONTEXT_TAGS})
        row.update(role=role, backend=backend, model=model, served_model=served_model, request_hash=request_hash,
                   input_tokens=int(input_tokens), output_tokens=int(output_tokens),
                   latency_s=round(float(latency_s), 3), cost_usd=float(cost_usd))
        if error is not None:
            row["error"] = self._clean(error)[:240]
        line = json.dumps(row, sort_keys=True, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return row

    def rows(self) -> list:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def total_cost(self) -> float:
        return round(sum(r.get("cost_usd", 0.0) for r in self.rows()), 10)


class LedgeredChat:
    """Chat provider wrapper: one row per physical call plus the served-model identity check.

    Put it innermost (under ``Cached``/``Budgeted``) so cache hits write nothing.
    ``expected_model`` is what the provider must report (``prefix=True`` accepts
    a version suffix). Cost is the provider-reported ``extra['cost']`` when
    present, else the price table (``price`` overrides the lookup).
    """

    def __init__(self, inner: Provider, writer: LedgerWriter, *, role: str, expected_model: str,
                 backend: str = "nous", prefix: bool = False, price: Optional[Tuple[float, float]] = None) -> None:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        self.inner, self.writer, self.role = inner, writer, role
        self.expected_model, self.backend, self.prefix = expected_model, backend, prefix
        self.price = price if price is not None else price_for(expected_model)

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    def _row(self, request: ChatRequest, **kw: Any) -> None:
        self.writer.write(role=self.role, backend=self.backend, model=request.model,
                          request_hash=request.request_hash, **kw)

    async def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            response = await self.inner.complete(request)
        except Exception as exc:
            self._row(request, served_model=None, error=f"{type(exc).__name__}: {exc}")
            raise
        ok = response.model.startswith(self.expected_model) if self.prefix else response.model == self.expected_model
        reported = response.extra.get("cost") if response.extra else None
        cost = float(reported) if isinstance(reported, (int, float)) else cost_usd(
            response.prompt_tokens, response.completion_tokens, self.price)
        self._row(request, served_model=response.model, input_tokens=response.prompt_tokens,
                  output_tokens=response.completion_tokens, latency_s=response.elapsed_s, cost_usd=cost,
                  error=None if ok else "served model identity mismatch")
        if not ok:
            raise ProviderError(f"served model {response.model!r} is not the expected {self.expected_model!r}")
        return response
