"""The LiteLLM proxy connection, configured exactly like the legacy simulators.

Legacy code (``backend/simulation.py``, ``backend/nanobot_simulation.py``) calls
``{LITELLM_API_BASE}/chat/completions`` with ``IO_SECRET_KEY`` as the bearer
token. This module builds the same connection for engine runs, wrapped in a
per-run response cache so a model-driven run stays replayable: replaying a run
answers every model call from its cache and never touches the network.

Like legacy, it is lenient about what the proxy serves: model aliases and
``finish_reason="length"`` on one-word replies are accepted.

Limits: each run is capped at ``ANTELLIGENCE_LLM_MAX_CALLS`` model calls (default
20,000) and, if set, ``ANTELLIGENCE_LLM_MAX_TOKENS`` tokens; calls past the cap fall
back to the agent's rule and count as failed. ``ANTELLIGENCE_LLM_MODELS`` (comma
separated) restricts which models a run may name. ``ANTELLIGENCE_OFFLINE=1`` turns
LLM runs off entirely; replay still works, since it needs no key.

LLM runs are host-bound: the model's answers live in this host's per-run cache
(``<data dir>/llm_cache/<run_id>.jsonl``), not in the bundle, so a bundle verifies
only where that cache file is present.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from antelligence.providers.openai_compat import OpenAICompatProvider
from antelligence.providers.wrappers import Budgeted, Cached

DEFAULT_API_BASE = "http://host.orb.internal:4000/v1"  # legacy LITELLM_API_BASE
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"  # legacy default
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")

# Legacy keeps its keys in backend/.env (loaded by backend/main.py); load it here too so the
# engine API finds them however it is started. Variables already set always win.
ENV_FILE = Path(__file__).resolve().parents[2] / "backend" / ".env"

_cache_dir: Optional[Path] = None
_env_loaded = False
_offline = contextvars.ContextVar("antelligence_llm_offline", default=False)


class LLMUnavailable(ValueError):
    """Model-driven agents were requested but no LiteLLM key is configured."""


def configure(cache_dir: Optional[Path]) -> None:
    """Where per-run response caches live (the engine data dir sets this)."""
    global _cache_dir
    _cache_dir = Path(cache_dir) if cache_dir is not None else None


@contextlib.contextmanager
def offline() -> Iterator[None]:
    """Answer model calls from run caches only (used by replay)."""
    token = _offline.set(True)
    try:
        yield
    finally:
        _offline.reset(token)


def _load_env() -> None:
    global _env_loaded
    if not _env_loaded:
        _env_loaded = True
        if ENV_FILE.is_file():
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE, override=False)


_TRUE = {"1", "true", "yes", "on"}
DEFAULT_MAX_CALLS = 20_000


def offline_mode() -> bool:
    """ANTELLIGENCE_OFFLINE: the process never calls a model (backend/main.py OFFLINE_MODE)."""
    return os.getenv("ANTELLIGENCE_OFFLINE", "").strip().lower() in _TRUE


def api_key() -> str:
    _load_env()
    if offline_mode():
        return ""
    return os.getenv("IO_SECRET_KEY") or os.getenv("LITELLM_API_KEY") or ""


def _int_env(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    return int(value) if value.isdigit() and int(value) > 0 else None


def max_calls() -> int:
    return _int_env("ANTELLIGENCE_LLM_MAX_CALLS") or DEFAULT_MAX_CALLS


def allowed_models() -> Optional[frozenset]:
    """Models runs may name (ANTELLIGENCE_LLM_MODELS), or None for any the proxy routes."""
    names = [m.strip() for m in os.getenv("ANTELLIGENCE_LLM_MODELS", "").split(",") if m.strip()]
    return frozenset(names) if names else None


def api_base() -> str:
    _load_env()
    return os.getenv("LITELLM_API_BASE") or DEFAULT_API_BASE


def available() -> bool:
    return bool(api_key())


def check_model(model: str) -> str:
    if not isinstance(model, str) or not MODEL_PATTERN.match(model):
        raise ValueError("model must be a model name like 'meta-llama/Llama-3.3-70B-Instruct'")
    allowed = allowed_models()
    if allowed is not None and model not in allowed:
        raise ValueError(f"model {model!r} is not allowed here; choose one of: {', '.join(sorted(allowed))}")
    return model


class _Proxy:
    """The proxy, described by what it is rather than where it is.

    The description goes into the hashed run config; the endpoint and allowlist
    are deployment details, so moving the proxy must not invalidate past runs.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def describe(self) -> Dict[str, Any]:
        return {"provider": "litellm"}

    async def complete(self, request: Any) -> Any:
        return await self.inner.complete(request)


def provider_for_run(run_id: str) -> Budgeted:
    """The LiteLLM provider for one run, behind that run's response cache."""
    replaying = _offline.get()
    key = api_key()
    if not key and not replaying:
        raise LLMUnavailable("LLM agents need IO_SECRET_KEY (or LITELLM_API_KEY) set for the backend")
    inner = _Proxy(OpenAICompatProvider(api_base(), api_key=key or None, allowed_models=allowed_models(),
                                        timeout_s=30.0, max_concurrency=8, require_model_match=False,
                                        require_stop=False))
    path = None
    if _cache_dir is not None:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", run_id)
        path = _cache_dir / f"{safe}.jsonl"
    # The budget sits outside the cache, so a replay trips it at the same call as the live run.
    return Budgeted(Cached(inner, path, offline=replaying), max_calls=max_calls(),
                    max_tokens=_int_env("ANTELLIGENCE_LLM_MAX_TOKENS"))
