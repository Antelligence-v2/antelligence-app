"""Nanobot brains for the tumor world.

:class:`NanobotPolicy` is the legacy rule-based nanobot (target the nearest
sensed living cell; otherwise chemotaxis on local gradients with inertia and
noise), expressed as a pure function of the LocalView. Coordination features
are switches, so arms differ only in what agents may share:

* ``announce``      — emit ``found`` (cells sensed here) and ``claimed``
                      (I am treating cell X) signals;
* ``honor_claims``  — skip cells another bot has claimed, if alternatives exist;
* ``use_signals``   — when nothing is sensed, head for heard ``found`` /
                      ``recruit`` signals;
* ``use_memory``    — when nothing is sensed, head for remembered ``found``
                      zones and cite the evidence.

``LLM_ACTIONS`` / ``LLM_SIGNAL_KINDS`` configure a kernel ``LLMPolicy``.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import Intent, LocalView
from antelligence.worlds.tumor.world import QUEEN, SEARCHING, zone_center, zone_subject

LLM_ACTIONS = {
    "target": "lock onto a sensed living cell: params.cell_id",
    "move": "step while searching: params.direction = [dx, dy]",
    "advance": "continue your current mission (approach, deliver, return to vessel, reload)",
    "noop": "wait",
}
LLM_SIGNAL_KINDS = {
    "found": 'tumor cells sensed here: pos=[x, y], payload={"cells": n}',
    "claimed": 'you are treating a cell: pos=[x, y], payload={"cell_id": id}',
}

CHEMOTAXIS_WEIGHTS = {"oxygen": -1.0, "trail_pheromone": 0.8, "alarm_pheromone": -0.5, "recruitment_pheromone": 0.6}


class NanobotPolicy:
    def __init__(
        self,
        *,
        announce: bool = False,
        honor_claims: bool = False,
        use_signals: bool = False,
        use_memory: bool = False,
        found_ttl: int = 20,
        claim_ttl: int = 8,
    ) -> None:
        self.announce = announce
        self.honor_claims = honor_claims
        self.use_signals = use_signals
        self.use_memory = use_memory
        self.found_ttl = found_ttl
        self.claim_ttl = claim_ttl

    def describe(self) -> Dict[str, Any]:
        return {"policy": "nanobot_rule", "announce": self.announce, "honor_claims": self.honor_claims,
                "use_signals": self.use_signals, "use_memory": self.use_memory,
                "found_ttl": self.found_ttl, "claim_ttl": self.claim_ttl}

    def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        if obs.get("role") == QUEEN:
            return Intent("noop")
        if obs["state"] != SEARCHING:
            return Intent("advance")
        pos = obs["pos"]
        cells = obs["cells"]
        emit: List[SignalDraft] = []
        if self.announce and cells:
            centroid = tuple(round(sum(c["pos"][i] for c in cells) / len(cells), 3) for i in range(len(pos)))
            emit.append(SignalDraft(kind="found", pos=centroid, payload={"cells": len(cells)}, ttl=self.found_ttl))

        if cells and obs["payload"] > 2.0:
            candidates = cells
            if self.honor_claims:
                claimed = {s.payload.get("cell_id") for s in view.signals if s.kind == "claimed"}
                unclaimed = [c for c in cells if c["id"] not in claimed]
                candidates = unclaimed or cells
            chosen = candidates[0]  # observation is sorted by distance
            if self.announce:
                emit.append(SignalDraft(kind="claimed", pos=tuple(chosen["pos"]),
                                        payload={"cell_id": chosen["id"]}, ttl=self.claim_ttl))
            return Intent("target", {"cell_id": chosen["id"]}, emit=tuple(emit), rationale="nearest sensed cell")

        lead = self._lead(view, pos)
        if lead is not None:
            target, cites, why = lead
            direction = [target[i] - pos[i] if i < len(target) else 0.0 for i in range(len(pos))]
            if math.hypot(*direction) > 1e-9:
                return Intent("move", {"direction": _unit(direction)}, emit=tuple(emit), cites=cites, rationale=why)

        return Intent("move", {"direction": self._chemotaxis(view)}, emit=tuple(emit))

    def _lead(self, view: LocalView, pos: List[float]) -> Optional[Tuple[Tuple[float, float], Tuple[str, ...], str]]:
        here = zone_subject(tuple(pos))
        if self.use_memory:
            zones = [(r, zone_center(r.subject)) for r in view.memory
                     if r.subject.startswith("zone:") and r.subject != here]
            if zones:
                record, center = min(zones, key=lambda z: (_d(z[1], pos), z[0].id))
                return center, (record.id,), "remembered tumor zone"
        if self.use_signals:
            leads = [s for s in view.signals if s.kind in ("found", "recruit")
                     and zone_subject(tuple(s.pos)) != here]
            if leads:
                best = min(leads, key=lambda s: (s.kind != "recruit", _d(s.pos, pos), s.id))
                return tuple(best.pos), (), f"heard {best.kind} signal"
        return None

    def _chemotaxis(self, view: LocalView) -> List[float]:
        obs = view.observation
        if len(obs["pos"]) == 3:
            return _chemotaxis_3d(obs, random.Random(view.seed))
        rng = random.Random(view.seed)
        gx = gy = 0.0
        for name, weight in CHEMOTAXIS_WEIGHTS.items():
            g = obs["gradients"].get(name)
            if g:
                gx += weight * g[0]
                gy += weight * g[1]
        if math.hypot(gx, gy) > 0:
            gx, gy = _unit([gx, gy])
            prev = obs["previous_direction"]
            dx = 0.7 * gx + 0.3 * prev[0] + rng.gauss(0, 0.1)
            dy = 0.7 * gy + 0.3 * prev[1] + rng.gauss(0, 0.1)
            if math.hypot(dx, dy) > 0:
                return _unit([dx, dy])
        if obs["inside_tumor"]:
            angle = rng.uniform(0, 2 * math.pi)
            return [math.cos(angle), math.sin(angle)]
        center = obs["anatomy"]["tumor_center"]
        return _unit([center[0] - obs["pos"][0], center[1] - obs["pos"][1]]) or [1.0, 0.0]


def _chemotaxis_3d(obs: Dict[str, Any], rng: random.Random) -> List[float]:
    """Same rule as 2D (weighted gradients, inertia, noise) with a z component."""
    g = [0.0, 0.0, 0.0]
    for name, weight in CHEMOTAXIS_WEIGHTS.items():
        grad = obs["gradients"].get(name)
        if grad:
            for i in range(3):
                g[i] += weight * grad[i]
    if math.hypot(*g) > 0:
        g = _unit(g)
        prev = obs["previous_direction"]
        d = [0.7 * g[i] + 0.3 * prev[i] + rng.gauss(0, 0.1) for i in range(3)]
        if math.hypot(*d) > 0:
            return _unit(d)
    if obs["inside_tumor"]:
        return _unit([rng.gauss(0, 1) for _ in range(3)]) or [1.0, 0.0, 0.0]  # uniform on the sphere
    center = obs["anatomy"]["tumor_center"]
    return _unit([center[i] - obs["pos"][i] for i in range(3)]) or [1.0, 0.0, 0.0]


def _unit(v: List[float]) -> List[float]:
    if len(v) == 2:
        n = math.hypot(v[0], v[1])
        return [v[0] / n, v[1] / n] if n > 0 else []
    n = math.hypot(*v)
    return [c / n for c in v] if n > 0 else []


def _d(a, b) -> float:
    if len(a) >= 3 and len(b) >= 3:
        return math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
    return math.hypot(a[0] - b[0], a[1] - b[1])
