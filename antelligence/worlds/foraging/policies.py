"""Foraging agent brains.

:class:`ChainForager` is the E13 target logic as a rule policy: it FOLLOWs the
best target it knows about and otherwise SWEEPs. "Knows" is strictly local:
its own view, signals it senses, and admitted memory records. When it follows
a remembered target it cites the record, so the evidence gate can block it if
the record went stale.

``LLM_ACTIONS`` / ``LLM_SIGNAL_KINDS`` configure a kernel ``LLMPolicy`` for the
same world.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import Intent, LocalView
from antelligence.worlds.foraging.world import FOLLOW, SWEEP

LLM_ACTIONS = {
    FOLLOW: 'walk one step toward params.target = [x, y] (a food you see, carry or remember, or the nest)',
    SWEEP: "continue your systematic search pattern",
}
LLM_SIGNAL_KINDS = {"found": "a food sighting: pos=[x, y], payload={\"food\": index}"}


class ChainForager:
    def __init__(self, *, announce: bool = False, use_memory: bool = False, use_signals: bool = False,
                 signal_ttl: int = 30) -> None:
        self.announce = announce
        self.use_memory = use_memory
        self.use_signals = use_signals
        self.signal_ttl = signal_ttl

    def describe(self) -> Dict[str, Any]:
        return {"policy": "chain_forager", "announce": self.announce, "use_memory": self.use_memory,
                "use_signals": self.use_signals, "signal_ttl": self.signal_ttl}

    def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        need = obs["next_needed"]
        nest = obs["nest"]
        visible = [(f[0], f[1], f[2]) for f in obs["visible_foods"]]
        carrying = obs["carrying"]
        emit = ()
        if self.announce and visible and not carrying:
            emit = tuple(SignalDraft(kind="found", pos=(x, y), payload={"food": i}, ttl=self.signal_ttl)
                         for x, y, i in visible)

        if any(c[2] == need for c in carrying):
            return Intent(FOLLOW, {"target": nest}, emit=emit, rationale="deliver next-needed food")

        for x, y, i in visible:
            if i == need:
                return Intent(FOLLOW, {"target": [x, y]}, emit=emit, rationale="visible next-needed food")

        remembered = self._remembered(view, need)
        if remembered is not None:
            target, record_id = remembered
            return Intent(FOLLOW, {"target": target}, emit=emit, cites=(record_id,) if record_id else (),
                          rationale="remembered next-needed food")

        if visible and not carrying:
            x, y, _ = visible[0]
            return Intent(FOLLOW, {"target": [x, y]}, emit=emit, rationale="visible food, not next-needed")
        return Intent(SWEEP, emit=emit)

    def _remembered(self, view: LocalView, need: int) -> Optional[Tuple[List[int], str]]:
        if self.use_memory:
            for record in view.memory:
                body = record.body
                if body.get("kind") == "found" and body.get("payload", {}).get("food") == need and body.get("pos"):
                    return [int(c) for c in body["pos"]], record.id
        if self.use_signals:
            for signal in view.signals:
                if signal.kind == "found" and signal.payload.get("food") == need:
                    return [int(c) for c in signal.pos], ""
        return None
