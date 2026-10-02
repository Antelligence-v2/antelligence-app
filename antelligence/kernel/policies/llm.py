"""LLMPolicy: one language-model agent brain usable in every world.

The world supplies the action vocabulary and signal kinds; the policy renders
the agent's LocalView (and nothing else) into a prompt, and parses a strict
JSON reply into an :class:`Intent`. Replies are validated, never repaired:

* ``action`` must be declared; ``params`` must be an object;
* at most ``max_emit`` signals, each of a declared kind with ``ttl <= max_ttl``;
* ``cites`` must name memory records that are actually in the view (no
  hallucinated evidence ids).

On a provider or parse failure the policy uses ``fallback`` (if configured) and
records why in ``Intent.meta``; otherwise it raises and the scheduler fails the
agent closed to a no-op. Fallbacks are never silent.
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, Callable, Dict, List, Mapping, Optional

from antelligence.kernel.canonical import canonical_json, content_hash
from antelligence.kernel.signal import SignalDraft, SignalError
from antelligence.kernel.types import Intent, LocalView, Policy
from antelligence.providers.base import ChatRequest, Provider, ProviderError

MAX_RATIONALE = 300
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class ReplyError(ValueError):
    """The model reply does not satisfy the intent contract."""


Render = Callable[[LocalView], Mapping[str, Any]]

DEFAULT_SYSTEM = (
    "You are one agent in a swarm. You only know what is in your local view: your own observation, "
    "signals other agents left nearby, and evidence records the swarm has admitted. Do not assume anything "
    "else about the world. Choose exactly one action from the allowed list. You may leave signals for "
    "other agents. Cite evidence record ids only if your action relies on them. Reply with one JSON object "
    "and nothing else."
)


def default_render(view: LocalView) -> Dict[str, Any]:
    return {
        "agent": view.agent_id,
        "tick": view.tick,
        "observation": view.observation,
        "signals": [
            {"id": s.id[:16], "kind": s.kind, "from": s.sender, "pos": list(s.pos) if s.pos else None,
             "topic": s.topic, "payload": s.payload, "age": view.tick - s.emitted_at}
            for s in view.signals
        ],
        "evidence": [
            {"id": r.id, "subject": r.subject, "kind": r.kind, "body": r.body}
            for r in view.memory
        ],
    }


class LLMPolicy:
    def __init__(
        self,
        provider: Provider,
        model: str,
        *,
        actions: Mapping[str, str],
        signal_kinds: Optional[Mapping[str, str]] = None,
        system: str = DEFAULT_SYSTEM,
        render: Render = default_render,
        max_tokens: int = 256,
        temperature: float = 0.0,
        max_emit: int = 2,
        max_ttl: int = 20,
        json_mode: bool = True,
        fallback: Optional[Policy] = None,
        name: str = "llm",
    ) -> None:
        if not actions:
            raise ValueError("at least one action is required")
        self.provider = provider
        self.model = model
        self.actions = dict(actions)
        self.signal_kinds = dict(signal_kinds or {})
        self.system = system
        self.render = render
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_emit = max_emit
        self.max_ttl = max_ttl
        self.json_mode = json_mode
        self.fallback = fallback
        self.name = name

    def describe(self) -> Dict[str, Any]:
        return {
            "policy": self.name,
            "model": self.model,
            "provider": self.provider.describe(),
            "actions": sorted(self.actions),
            "signal_kinds": sorted(self.signal_kinds),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_emit": self.max_emit,
            "system_hash": content_hash(self.system)[:16],
            "fallback": None if self.fallback is None else self.fallback.describe(),
        }

    def messages(self, view: LocalView) -> List[Dict[str, str]]:
        contract = {
            "allowed_actions": self.actions,
            "signal_kinds": self.signal_kinds,
            "reply_format": {
                "action": "one of allowed_actions",
                "params": "object of action parameters",
                "emit": f"list (max {self.max_emit}) of {{kind, pos:[x,y] or topic, payload:{{}}, ttl<= {self.max_ttl}}}",
                "cites": "list of evidence ids your action relies on",
                "rationale": f"short reason (<= {MAX_RATIONALE} chars)",
            },
        }
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": canonical_json({"view": self.render(view), "contract": contract})},
        ]

    def request(self, view: LocalView) -> ChatRequest:
        return ChatRequest(
            model=self.model,
            messages=tuple(self.messages(view)),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            seed=view.seed % 2_147_483_647,
            response_format={"type": "json_object"} if self.json_mode else None,
        )

    async def decide(self, view: LocalView) -> Intent:
        request = self.request(view)
        try:
            response = await self.provider.complete(request)
        except ProviderError as exc:
            return await self._fallback(view, f"provider:{type(exc).__name__}", {"request_hash": request.request_hash})
        meta = {"policy": self.name, **response.accounting()}
        try:
            return self.parse(response.content, view, meta)
        except ReplyError as exc:
            return await self._fallback(view, f"reply:{exc}", meta)

    async def _fallback(self, view: LocalView, reason: str, meta: Mapping[str, Any]) -> Intent:
        if self.fallback is None:
            raise ReplyError(reason)
        result = self.fallback.decide(view)
        if inspect.isawaitable(result):
            result = await result
        return Intent(action=result.action, params=result.params, emit=result.emit, rationale=result.rationale,
                      cites=result.cites, meta={**meta, **dict(result.meta), "fallback": reason[:200]})

    def parse(self, content: str, view: LocalView, meta: Mapping[str, Any]) -> Intent:
        text = content.strip()
        fenced = _FENCE.match(text)
        if fenced:
            text = fenced.group(1)
        try:
            reply = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReplyError(f"not JSON ({exc.msg})") from exc
        if not isinstance(reply, dict):
            raise ReplyError("reply must be a JSON object")
        unknown = set(reply) - {"action", "params", "emit", "cites", "rationale"}
        if unknown:
            raise ReplyError(f"unknown fields {sorted(unknown)}")
        action = reply.get("action")
        if action not in self.actions:
            raise ReplyError(f"action {action!r} not allowed")
        params = reply.get("params", {})
        if not isinstance(params, dict):
            raise ReplyError("params must be an object")
        emit_raw = reply.get("emit", [])
        if not isinstance(emit_raw, list) or len(emit_raw) > self.max_emit:
            raise ReplyError(f"emit must be a list of at most {self.max_emit}")
        drafts = [self._draft(item) for item in emit_raw]
        cites = reply.get("cites", [])
        known = {r.id for r in view.memory}
        if not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
            raise ReplyError("cites must be a list of strings")
        hallucinated = [c for c in cites if c not in known]
        if hallucinated:
            raise ReplyError("cites evidence not in view")
        rationale = reply.get("rationale")
        if rationale is not None and not isinstance(rationale, str):
            raise ReplyError("rationale must be a string")
        return Intent(action=action, params=params, emit=tuple(drafts), cites=tuple(dict.fromkeys(cites)),
                      rationale=None if rationale is None else rationale[:MAX_RATIONALE], meta=meta)

    def _draft(self, item: Any) -> SignalDraft:
        if not isinstance(item, dict):
            raise ReplyError("each emit entry must be an object")
        kind = item.get("kind")
        if kind not in self.signal_kinds:
            raise ReplyError(f"signal kind {kind!r} not allowed")
        ttl = item.get("ttl", 1)
        if not isinstance(ttl, int) or isinstance(ttl, bool) or not 1 <= ttl <= self.max_ttl:
            raise ReplyError("ttl out of range")
        pos = item.get("pos")
        try:
            return SignalDraft(kind=kind, pos=tuple(pos) if isinstance(pos, list) else pos, topic=item.get("topic"),
                               payload=item.get("payload") or {}, ttl=ttl)
        except (SignalError, TypeError, ValueError) as exc:
            raise ReplyError(f"bad signal: {exc}") from exc
