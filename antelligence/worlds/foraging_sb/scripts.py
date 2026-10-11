"""Scripts for foraging_sb: S and the variant-aware S'. Ordinary Policies that read ``SensedState.fields``.

* :class:`ShortestPath` (S) -- walk the shortest path to the remembered food, carry to the remembered nest,
  explore toward unseen ground when nothing is remembered. It trusts its memory.
* :class:`ExploreWhenEmpty` (S' for v1) -- S, but once the remembered food spot is in view and shows no food
  it forgets that spot and explores until it sees food somewhere else.
* :class:`Unmirror` (S' for v2) -- S with its own map memory, built from the view with the west-east flip
  undone. It knows the flip may start at tick T and decides whether it has started by checking which reading
  of the view (as given, or mirrored) agrees with the walls it already knows; with no evidence it learns nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from antelligence.kernel.types import Intent, LocalView
from antelligence.worlds.foraging_sb.nav import RADIUS, MapMemory, plan_route, unstick
from antelligence.worlds.foraging_sb.sensing import ForagingSensor, agents_in_view


class ShortestPath:
    """S: remember food and nest, take the shortest path."""

    def __init__(self, sensor: Optional[ForagingSensor] = None) -> None:
        self.sensor = sensor or ForagingSensor()

    def describe(self) -> Dict[str, Any]:
        return {"policy": "foraging_sb.S", "version": 1}

    def decide(self, view: LocalView) -> Intent:
        f = self.sensor.sense(view).fields
        return Intent(unstick(f["route"], f["stuck"], f["view"], view.seed))


class ExploreWhenEmpty(ShortestPath):
    """S' for v1: forget a remembered food spot that is in view and empty, then go to food seen elsewhere."""

    def __init__(self, sensor: Optional[ForagingSensor] = None) -> None:
        super().__init__(sensor)
        self._state: Dict[str, Dict[str, Any]] = {}

    def describe(self) -> Dict[str, Any]:
        return {"policy": "foraging_sb.S_prime_v1", "version": 1}

    def decide(self, view: LocalView) -> Intent:
        f = self.sensor.sense(view).fields
        agent, tick = f["agent"], f["tick"]
        st = self._state.get(agent)
        if st is None or tick <= st["tick"]:  # a new run reuses the policy
            st = self._state[agent] = {"tick": 0, "stale": None, "target": None}
        st["tick"] = tick
        remembered = _t(f["food_at"])
        if f["food_gone"]:
            st["stale"], st["target"] = remembered, None
        seen = _t(f["food_seen"])
        if seen is not None and seen != st["stale"]:
            st["target"] = seen  # food in view somewhere that is not the emptied spot
        target = st["target"] or (remembered if remembered != st["stale"] else None)
        action, _ = plan_route(f["map"], _t(f["pos"]), f["carrying"], target, _t(f["nest_at"]),
                               [tuple(c) for c in f["occupied"]], rot=int(agent) % 4)
        return Intent(unstick(action, f["stuck"], f["view"], view.seed))


def _t(cell: Optional[List[int]]) -> Optional[Tuple[int, int]]:
    return (cell[0], cell[1]) if cell else None


def _mismatch(mem: MapMemory, pos: Tuple[int, int], rows: List[str]) -> int:
    """Wall disagreements between a reading of the view and the map already known."""
    bad = 0
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            x, y = pos[0] + c - RADIUS, pos[1] + r - RADIUS
            if ch == "*" or not (0 <= x < mem.width and 0 <= y < mem.height):
                continue
            known = mem.rows[y][x]
            if known in "?FN" or ch in "FN":
                continue
            bad += (known == "#") != (ch == "W")
    return bad


class Unmirror(ShortestPath):
    """S' for v2: knows the sensor may flip west-east from ``flip_tick`` and undoes it."""

    def __init__(self, flip_tick: int, sensor: Optional[ForagingSensor] = None) -> None:
        super().__init__(sensor)
        self.flip_tick = flip_tick
        self._state: Dict[str, Dict[str, Any]] = {}

    def describe(self) -> Dict[str, Any]:
        return {"policy": "foraging_sb.S_prime_v2", "version": 1, "flip_tick": self.flip_tick}

    def decide(self, view: LocalView) -> Intent:
        f = self.sensor.sense(view).fields
        agent, tick, pos = f["agent"], f["tick"], (f["pos"][0], f["pos"][1])
        st = self._state.get(agent)
        if st is None or tick <= st["tick"]:  # a new run reuses the policy
            mem = MapMemory(*view.observation["grid"], sticky=False)
            st = self._state[agent] = {"mem": mem, "plain": 0, "mirror": 0, "tick": 0}
        st["tick"] = tick
        mem: MapMemory = st["mem"]
        rows: List[str] = list(f["view"])
        mirrored = [r[::-1] for r in rows]
        learn = True
        if tick >= self.flip_tick:
            st["plain"] += _mismatch(mem, pos, rows)
            st["mirror"] += _mismatch(mem, pos, mirrored)
            learn = st["plain"] != st["mirror"]  # no evidence either way: learn nothing from this view
            if st["plain"] > st["mirror"]:
                rows = mirrored
        if learn:
            mem.update(pos, rows)
        action, _ = plan_route(mem.as_rows(), pos, f["carrying"], mem.food_at, mem.nest_at,
                               agents_in_view(pos, rows), rot=int(agent) % 4)
        return Intent(unstick(action, f["stuck"], rows, view.seed))
