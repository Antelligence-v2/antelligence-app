"""Sensor for foraging_sb: LocalView -> SensedState in short words.

Everything is computed here in code (directions, distances, blocked sides), so a decision model never
counts or does geometry. The text only uses what the world told this agent: its own view (mirrored under
variant v2), the cells it remembers, and the peer messages it heard. The remembered food and nest are the spots
the agent was briefed on, moved only when it picks up or drops there; seeing the spot empty or food somewhere
else never changes them, which is what makes a script stale when the world changes.

Actions: four moves, pick up (food next to you), drop (nest next to you) and stay.
Checks (at most two judgement questions): whether the remembered food patch is still there, and whether the
nest is where the agent remembered it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from antelligence.kernel.decision import Question, SensedState
from antelligence.kernel.types import LocalView
from antelligence.worlds.foraging_sb.nav import DIRS, RADIUS, Cell, plan_route, relative, ring_of

ACTIONS: Dict[str, str] = {
    "north": "move one cell north (up the map)",
    "east": "move one cell east (right)",
    "south": "move one cell south (down)",
    "west": "move one cell west (left)",
    "pick_up": "pick up one piece of food (needs food next to you and empty hands)",
    "drop": "drop the food you carry into the nest (needs the nest next to you)",
    "stay": "stay where you are",
}

SEEN = {".": "open", "W": "wall", "F": "food", "N": "nest", "*": "edge"}  # what one view cell is called
FOOD_CHECK = "food_still_there"
NEST_CHECK = "nest_where_remembered"

CHECKS: Dict[str, Question] = {
    FOOD_CHECK: Question(
        "noul", "Is the food patch you remember still there? Answer no if the state says the spot is empty or "
        "what you see contradicts it.",
        criteria={"true": "the remembered food is still there", "false": "the remembered food is gone"}),
    NEST_CHECK: Question(
        "noul", "Is the nest where you remembered it? Answer no if the nest you see now is in a different place "
        "from the one you remembered.",
        criteria={"true": "the nest is where remembered", "false": "the nest is not where remembered"}),
}


def _cell(raw: Optional[List[int]]) -> Optional[Cell]:
    return (raw[0], raw[1]) if raw else None


def agents_in_view(pos: Cell, view: List[str]) -> List[Cell]:
    """Other agents in the perceived window as cells in the agent's own frame."""
    out = []
    for r, row in enumerate(view):
        for c, ch in enumerate(row):
            if ch.isdigit():
                out.append((pos[0] + c - RADIUS, pos[1] + r - RADIUS))
    return out


def derive(obs: Mapping[str, Any]) -> Dict[str, Any]:
    """Structured facts for one agent (the ``fields`` of the SensedState), computed from the observation."""
    pos = (obs["pos"][0], obs["pos"][1])
    view: List[str] = list(obs["view"])
    food_at, nest_at = _cell(obs["food_at"]), _cell(obs["nest_at"])
    occupied = agents_in_view(pos, view)
    action, mode = plan_route(obs["map"], pos, bool(obs["carrying"]), food_at, nest_at, occupied,
                              rot=int(obs["agent"]) % 4)

    def in_view(cell: Optional[Cell]) -> bool:
        return cell is not None and max(abs(cell[0] - pos[0]), abs(cell[1] - pos[1])) <= RADIUS

    food_in_view = in_view(food_at)
    # The remembered food cell is inside the window: is food actually shown there?
    food_gone = False
    if food_in_view:
        r, c = food_at[1] - pos[1] + RADIUS, food_at[0] - pos[0] + RADIUS
        food_gone = view[r][c] != "F"
    nest_prev, nest_seen = _cell(obs["nest_prev"]), _cell(obs["nest_seen"])
    # The nest is a 2x2 block, so two sightings of it can differ by one cell without it having moved.
    nest_moved = (nest_prev is not None and nest_seen is not None
                  and max(abs(nest_prev[0] - nest_seen[0]), abs(nest_prev[1] - nest_seen[1])) > 1)
    ring = ring_of(view)
    return {
        "agent": obs["agent"], "tick": obs["tick"], "pos": list(pos), "carrying": bool(obs["carrying"]),
        "view": view, "map": list(obs["map"]), "food_at": list(food_at) if food_at else None,
        "nest_at": list(nest_at) if nest_at else None, "food_gone": food_gone, "food_in_view": food_in_view,
        "food_seen": obs["food_seen"], "nest_seen": list(nest_seen) if nest_seen else None, "nest_moved": nest_moved,
        "occupied": [list(c) for c in occupied], "stuck": int(obs["stuck"]),
        "food_adjacent": "F" in ring.values(), "nest_adjacent": "N" in ring.values(),
        "last": obs.get("last"), "heard": list(obs["heard"]),
        "route": action, "mode": mode,
    }


def render(f: Mapping[str, Any]) -> str:
    """The state text: short sentences, directions in words."""
    px, py = f["pos"]
    parts = [f"Carrying food: {'yes' if f['carrying'] else 'no'}."]
    if f["food_at"]:
        fx, fy = f["food_at"]
        parts.append(f"Remembered food spot: {relative(fx - px, fy - py)}.")
        if f["food_in_view"]:
            parts.append("That spot is in view and shows no food." if f["food_gone"] else
                         "That spot is in view and food is there.")
    else:
        parts.append("Food: none remembered yet.")
    if f["nest_at"]:
        nx, ny = f["nest_at"]
        parts.append(f"Remembered nest: {relative(nx - px, ny - py)}.")
        if f["nest_moved"]:
            sx, sy = f["nest_seen"]
            parts.append(f"A nest is in view now: {relative(sx - px, sy - py)}, not where it was remembered.")
    else:
        parts.append("Nest: none remembered yet.")
    if f["food_adjacent"]:
        parts.append("Food is next to you.")
    if f["nest_adjacent"]:
        parts.append("The nest is next to you.")
    if f["food_seen"] and f["food_seen"] != f["food_at"]:
        parts.append(f"Food in view: {relative(f['food_seen'][0] - px, f['food_seen'][1] - py)}.")
    view = f["view"]  # the agent's own 5x5 window, two cells out each way (stopping at the first thing in the way)
    for name, (dx, dy) in DIRS.items():
        cells = []
        for k in (1, 2):
            ch = view[RADIUS + dy * k][RADIUS + dx * k]
            cells.append(f"agent {ch}" if ch.isdigit() else SEEN[ch])
            if ch != ".":
                break
        parts.append(f"{name.capitalize()}: {', then '.join(cells)}.")
    if f["last"]:
        act, how = f["last"]
        parts.append(f"Last {'move' if act in DIRS else 'action'}: {act}, {how}.")
    for m in f["heard"][:2]:
        parts.append(f"Heard: agent {m['from']} ({relative(m['dx'], m['dy'])} of you) says \"{m['text']}\".")
    # No route hint: a planner hint that ignores other agents jammed every model arm (dev seed 100).
    return " ".join(parts)


class ForagingSensor:
    """``Sensor`` for foraging_sb. Deterministic, no RNG, no hidden state."""

    def sense(self, view: LocalView) -> SensedState:
        fields = derive(view.observation)
        checks: Dict[str, Question] = {}
        if fields["food_at"]:
            checks[FOOD_CHECK] = CHECKS[FOOD_CHECK]
        if fields["nest_at"]:
            checks[NEST_CHECK] = CHECKS[NEST_CHECK]
        return SensedState(render(fields), fields, ACTIONS, checks)

    def describe(self) -> Dict[str, Any]:
        return {"sensor": "foraging_sb", "version": 1, "actions": list(ACTIONS), "checks": list(CHECKS)}
