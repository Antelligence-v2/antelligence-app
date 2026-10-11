"""Deterministic port of SwarmBench foraging (MIT, https://github.com/x66ccff/swarmbench).

Ten agents, 100 rounds, a 10x10 walled map with a 2x2 food source and a 2x2 nest on opposite sides of a
serpentine wall (the published layouts, generated from the same seeded draws as ``swarmbench/task.py``).
Each agent sees an egocentric 5x5 window, hears radius-limited auto-generated peer messages (<= 120
characters) and scores a delivery by bringing food to the nest. See README.md for every departure from
SwarmBench (the ILP physics is replaced by a deterministic push rule).

Conditions (instructions and scorer never change):

* ``base`` -- as published (food is unlimited).
* ``v1``   -- "food runs out": the patch empties after ``n_pickups`` pickups and a new one appears elsewhere.
* ``v2``   -- "sensor flips": from tick ``flip_tick`` the west-east axis of every agent's *view* is mirrored.
  Only what the agent senses is mirrored; the world itself is not.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Set, Tuple

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import NOOP, Intent, Observation, Outcome
from antelligence.worlds.foraging_sb.nav import DIRS, RADIUS, VIEW, Cell, MapMemory, compass

WIDTH = HEIGHT = 10
N_AGENTS = 10
STEPS = 100
MSG_RADIUS = 4  # Chebyshev cells; SwarmBench uses the view radius (2)
MSG_MAX = 120
BLOCK = 2  # food and nest are 2x2 blocks
CONDITIONS = ("base", "v1", "v2")
V1_PICKUPS = 6  # variant parameters (tuned in variants.py, see README)
V2_FLIP_TICK = 30

MOVES = tuple(DIRS)  # north east south west
STAY = "stay"
PICK_UP = "pick_up"
DROP = "drop"


def _block(top: int, left: int) -> List[Cell]:
    return [(left + dx, top + dy) for dy in range(BLOCK) for dx in range(BLOCK)]


def _anchor(block: List[Cell]) -> Cell:
    """The block cell closest to the map centre (a corner cell of a block can have no open neighbour)."""
    return min(block, key=lambda c: (abs(2 * c[0] - WIDTH + 1) + abs(2 * c[1] - HEIGHT + 1), c))


def make_layout(seed: int) -> Dict[str, Any]:
    """The SwarmBench foraging layout for ``seed`` (same Random draws, same order as swarmbench/task.py).

    Returns walls (x, y), food and nest blocks, the wall orientation and the ten agent start cells.
    """
    rng = Random(seed)
    w, h = WIDTH, HEIGHT
    walls = {(x, y) for x in range(w) for y in range(h) if x in (0, w - 1) or y in (0, h - 1)}
    food_i = rng.choice([1, h - 3])
    food_j = rng.choice([1, w - 3])
    nest_i = h - 3 if food_i == 1 else 1
    nest_j = w - 3 if food_j == 1 else 1
    horizontal = rng.randint(0, 1) == 0
    if horizontal:
        rows = list(range(4, h - 4, 4))
        if len(rows) % 2 == 1:
            nest_j = food_j = 1
        for n, i in enumerate(rows):
            span = range(0, w + (-w // 3 + 1)) if n % 2 == 0 else range(w // 3, w)
            walls |= {(x, i) for x in span}
    else:
        cols = list(range(4, w - 4, 4))
        if len(cols) % 2 == 1:
            nest_i = food_i = 1
        for n, j in enumerate(cols):
            span = range(0, h + (-h // 3 + 1)) if n % 2 == 0 else range(h // 3, h)
            walls |= {(j, y) for y in span}
    food, nest = _block(food_i, food_j), _block(nest_i, nest_j)
    starts: List[Cell] = []
    taken = walls | set(food) | set(nest)
    while len(starts) < N_AGENTS:  # spread(): uniform over the inner map, rejection sampling
        x, y = rng.randint(1, w - 2), rng.randint(1, h - 2)
        if (x, y) not in taken and (x, y) not in starts:
            starts.append((x, y))
    return {"walls": walls, "food": food, "nest": nest, "horizontal": horizontal, "starts": starts,
            "food_corner": (food_i, food_j)}


class ForagingSBWorld:
    def __init__(self, seed: int, condition: str = "base", *, n_pickups: int = V1_PICKUPS,
                 flip_tick: int = V2_FLIP_TICK, max_steps: int = STEPS) -> None:
        if condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        self.seed, self.condition = seed, condition
        self.n_pickups, self.flip_tick, self.max_steps = n_pickups, flip_tick, max_steps
        lay = make_layout(seed)
        self.layout = lay
        self.walls: Set[Cell] = set(lay["walls"])
        self.nest: List[Cell] = list(lay["nest"])
        self.food: List[Cell] = list(lay["food"])
        self.positions: Dict[str, Cell] = {str(i): p for i, p in enumerate(lay["starts"])}
        self.carrying: Dict[str, bool] = {a: False for a in self.positions}
        self.memory: Dict[str, MapMemory] = {a: MapMemory(WIDTH, HEIGHT) for a in self.positions}
        for m in self.memory.values():  # briefed at the start: where the food patch and the nest are
            m.food_at, m.nest_at = _anchor(self.food), _anchor(self.nest)
        self.stuck: Dict[str, int] = {a: 0 for a in self.positions}  # consecutive failed moves
        self.deliveries = 0
        self.pickups = 0
        self.patch_swaps = 0
        self.delivery_ticks: List[int] = []
        self.counters = {"moves": 0, "pushes": 0, "blocked": 0, "idle": 0, "invalid": 0}
        self._revision = 0
        self._tick = 0
        self._cache: Dict[str, Tuple[int, Dict[str, Any]]] = {}  # agent -> (tick, perception)
        self._inbox: List[Dict[str, Any]] = []  # messages posted last tick
        self._outbox: List[Dict[str, Any]] = []
        self.messages_sent = 0

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self.positions)

    def describe(self) -> Dict[str, Any]:
        return {"world": "foraging_sb", "version": 1, "seed": self.seed, "condition": self.condition,
                "grid": [WIDTH, HEIGHT], "agents": N_AGENTS, "max_steps": self.max_steps, "view": VIEW,
                "msg_radius": MSG_RADIUS, "n_pickups": self.n_pickups, "flip_tick": self.flip_tick}

    def scene(self) -> Dict[str, Any]:
        return {"kind": "grid", "grid": [WIDTH, HEIGHT], "view_k": VIEW, "walls": sorted(map(list, self.walls)),
                "nest": [list(c) for c in self.nest]}

    def snapshot(self) -> Dict[str, Any]:
        return {"agents": [[p[0], p[1], int(self.carrying[a])] for a, p in sorted(self.positions.items())],
                "food": [list(c) for c in self.food], "delivered": self.deliveries,
                "flipped": self.flipped(self._tick)}

    def flipped(self, tick: int) -> bool:
        return self.condition == "v2" and tick >= self.flip_tick

    def metrics(self) -> Dict[str, Any]:
        return {"deliveries": self.deliveries, "pickups": self.pickups, "patch_swaps": self.patch_swaps,
                "messages_sent": self.messages_sent, **self.counters}

    def done(self, tick: int) -> bool:
        return tick >= self.max_steps

    # ------------------------------------------------------------ perception
    def _cell_char(self, cell: Cell, me: str) -> str:
        if not (0 <= cell[0] < WIDTH and 0 <= cell[1] < HEIGHT):
            return "*"
        if cell in self.walls:
            return "W"
        if cell in self.food:
            return "F"
        if cell in self.nest:
            return "N"
        for a, p in self.positions.items():
            if p == cell:
                return "Y" if a == me else a
        return "."

    def view_rows(self, agent_id: str, tick: int) -> List[str]:
        """The egocentric 5x5 window as the agent perceives it (mirrored west-east once the sensor flips)."""
        px, py = self.positions[agent_id]
        rows = ["".join(self._cell_char((px + dx, py + dy), agent_id) for dx in range(-RADIUS, RADIUS + 1))
                for dy in range(-RADIUS, RADIUS + 1)]
        return [r[::-1] for r in rows] if self.flipped(tick) else rows

    def _message(self, agent_id: str, rows: List[str]) -> Optional[str]:
        """Auto-generated broadcast: a carrier that sees the nest names its direction, else a seer names food."""
        want = "N" if self.carrying[agent_id] else "F"
        best: Optional[Tuple[int, int, int]] = None
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == want:
                    cand = (abs(c - RADIUS) + abs(r - RADIUS), r, c)
                    best = min(best, cand) if best else cand
        if best is None:
            return None
        text = f"{'nest' if want == 'N' else 'food'} is {compass(best[2] - RADIUS, best[1] - RADIUS)} of me"
        return text[:MSG_MAX]

    def _perceive(self, agent_id: str, tick: int) -> Dict[str, Any]:
        cached = self._cache.get(agent_id)
        if cached and cached[0] == tick:
            return cached[1]
        pos = self.positions[agent_id]
        rows = self.view_rows(agent_id, tick)
        mem = self.memory[agent_id]
        prev_food, prev_nest = mem.food_at, mem.nest_at
        seen_food, seen_nest = mem.update(pos, rows)
        flip = self.flipped(tick)
        heard = []
        for m in self._inbox:
            sx, sy = m["pos"]
            if m["from"] == agent_id or max(abs(sx - pos[0]), abs(sy - pos[1])) > MSG_RADIUS:
                continue
            dx, dy = sx - pos[0], sy - pos[1]
            heard.append({"from": m["from"], "text": m["text"], "dx": -dx if flip else dx, "dy": dy})
        heard.sort(key=lambda m: (abs(m["dx"]) + abs(m["dy"]), m["from"]))
        data = {
            "agent": agent_id, "tick": tick, "pos": list(pos), "view": rows, "carrying": self.carrying[agent_id],
            "grid": [WIDTH, HEIGHT], "map": mem.as_rows(),
            "food_at": list(mem.food_at) if mem.food_at else None,
            "nest_at": list(mem.nest_at) if mem.nest_at else None,
            "food_prev": list(prev_food) if prev_food else None,
            "nest_prev": list(prev_nest) if prev_nest else None,
            "food_seen": list(seen_food) if seen_food else None,
            "nest_seen": list(seen_nest) if seen_nest else None,
            "heard": heard,
            "stuck": self.stuck[agent_id],
        }
        self._cache[agent_id] = (tick, data)
        text = self._message(agent_id, rows)
        if text:
            self._outbox.append({"from": agent_id, "text": text, "pos": pos})
        return data

    def observe(self, agent_id: str, tick: int) -> Observation:
        data = self._perceive(agent_id, tick)
        return Observation(data=data, sense=SenseQuery(pos=self.positions[agent_id], radius=0, kinds=frozenset()))

    # ---------------------------------------------------------------- action
    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        action = intent.action
        if action in (NOOP, STAY):
            self.counters["idle"] += 1
            self.stuck[agent_id] = 0
            return Outcome(True)
        if action in (PICK_UP, DROP):
            self.stuck[agent_id] = 0
            return self._pick_up(agent_id) if action == PICK_UP else self._drop(agent_id, tick)
        if action not in DIRS:
            self.counters["invalid"] += 1
            return Outcome(False, "unknown_action")
        outcome = self._move(agent_id, DIRS[action])
        self.stuck[agent_id] = 0 if outcome.accepted else self.stuck[agent_id] + 1
        return outcome

    def _pick_up(self, agent_id: str) -> Outcome:
        """Take one piece of food from a patch the agent stands next to (one piece at a time)."""
        cell = self._touching(self.positions[agent_id], self.food)
        if self.carrying[agent_id] or cell is None:
            self.counters["invalid"] += 1
            return Outcome(False, "already_carrying" if self.carrying[agent_id] else "no_food_adjacent")
        self.carrying[agent_id] = True
        self.memory[agent_id].refresh(food=cell)
        self.pickups += 1
        self._revision += 1
        if self.condition == "v1" and self.pickups == self.n_pickups:
            self._swap_patch()
        return Outcome(True, effects={"pickups": self.pickups})

    def _drop(self, agent_id: str, tick: int) -> Outcome:
        """Deliver carried food to a nest the agent stands next to: one point."""
        cell = self._touching(self.positions[agent_id], self.nest)
        if not self.carrying[agent_id] or cell is None:
            self.counters["invalid"] += 1
            return Outcome(False, "not_carrying" if not self.carrying[agent_id] else "no_nest_adjacent")
        self.carrying[agent_id] = False
        self.memory[agent_id].refresh(nest=cell)
        self.deliveries += 1
        self.delivery_ticks.append(tick)
        self._revision += 1
        return Outcome(True, effects={"deliveries": self.deliveries})

    def _free(self, cell: Cell) -> bool:
        return (0 <= cell[0] < WIDTH and 0 <= cell[1] < HEIGHT and cell not in self.walls
                and cell not in self.food and cell not in self.nest)

    def _move(self, agent_id: str, delta: Cell) -> Outcome:
        """Push rule: step into a free cell; step into a chain of at most two agents if the cell behind it is free.

        Agents have weight 1 and force 2 (SwarmBench), so one agent can shove a chain of <= 2 agents;
        walls, food and nest never move. Moves resolve one agent at a time in agent-id order.
        """
        by_cell = {p: a for a, p in self.positions.items()}
        pos = self.positions[agent_id]
        cell = (pos[0] + delta[0], pos[1] + delta[1])
        chain: List[str] = []
        probe = cell
        while probe in by_cell and len(chain) <= 2:
            chain.append(by_cell[probe])
            probe = (probe[0] + delta[0], probe[1] + delta[1])
        if not self._free(cell):
            self.counters["blocked"] += 1
            return Outcome(False, "blocked")
        if chain:
            if len(chain) > 2 or not self._free(probe) or probe in by_cell:
                self.counters["blocked"] += 1
                return Outcome(False, "blocked_by_agent")
            for a in reversed(chain):  # far end first
                p = self.positions[a]
                self.positions[a] = (p[0] + delta[0], p[1] + delta[1])
            self.counters["pushes"] += 1
        self.positions[agent_id] = cell
        self.counters["moves"] += 1
        self._revision += 1
        return Outcome(True, effects={"pos": list(cell), "pushed": len(chain)})

    # ------------------------------------------------------------ environment
    def _touching(self, pos: Cell, cells: List[Cell]) -> Optional[Cell]:
        """A cell of ``cells`` that shares an edge with ``pos`` (first in north, east, south, west order)."""
        near = ((pos[0] + dx, pos[1] + dy) for dx, dy in DIRS.values())
        return next((c for c in near if c in cells), None)

    def step_environment(self, tick: int) -> None:
        """Post this tick's auto-generated messages (delivered to listeners next tick)."""
        self._tick = tick
        self._inbox, self._outbox = self._outbox, []
        self.messages_sent += len(self._inbox)

    def _swap_patch(self) -> None:
        """v1: the patch is exhausted; a fresh, unlimited one appears on the far side of the same lane (see README)."""
        top, left = self.layout["food_corner"]
        if self.layout["horizontal"]:
            left = WIDTH - 3 if left < WIDTH // 2 else 1
        else:
            top = HEIGHT - 3 if top < HEIGHT // 2 else 1
        self.layout["food_corner"] = (top, left)
        self.food = _block(top, left)
        self.patch_swaps += 1
        self._revision += 1
