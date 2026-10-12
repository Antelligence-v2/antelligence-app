"""The LiteLLM proxy connection, configured exactly like the legacy simulators.

Legacy code (``backend/simulation.py``, ``backend/nanobot_simulation.py``) calls
``{LITELLM_API_BASE}/chat/completions`` with ``IO_SECRET_KEY`` as the bearer
token. This module builds the same connection for engine runs, wrapped in a
per-run response cache so a model-driven run stays replayable: replaying a run
answers every model call from its cache and never touches the network.

Like legacy, it is lenient about what the proxy serves: model aliases and
``finish_reason="length"`` on one-word replies are accepted.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
import re
from pathlib import Path
from typing import Iterator, Optional

from antelligence.providers.openai_compat import OpenAICompatProvider
from antelligence.providers.wrappers import Cached

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


def api_key() -> str:
    _load_env()
    return os.getenv("IO_SECRET_KEY") or os.getenv("LITELLM_API_KEY") or ""


def api_base() -> str:
    _load_env()
    return os.getenv("LITELLM_API_BASE") or DEFAULT_API_BASE


def available() -> bool:
    return bool(api_key())


def check_model(model: str) -> str:
    if not isinstance(model, str) or not MODEL_PATTERN.match(model):
        raise ValueError("model must be a model name like 'meta-llama/Llama-3.3-70B-Instruct'")
    return model


def provider_for_run(run_id: str) -> Cached:
    """The LiteLLM provider for one run, behind that run's response cache."""
    replaying = _offline.get()
    key = api_key()
    if not key and not replaying:
        raise LLMUnavailable("LLM agents need IO_SECRET_KEY (or LITELLM_API_KEY) set for the backend")
    inner = OpenAICompatProvider(api_base(), api_key=key or None, timeout_s=30.0, max_concurrency=8,
                                 require_model_match=False, require_stop=False)
    path = None
    if _cache_dir is not None:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", run_id)
        path = _cache_dir / f"{safe}.jsonl"
    return Cached(inner, path, offline=replaying)
