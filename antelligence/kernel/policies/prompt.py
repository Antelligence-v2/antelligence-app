"""Free-text model calls for ported legacy agents.

Legacy agents ask for one word ("toward", "explore", ...) or a loose JSON blob
and map the answer onto a rule behavior, falling back when the reply is
unusable. :func:`ask` makes that call through any engine provider and returns
the reply text plus provenance for the event log; :func:`one_word` adds the
legacy word parsing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from antelligence.kernel.types import PROVIDER_ERROR  # noqa: F401 (re-exported for policies)
from antelligence.providers.base import ChatRequest, Provider, ProviderError

logger = logging.getLogger(__name__)


async def ask(provider: Provider, model: str, system: str, user: str, *, temperature: float,
              max_tokens: int, seed: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
    """One chat call. Raises ``ProviderError`` on transport or contract failure.

    Pass the decision's ``seed`` (``view.seed``): it makes every decision its own
    request, so an agent that sees the same prompt twice gets a fresh sample (as
    legacy did) instead of the run cache's earlier answer. The cache then only
    serves replay.
    """
    request = ChatRequest(model=model, messages=({"role": "system", "content": system},
                                                 {"role": "user", "content": user}),
                          max_tokens=max_tokens, temperature=temperature,
                          seed=None if seed is None else seed % 2**31)
    try:
        response = await provider.complete(request)
    except ProviderError as exc:
        logger.warning("model call failed (%s): %s", model, exc)
        raise
    return response.content, response.accounting()


def one_word(text: str, allowed: Sequence[str]) -> Optional[str]:
    """The legacy parse: the stripped, lower-cased reply if it is an allowed word."""
    word = text.strip().strip(".'\"`").lower()
    return word if word in allowed else None


def json_object(text: str) -> Optional[Dict[str, Any]]:
    """The legacy parse: the outermost ``{...}`` in the reply, if it is a JSON object."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
