"""Ant colony world: the legacy ant foraging simulation on the engine.

Port of ``backend/simulation.SimpleForagingModel``. The world owns the grid,
food clusters, the four pheromone maps (trail, alarm, recruitment, fear), ant
and predator bodies, pickup/drop, hunting and evaporation. Policies own every
decision (``policies.py``): where an ant or predator moves, and the Queen's
guidance.

Agents: ``ant-000``.. (removed when caught), ``predator-000``.., and an
optional body-less ``queen`` at the nest. Each tick every agent decides from the
same snapshot, then intents apply in id order (ants, then predators, then the
Queen), followed by evaporation, matching legacy's step order. The Queen's
guidance reaches ants one tick later than in legacy, so she hands each ant a
goal cell (legacy: the nest or the nearest food) and the ant takes legacy's best
step toward it from where it stands, instead of a stale one-step move.

Layout is drawn from the world's own RandomState in legacy's exact order
(food clusters, then ants, then predators), so seed 42 reproduces the legacy
endpoint's starting layout.

Metrics are honest where legacy double counted: legacy added to
``food_collected`` both when food was picked up and when it was dropped at the
nest. Here ``food_collected`` counts pickups (food removed from the map) and
``food_delivered`` counts drops at the nest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.frames import encode_field
from antelligence.kernel.types import Intent, Observation, Outcome

Pos = Tuple[int, int]
QUEEN = "queen"
PHEROMONES = ("trail", "alarm", "recruitment", "fear")


@dataclass
class Ant:
    index: int
    pos: Pos
    is_llm: bool
    carrying: bool = False
    food_collected: int = 0
    steps_since_food: int = 0
    guidance: Optional[Pos] = None  # Queen's goal cell, valid for the tick after it was given
    guidance_tick: int = -1
    flipped_at: int = -1  # tick the ant last picked up or dropped food


@dataclass
class Predator:
    index: int
    pos: Pos
    is_llm: bool
    energy: int = 100
    cooldown: int = 0
    ants_caught: int = 0
    moves: int = 0


@dataclass
class Deposits:
    trail: float = 1.0
    alarm: float = 2.0
    recruitment: float = 1.5
    fear: float = 3.0
    decay: float = 0.05
    max_value: float = 10.0

    def describe(self) -> Dict[str, float]:
        return dict(self.__dict__)


class AntColonyWorld:
    def __init__(
        self,
        seed: int,
        *,
        width: int = 20,
        height: int = 20,
        n_ants: int = 10,
        n_food: int = 15,
        n_predators: int = 0,
        max_steps: int = 200,
        llm_ants: Optional[Set[int]] = None,
        llm_predators: Optional[Set[int]] = None,
        queen: bool = False,
        deposits: Optional[Deposits] = None,
    ) -> None:
        if width < 5 or height < 5:
            raise ValueError("grid must be at least 5x5")
        if not 1 <= n_food <= width * height:
            raise ValueError("n_food must fit on the grid")
        self.seed = seed
        self.width, self.height = width, height
        self.n_ants, self.n_food, self.n_predators = n_ants, n_food, n_predators
        self.max_steps = max_steps
        self.queen = queen
        self.deposits = deposits or Deposits()
        self.nest: Pos = (width // 2, height // 2)
        rs = np.random.RandomState(seed % (2**32))
        self._rng = random.Random(seed)  # legacy's random.random() drop roll
        self.foods: Set[Pos] = _place_food(rs, width, height, n_food)
        llm_ants = llm_ants or set()
        llm_predators = llm_predators or set()
        self.ants: Dict[str, Ant] = {}
        for i in range(n_ants):
            self.ants[f"ant-{i:03d}"] = Ant(i, (int(rs.randint(width)), int(rs.randint(height))), i in llm_ants)
        self.predators: Dict[str, Predator] = {}
        for i in range(n_predators):
            self.predators[f"predator-{i:03d}"] = Predator(i, (int(rs.randint(width)), int(rs.randint(height))),
                                                           i in llm_predators)
        self.pheromones = {name: np.zeros((width, height)) for name in PHEROMONES}
        self.efficiency = np.zeros((width, height))
        self.initial_food = len(self.foods)
        self.queen_report = "Queen initialized" if queen else "No queen active"
        self._revision = 0
        self.cleared_at: Optional[int] = None
        self.counters = {"food_collected": 0, "food_delivered": 0, "food_collected_by_llm": 0,
                         "food_collected_by_rule": 0, "ants_caught": 0, "llm_ants_caught": 0, "rule_ants_caught": 0,
                         "escapes": 0, "guided_moves": 0, "invalid_actions": 0}

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self.ants) + sorted(self.predators) + ([QUEEN] if self.queen else [])

    def describe(self) -> Dict[str, Any]:
        return {"world": "ant_colony", "version": 1, "seed": self.seed, "width": self.width, "height": self.height,
                "n_ants": self.n_ants, "n_food": self.n_food, "n_predators": self.n_predators,
                "max_steps": self.max_steps, "queen": self.queen, "deposits": self.deposits.describe(),
                "llm_ants": sorted(a.index for a in self.ants.values() if a.is_llm),
                "llm_predators": sorted(p.index for p in self.predators.values() if p.is_llm)}

    def observe(self, agent_id: str, tick: int) -> Observation:
        quiet = SenseQuery(kinds=frozenset())
        if agent_id == QUEEN:
            return Observation(self._queen_view(tick), quiet)
        if agent_id in self.predators:
            return Observation(self._predator_view(self.predators[agent_id]), quiet)
        return Observation(self._ant_view(self.ants[agent_id], tick), quiet)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if agent_id == QUEEN:
            return self._apply_queen(intent, tick)
        if agent_id in self.predators:
            return self._apply_predator(self.predators[agent_id], intent)
        ant = self.ants.get(agent_id)
        if ant is None:
            return Outcome(False, "caught")  # eaten earlier this tick
        return self._apply_ant(agent_id, ant, intent, tick)

    def step_environment(self, tick: int) -> None:
        self.efficiency *= 0.98
        self.efficiency[self.efficiency < 0.01] = 0
        for ant in self.ants.values():
            if ant.is_llm:
                self.efficiency[ant.pos] += 0.1
        for name in PHEROMONES:
            self.pheromones[name] *= (1 - self.deposits.decay)
            np.clip(self.pheromones[name], 0, self.deposits.max_value, out=self.pheromones[name])
        if self.cleared_at is None and not self.foods:
            self.cleared_at = tick

    def metrics(self) -> Dict[str, Any]:
        collected = self.counters["food_collected"]
        return {
            **self.counters,
            "initial_food": self.initial_food,
            "food_remaining": len(self.foods),
            "collection_rate": round(collected / self.initial_food, 6) if self.initial_food else 0.0,
            "all_food_collected": not self.foods,
            "cleared_at": self.cleared_at,
            "ants_alive": len(self.ants),
            "ants_carrying_food": sum(a.carrying for a in self.ants.values()),
        }

    def done(self, tick: int) -> bool:
        return tick >= self.max_steps or not self.foods

    # ---------------------------------------------------------- visualization
    def scene(self) -> Dict[str, Any]:
        return {"kind": "ant_colony", "grid": [self.width, self.height], "nest": list(self.nest),
                "fields": list(PHEROMONES) + ["efficiency"], "queen": self.queen}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "ants": [[a.pos[0], a.pos[1], int(a.carrying), int(a.is_llm), a.index] for _, a in sorted(self.ants.items())],
            "predators": [[p.pos[0], p.pos[1], p.energy, int(p.is_llm), p.index]
                          for _, p in sorted(self.predators.items())],
            "foods": sorted([list(f) for f in self.foods]),
            "fields": {**{name: encode_field(self.pheromones[name]) for name in PHEROMONES},
                       "efficiency": encode_field(self.efficiency)},
            "queen_report": self.queen_report,
        }

    # ---------------------------------------------------------------- views
    def neighbors(self, pos: Pos) -> List[Pos]:
        """Legacy get_neighborhood order: dx -1..1, dy -1..1, excluding (0, 0)."""
        x, y = pos
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx, dy) != (0, 0) and 0 <= x + dx < self.width and 0 <= y + dy < self.height]

    def _local_pheromones(self, pos: Pos, radius: int = 2) -> Dict[str, float]:
        x, y = pos
        x0, x1 = max(0, x - radius), min(self.width, x + radius + 1)
        y0, y1 = max(0, y - radius), min(self.height, y + radius + 1)
        area = (2 * radius + 1) ** 2  # legacy normalizes by the full window, even at edges
        return {name: round(float(self.pheromones[name][x0:x1, y0:y1].sum()) / area, 6) for name in PHEROMONES}

    def _nearest_food(self, pos: Pos) -> Optional[Pos]:
        if not self.foods:
            return None
        return min(self.foods, key=lambda f: abs(f[0] - pos[0]) + abs(f[1] - pos[1]))

    def _ant_view(self, ant: Ant, tick: int) -> Dict[str, Any]:
        x, y = ant.pos
        guidance = None
        goal = ant.guidance
        stale = goal is not None and (ant.flipped_at == ant.guidance_tick  # Queen saw it before it picked up/dropped
                                      or (goal != self.nest and goal not in self.foods))  # her food is gone
        if goal is not None and ant.guidance_tick == tick - 1 and not stale:  # legacy Queen step: the cell (staying allowed) closest to her goal
            guidance = list(min(self.neighbors(ant.pos) + [ant.pos],
                                key=lambda c: abs(c[0] - goal[0]) + abs(c[1] - goal[1])))
        food = self._nearest_food(ant.pos)
        return {
            "role": "ant",
            "index": ant.index,
            "pos": [x, y],
            "grid": [self.width, self.height],
            "nest": list(self.nest),
            "carrying": ant.carrying,
            "food_here": ant.pos in self.foods,
            "food_nearby": any(abs(fx - x) <= 1 and abs(fy - y) <= 1 for fx, fy in self.foods),
            "nearest_food": None if food is None else list(food),
            "neighbors": [list(n) for n in self.neighbors(ant.pos)],
            "predators_within_2": [list(p.pos) for _, p in sorted(self.predators.items())
                                   if abs(p.pos[0] - x) <= 2 and abs(p.pos[1] - y) <= 2],
            "predators_within_3": sum(abs(p.pos[0] - x) <= 3 and abs(p.pos[1] - y) <= 3
                                      for p in self.predators.values()),
            "pheromones": self._local_pheromones(ant.pos),
            "food_collected": ant.food_collected,
            "queen_guidance": guidance,
        }

    def _predator_view(self, p: Predator) -> Dict[str, Any]:
        # Legacy regenerated energy and cooled down *before* deciding, so show post-update values.
        energy = min(100, p.energy + 2) if p.energy < 100 else p.energy
        cooldown = max(0, p.cooldown - 1)
        x, y = p.pos
        ants = sorted(self.ants.items())
        nearest = min(ants, key=lambda kv: abs(kv[1].pos[0] - x) + abs(kv[1].pos[1] - y))[1].pos if ants else None
        cells = self.neighbors(p.pos) + [p.pos]
        return {
            "role": "predator",
            "index": p.index,
            "pos": [x, y],
            "grid": [self.width, self.height],
            "energy": energy,
            "cooldown": cooldown,
            "ants_caught": p.ants_caught,
            "moves": p.moves,
            "neighbors": [list(n) for n in self.neighbors(p.pos)],
            "nearest_ant": None if nearest is None else list(nearest),
            "ants_within_3": sum(abs(a.pos[0] - x) <= 3 and abs(a.pos[1] - y) <= 3 for _, a in ants),
            "fear_by_cell": [round(float(self.pheromones["fear"][c]), 6) for c in cells],
            "pheromones": self._local_pheromones(p.pos),
        }

    def _queen_view(self, tick: int) -> Dict[str, Any]:
        peaks = {}
        for name in ("trail", "alarm", "recruitment"):
            grid = self.pheromones[name]
            top = float(grid.max())
            at = np.argwhere(grid == top)
            peaks[name] = {"max": round(top, 6), "at": [int(at[0][0]), int(at[0][1])] if at.size else None}
        return {
            "role": "queen",
            "step": tick,
            "grid": [self.width, self.height],
            "nest": list(self.nest),
            "foods": sorted([list(f) for f in self.foods]),
            "ants": [{"id": name, "index": a.index, "pos": list(a.pos), "carrying": a.carrying}
                     for name, a in sorted(self.ants.items())],
            "peaks": peaks,
        }

    # ------------------------------------------------------------- mechanics
    def deposit(self, pos: Pos, name: str, amount: float) -> None:
        if 0 <= pos[0] < self.width and 0 <= pos[1] < self.height:
            grid = self.pheromones[name]
            grid[pos] = min(grid[pos] + amount, self.deposits.max_value)

    def _target(self, pos: Pos, raw: Any) -> Optional[Pos]:
        if not (isinstance(raw, list) and len(raw) == 2 and all(isinstance(c, int) and not isinstance(c, bool)
                                                                for c in raw)):
            return None
        target = (raw[0], raw[1])
        return target if target == pos or target in self.neighbors(pos) else None

    def _apply_ant(self, agent_id: str, ant: Ant, intent: Intent, tick: int) -> Outcome:
        if intent.action != "move":
            self.counters["invalid_actions"] += 1
            return Outcome(False, "unknown_action")
        target = self._target(ant.pos, intent.params.get("to"))
        if target is None:
            self.counters["invalid_actions"] += 1
            return Outcome(False, "bad_move")
        d = self.deposits
        effects: Dict[str, Any] = {}
        was_carrying = ant.carrying
        # Deposits before moving, from the ant's state (legacy order).
        if ant.carrying:
            self.deposit(ant.pos, "trail", d.trail * 0.5)
        elif ant.pos in self.foods:
            self.deposit(ant.pos, "trail", d.trail * 1.5)
        if intent.params.get("escape"):
            self.deposit(ant.pos, "alarm", d.alarm * 2)
            self.counters["escapes"] += 1
        if intent.params.get("api_error"):
            self.deposit(ant.pos, "alarm", d.alarm * 1.5)
        if intent.params.get("guided"):
            self.counters["guided_moves"] += 1
        ant.pos = target
        if ant.pos in self.foods and not ant.carrying:
            ant.carrying = True
            self.foods.discard(ant.pos)
            self._revision += 1
            ant.food_collected += 1
            ant.steps_since_food = 0
            self.counters["food_collected"] += 1
            self.counters["food_collected_by_llm" if ant.is_llm else "food_collected_by_rule"] += 1
            if ant.is_llm:
                self.efficiency[ant.pos] += 10.0
            self.deposit(ant.pos, "trail", d.trail * 2)
            effects["picked_up"] = list(ant.pos)
        near_nest = abs(ant.pos[0] - self.nest[0]) <= 2 and abs(ant.pos[1] - self.nest[1]) <= 2
        if ant.carrying and ant.is_llm:
            if abs(ant.pos[0] - self.nest[0]) + abs(ant.pos[1] - self.nest[1]) <= 2:
                ant.carrying = False
                self.counters["food_delivered"] += 1
                self.deposit(ant.pos, "trail", d.trail * 3)
                effects["delivered"] = True
        else:
            ant.steps_since_food += 1
            if ant.is_llm and ant.steps_since_food > 10 and not ant.carrying:
                self.deposit(ant.pos, "recruitment", d.recruitment)
        if ant.carrying and near_nest and (ant.is_llm or self._rng.random() < 0.3):
            ant.carrying = False
            self.counters["food_delivered"] += 1
            self.deposit(ant.pos, "trail", d.trail * 1.5)
            effects["delivered"] = True
        if ant.carrying != was_carrying or "delivered" in effects:
            ant.flipped_at = tick
        return Outcome(True, effects={"pos": list(ant.pos), **effects})

    def _apply_predator(self, p: Predator, intent: Intent) -> Outcome:
        if p.cooldown > 0:
            p.cooldown -= 1
        if p.energy < 100:
            p.energy = min(100, p.energy + 2)
        self.deposit(p.pos, "fear", self.deposits.fear)
        target = self._target(p.pos, intent.params.get("to")) if intent.action == "move" else None
        if target is None:
            self.counters["invalid_actions"] += 1
            target = p.pos
        p.moves += 1
        p.pos = target
        effects: Dict[str, Any] = {"pos": list(p.pos)}
        if p.cooldown == 0 and p.energy >= 30:
            for name, ant in sorted(self.ants.items()):  # legacy scanned ants in creation order
                if abs(ant.pos[0] - p.pos[0]) + abs(ant.pos[1] - p.pos[1]) <= 2:
                    del self.ants[name]
                    self._revision += 1
                    p.ants_caught += 1
                    p.energy = min(100, p.energy + 20)
                    p.cooldown = 5
                    self.counters["ants_caught"] += 1
                    self.counters["llm_ants_caught" if ant.is_llm else "rule_ants_caught"] += 1
                    self.deposit(p.pos, "fear", self.deposits.fear * 3)
                    effects["caught"] = name
                    break
        return Outcome(True, effects=effects)

    def _apply_queen(self, intent: Intent, tick: int) -> Outcome:
        if intent.rationale:
            self.queen_report = intent.rationale
        if intent.action == "noop":
            return Outcome(True)
        if intent.action != "guide" or not isinstance(intent.params.get("guidance"), dict):
            self.counters["invalid_actions"] += 1
            return Outcome(False, "bad_guidance")
        guided = []
        for name, goal in sorted(intent.params["guidance"].items()):
            ant = self.ants.get(name)
            if ant is None or not (isinstance(goal, list) and len(goal) == 2
                                   and all(isinstance(c, int) and not isinstance(c, bool) for c in goal)
                                   and 0 <= goal[0] < self.width and 0 <= goal[1] < self.height):
                continue
            ant.guidance, ant.guidance_tick = (goal[0], goal[1]), tick
            guided.append(name)
        return Outcome(True, effects={"guided": guided})


def _place_food(rs: np.random.RandomState, width: int, height: int, n_food: int) -> Set[Pos]:
    """Legacy food clusters, drawn in legacy's exact order."""
    foods: Set[Pos] = set()
    n_clusters = max(2, min(4, n_food // 4))
    radius = max(2, min(width, height) // 5)
    nest_x, nest_y = width // 2, height // 2
    min_dist = max(3, min(width, height) // 4)
    centers: List[Pos] = []
    attempts = 0
    while len(centers) < n_clusters and attempts < 100:
        cx, cy = int(rs.randint(1, width - 1)), int(rs.randint(1, height - 1))
        if abs(cx - nest_x) + abs(cy - nest_y) >= min_dist:
            centers.append((cx, cy))
        attempts += 1
    while len(centers) < n_clusters:
        centers.append((int(rs.randint(1, width - 1)), int(rs.randint(1, height - 1))))
    per_cluster = n_food // n_clusters
    for cx, cy in centers:
        placed = tries = 0
        while placed < per_cluster and tries < 50:
            fx = cx + int(rs.randint(-radius, radius + 1))
            fy = cy + int(rs.randint(-radius, radius + 1))
            if 0 <= fx < width and 0 <= fy < height and (fx, fy) not in foods:
                foods.add((fx, fy))
                placed += 1
            tries += 1
    while len(foods) < n_food:
        foods.add((int(rs.randint(width)), int(rs.randint(height))))
    return foods
