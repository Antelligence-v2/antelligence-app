"""LLMQueen: the scheduler agent behind the "queen" id. Sees only the board.

Cadence: she speaks on ticks where ``(tick - 1) % every == 0`` (ticks 1, 1+every, ...), so the
first tick always counts; foraging uses ``every=10``, coloring ``every=1``. Her prompt holds ONLY:
the tick, aggregate counts from her observation, worker ``report`` signals seen since her last
turn (sender, group, reason), the group list, the action menu, and her own past signals (policy
state; the scheduler hides self-sent signals). She replies strict JSON::

    {"groups": {"<group_id>": {"goal": "<=120 chars", "allowed": ["<action id>", ...]}}}

Validation: unknown actions are dropped, goals cut to 120 chars, an empty ``allowed`` or a
missing group keeps that group's previous signal. A failed or invalid reply re-emits all
previous signals (so workers keep their last orders) and records why in ``Intent.meta``.
One ``queen`` signal per group, topic ``board``, ``ttl = every``, so orders expire exactly when
the next turn's orders become visible. Use one instance per run (it holds state).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Tuple

from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import NOOP, Intent, LocalView
from antelligence.providers.base import ChatRequest, Provider

MAX_GOAL = 120
MAX_REASON = 120
MAX_REPORTS = 24
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

SYSTEM = (
    "You are the queen of a swarm of workers. You cannot see the world. You only see the board: reports "
    "from workers whose own evidence disagrees with your last orders, and a few aggregate counts. For each "
    "worker group, set a short goal and the list of actions that group may take. If reports show your "
    "orders look wrong, change them; otherwise keep them. Reply with one JSON object and nothing else: "
    '{"groups": {"<group_id>": {"goal": "<at most 120 characters>", "allowed": ["<action id>", ...]}}}'
)


class QueenReplyError(ValueError):
    """The queen's reply does not satisfy the signal contract."""


class LLMQueen:
    def __init__(self, provider: Provider, model: str, *, groups: Mapping[str, Tuple[str, ...]],
                 actions: Mapping[str, str], every: int, max_tokens: int = 300,
                 instructions: str = "") -> None:
        if every < 1 or max_tokens < 1 or not groups or not actions:
            raise ValueError("every and max_tokens must be positive; groups and actions must be non-empty")
        self.provider = provider
        self.model = model
        self.groups = {g: tuple(m) for g, m in groups.items()}
        self.actions = dict(actions)
        self.every = every
        self.max_tokens = max_tokens
        self.instructions = instructions.strip()  # the world's task text, so her goals serve the real objective
        self.system = f"{SYSTEM}\n\nThe workers' task, as they were told it: {self.instructions}" \
            if self.instructions else SYSTEM
        self.previous: Dict[str, Dict[str, Any]] = {}  # group -> {"goal", "allowed"}: her own past signals
        self._seen: set = set()  # report signal ids already shown to her
        self._reports: List[Dict[str, str]] = []  # reports seen since her last turn

    def describe(self) -> Dict[str, Any]:
        return {"policy": "llm_queen", "model": self.model, "provider": self.provider.describe(),
                "groups": {g: len(m) for g, m in sorted(self.groups.items())}, "actions": sorted(self.actions),
                "every": self.every, "max_tokens": self.max_tokens, "instructions": self.instructions}

    def _collect(self, view: LocalView) -> None:
        for s in view.signals:
            if s.kind != "report" or s.id in self._seen:
                continue
            self._seen.add(s.id)
            reason = str(s.payload.get("reason", ""))[:MAX_REASON]
            self._reports.append({"from": s.sender, "group": str(s.payload.get("group", "")), "reason": reason})

    def request(self, view: LocalView) -> ChatRequest:
        counts = view.observation.get("counts", {})
        body = {"tick": view.tick, "counts": counts, "groups": {g: len(m) for g, m in sorted(self.groups.items())},
                "actions": self.actions, "reports": self._reports[-MAX_REPORTS:], "your_previous_orders": self.previous}
        return ChatRequest(model=self.model, messages=({"role": "system", "content": self.system},
                                                       {"role": "user", "content": canonical_json(body)}),
                           max_tokens=self.max_tokens, temperature=0.0, seed=view.seed % 2_147_483_647,
                           response_format={"type": "json_object"})

    def parse(self, content: str) -> Dict[str, Dict[str, Any]]:
        text = content.strip()
        fenced = _FENCE.match(text)
        if fenced:
            text = fenced.group(1)
        try:
            reply = json.loads(text)
        except json.JSONDecodeError as exc:
            raise QueenReplyError(f"not JSON ({exc.msg})") from exc
        raw = reply.get("groups") if isinstance(reply, dict) else None
        if not isinstance(raw, dict):
            raise QueenReplyError("reply needs a 'groups' object")
        orders: Dict[str, Dict[str, Any]] = {}
        for group, order in raw.items():
            if group not in self.groups or not isinstance(order, dict):
                continue
            goal, allowed = order.get("goal"), order.get("allowed")
            if not isinstance(goal, str) or not isinstance(allowed, list):
                continue
            keep = list(dict.fromkeys(a for a in allowed if isinstance(a, str) and a in self.actions))
            if keep:
                orders[group] = {"goal": goal[:MAX_GOAL], "allowed": keep}
        if not orders:
            raise QueenReplyError("no valid group orders")
        return orders

    def _signals(self, orders: Mapping[str, Mapping[str, Any]]) -> Tuple[SignalDraft, ...]:
        return tuple(SignalDraft(kind="queen", topic="board", ttl=self.every,
                                 payload={"group": g, "goal": o["goal"], "allowed": list(o["allowed"])})
                     for g, o in sorted(orders.items()))

    async def decide(self, view: LocalView) -> Intent:
        self._collect(view)
        if (view.tick - 1) % self.every != 0:
            return Intent(NOOP, meta={"policy": "llm_queen", "spoke": False})
        request = self.request(view)
        reports_shown = len(self._reports[-MAX_REPORTS:])
        self._reports = []
        meta: Dict[str, Any] = {"policy": "llm_queen", "spoke": True, "reports_shown": reports_shown}
        try:
            response = await self.provider.complete(request)
            meta.update(response.accounting())
            fresh = self.parse(response.content)
        except Exception as exc:  # keep orders, say why
            meta["kept_previous"] = f"{type(exc).__name__}:{str(exc)[:100]}"
            return Intent(NOOP, emit=self._signals(self.previous), meta=meta)
        merged = {**self.previous, **fresh}
        meta["groups_updated"] = sorted(fresh)
        self.previous = {g: dict(o) for g, o in merged.items()}
        return Intent(NOOP, emit=self._signals(self.previous), meta=meta)
