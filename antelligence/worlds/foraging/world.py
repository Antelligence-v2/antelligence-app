"""Chain-prioritized foraging world (E13) on the engine.

Mechanics follow E13 exactly: 10x10 grid, 3 agents, 3 foods delivered in
chain order 0 -> 1 -> 2, view 5x5, auto-pick on stepping onto food
(multi-carry), auto-drop at the nest in chain order. Agents choose FOLLOW
(one step toward a target they name) or SWEEP (next cell of their own
deterministic snake path); the world executes the step.

Two deliberate differences from the E13 harness, both toward stricter
evidence handling:

* **No ground-truth recall filter.** E13 filtered memory hits against
  ``env["foods_remaining"]``. Here picking up a food is a world outcome that
  replaces the ``food:<i>`` source, so stale claims are invalidated by the
  trust layer rather than by peeking at true state.
* **Simultaneous decisions.** All agents decide from the same pre-tick state
  (kernel contract); E13 let later agents see earlier agents' moves within a
  step. Absolute numbers are therefore not expected to match E13's LLM runs;
  the deterministic fixture/oracle parity is what is checked.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import Intent, Observation, Outcome
from antelligence.worlds.foraging.fixtures import (
    AGENTS,
    DIRS,
    HEIGHT,
    N_FOOD,
    STEPS,
    VIEW_K,
    WIDTH,
    Pos,
    env_for,
    step_toward,
    sweep_path,
)

FOLLOW = "follow"
SWEEP = "sweep"
NOOP = "noop"


def food_subject(index: int) -> str:
    return f"food:{index}"


class ChainForagingWorld:
    def __init__(self, seed: int, *, max_steps: int = STEPS, hearing: float = 0.0) -> None:
        self.seed = seed
        self.max_steps = max_steps
        self.hearing = hearing
        starts, nest, foods, food_index = env_for(seed)
        self.nest: Pos = nest
        self.foods: List[Pos] = list(foods)
        self.food_index: Dict[Pos, int] = dict(food_index)
        self.remaining: List[Pos] = list(foods)
        self.positions: Dict[str, Pos] = {str(i): starts[i] for i in range(AGENTS)}
        self.carrying: Dict[str, Set[Pos]] = {a: set() for a in self.positions}
        self.sweeps = {a: sweep_path(starts[int(a)]) for a in self.positions}
        self.sweep_idx = {a: 0 for a in self.positions}
        self.next_needed = 0
        self.delivered = 0
        self._revision = 0
        self.steps_to_success: Optional[int] = None
        self.counters = {"sweep_moves": 0, "directed_moves": 0, "idle": 0, "invalid_actions": 0}

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self.positions)

    def describe(self) -> Dict[str, Any]:
        return {"world": "chain_foraging", "version": 1, "seed": self.seed, "max_steps": self.max_steps,
                "grid": [WIDTH, HEIGHT], "view_k": VIEW_K, "agents": AGENTS, "n_food": N_FOOD,
                "hearing": self.hearing}

    def observe(self, agent_id: str, tick: int) -> Observation:
        pos = self.positions[agent_id]
        r = VIEW_K // 2
        visible = [[f[0], f[1], self.food_index[f]] for f in self.remaining
                   if abs(f[0] - pos[0]) <= r and abs(f[1] - pos[1]) <= r]
        data = {
            "pos": list(pos),
            "nest": list(self.nest),
            "grid": [WIDTH, HEIGHT],
            "visible_foods": visible,
            "carrying": [[c[0], c[1], self.food_index[c]] for c in sorted(self.carrying[agent_id])],
            "next_needed": self.next_needed,
            "delivered": self.delivered,
        }
        sense = SenseQuery(pos=pos, radius=self.hearing) if self.hearing > 0 else SenseQuery(pos=pos, radius=0,
                                                                                               kinds=frozenset())
        return Observation(data=data, sense=sense)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if self.delivered == N_FOOD:
            return Outcome(True, "already_complete")
        pos = self.positions[agent_id]
        if intent.action == NOOP:
            self.counters["idle"] += 1
            return Outcome(True)
        if intent.action == FOLLOW:
            target = intent.params.get("target")
            if not (isinstance(target, list) and len(target) == 2 and all(isinstance(c, int) for c in target)
                    and 0 <= target[0] < WIDTH and 0 <= target[1] < HEIGHT):
                self.counters["invalid_actions"] += 1
                return Outcome(False, "bad_target")
            move = step_toward(pos, (target[0], target[1]))
            new = (pos[0] + DIRS[move][0], pos[1] + DIRS[move][1]) if move else (target[0], target[1])
            self.counters["directed_moves"] += 1
        elif intent.action == SWEEP:
            new = self._sweep_step(agent_id, pos)
        else:
            self.counters["invalid_actions"] += 1
            return Outcome(False, "unknown_action")
        self.positions[agent_id] = new
        changed = self._pick_and_drop(agent_id, new, tick)
        effects: Dict[str, Any] = {"pos": list(new)}
        if changed:
            effects["subjects_changed"] = changed
        if self.delivered:
            effects["delivered"] = self.delivered
        return Outcome(True, effects=effects)

    def step_environment(self, tick: int) -> None:
        pass

    def metrics(self) -> Dict[str, Any]:
        return {
            "success": self.delivered == N_FOOD,
            "steps_to_success": self.steps_to_success,
            "deliveries": self.delivered,
            **self.counters,
        }

    def done(self, tick: int) -> bool:
        return self.delivered == N_FOOD or tick >= self.max_steps

    # ------------------------------------------------------------ mechanics
    def _sweep_step(self, agent_id: str, pos: Pos) -> Pos:
        path = self.sweeps[agent_id]
        while self.sweep_idx[agent_id] < len(path):
            cell = path[self.sweep_idx[agent_id]]
            self.sweep_idx[agent_id] += 1
            if cell != pos:
                move = step_toward(pos, cell)
                if move:
                    self.counters["sweep_moves"] += 1
                    return pos[0] + DIRS[move][0], pos[1] + DIRS[move][1]
        return pos

    def _pick_and_drop(self, agent_id: str, pos: Pos, tick: int) -> List[str]:
        changed: List[str] = []
        if pos in self.remaining:
            self.remaining.remove(pos)
            self.carrying[agent_id].add(pos)
            changed.append(food_subject(self.food_index[pos]))
            self._revision += 1
        carried = self.carrying[agent_id]
        if pos == self.nest and carried:
            while True:
                drop = next((c for c in carried if self.food_index[c] == self.next_needed), None)
                if drop is None:
                    break
                carried.remove(drop)
                self.delivered += 1
                self.next_needed += 1
                self._revision += 1
                if self.delivered == N_FOOD:
                    self.steps_to_success = tick
                    break
        return changed
