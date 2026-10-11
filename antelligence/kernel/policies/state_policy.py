"""StateChatPolicy: the every-agent arm (DS-all, Q-all).

Same SensedState text and the same action list as the framework workers -- but no REPORT, no
queen, no checks. Options are listed in a seeded shuffle (``view.seed``) so list order does not
bias the model. One short JSON answer ``{"action": "<id>"}``; anything off-list, unparsable or a
provider failure becomes NOOP with the reason in ``Intent.meta`` (never silent).
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List

from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.decision import Sensor
from antelligence.kernel.types import NOOP, Intent, LocalView
from antelligence.providers.base import ChatRequest, Provider

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

SYSTEM = ("You control one agent. Read its state and choose exactly one action from the list. "
          'Reply with one JSON object and nothing else, like {"action": "<id>"}.')


class StateChatPolicy:
    def __init__(self, provider: Provider, model: str, sensor: Sensor, *, max_tokens: int = 64) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self.provider = provider
        self.model = model
        self.sensor = sensor
        self.max_tokens = max_tokens

    def describe(self) -> Dict[str, Any]:
        return {"policy": "state_chat", "model": self.model, "provider": self.provider.describe(),
                "sensor": self.sensor.describe(), "max_tokens": self.max_tokens}

    def request(self, view: LocalView) -> ChatRequest:
        sensed = self.sensor.sense(view)
        order: List[str] = sorted(sensed.actions)
        random.Random(view.seed).shuffle(order)
        menu = "\n".join(f"- {a}: {sensed.actions[a]}" for a in order)
        user = f"{sensed.text}\n\nActions:\n{menu}\n\nReply with JSON: " + canonical_json({"action": "<id>"})
        return ChatRequest(model=self.model, messages=({"role": "system", "content": SYSTEM},
                                                       {"role": "user", "content": user}),
                           max_tokens=self.max_tokens, temperature=0.0, seed=view.seed % 2_147_483_647,
                           response_format={"type": "json_object"})

    async def decide(self, view: LocalView) -> Intent:
        sensed = self.sensor.sense(view)
        meta: Dict[str, Any] = {"policy": "state_chat"}
        try:
            response = await self.provider.complete(self.request(view))
        except Exception as exc:
            return Intent(NOOP, meta={**meta, "reason": f"provider:{type(exc).__name__}:{str(exc)[:100]}"})
        meta.update(response.accounting())
        text = response.content.strip()
        fenced = _FENCE.match(text)
        if fenced:
            text = fenced.group(1)
        try:
            reply = json.loads(text)
        except json.JSONDecodeError:
            return Intent(NOOP, meta={**meta, "reason": "reply_not_json"})
        action = reply.get("action") if isinstance(reply, dict) else None
        if not isinstance(action, str) or action not in sensed.actions:
            return Intent(NOOP, meta={**meta, "reason": "action_not_offered"})
        return Intent(action, meta={**meta, "answer": action})
