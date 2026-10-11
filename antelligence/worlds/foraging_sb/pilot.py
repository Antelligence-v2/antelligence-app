"""``FORAGING_SB``: the foraging_sb world as a v4 pilot ``PilotWorld``.

Privileged methods (``oracle_action``, ``labelled_questions``) read hidden world state and are for labels
and metrics only; no policy or queen may call them during a run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from antelligence.experiments.pilot_contract import BoardSummary, LabelledQuestion
from antelligence.kernel.decision import Question, Sensor
from antelligence.kernel.types import LocalView, Policy, World
from antelligence.worlds.foraging_sb.nav import first_step, next_to
from antelligence.worlds.foraging_sb.scripts import ExploreWhenEmpty, ShortestPath, Unmirror
from antelligence.worlds.foraging_sb.sensing import ACTIONS, CHECKS, FOOD_CHECK, NEST_CHECK, ForagingSensor
from antelligence.worlds.foraging_sb.world import (
    CONDITIONS,
    HEIGHT,
    N_AGENTS,
    STEPS,
    V1_PICKUPS,
    V2_FLIP_TICK,
    WIDTH,
    ForagingSBWorld,
)

MOVE_QUESTION = Question("choice", "Which way should you move now?", options=tuple(ACTIONS), criteria=ACTIONS)
RECENT = 10  # board "recent deliveries" window, in ticks (= the queen cadence)


class ForagingSB:
    name = "foraging_sb"
    actions: Mapping[str, str] = ACTIONS

    def make_world(self, seed: int, condition: str) -> World:
        return ForagingSBWorld(seed, condition, n_pickups=V1_PICKUPS, flip_tick=V2_FLIP_TICK, max_steps=STEPS)

    def sensor(self) -> Sensor:
        return ForagingSensor()

    def script(self, condition: str, *, adapted: bool) -> Policy:
        if condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        if not adapted:
            return ShortestPath()
        if condition == "v1":
            return ExploreWhenEmpty()
        if condition == "v2":
            return Unmirror(V2_FLIP_TICK)
        raise ValueError("S' exists for v1 and v2 only")

    def score(self, world: World) -> float:
        return float(world.deliveries)  # type: ignore[attr-defined]

    def groups(self, world: World) -> Mapping[str, Tuple[str, ...]]:
        ids = sorted(world.agents())
        half = len(ids) // 2
        return {"g1": tuple(ids[:half]), "g2": tuple(ids[half:])}

    def board_summary(self, world: World, tick: int) -> BoardSummary:
        w: ForagingSBWorld = world  # type: ignore[assignment]
        return BoardSummary(tick, {"deliveries": w.deliveries, "carrying": sum(w.carrying.values()),
                                   "recent_deliveries": sum(1 for t in w.delivery_ticks if t > tick - RECENT)})

    def oracle_action(self, world: World, agent_id: str, tick: int) -> str:
        """Shortest path on the true map to the real food (or the nest when carrying)."""
        w: ForagingSBWorld = world  # type: ignore[assignment]
        pos = w.positions[agent_id]
        targets = w.nest if w.carrying[agent_id] else w.food
        goals = set().union(*(next_to(c) for c in targets))
        if pos in goals:
            return "drop" if w.carrying[agent_id] else "pick_up"
        rows = ["".join("#" if (x, y) in w.walls else "F" if (x, y) in w.food else "N" if (x, y) in w.nest else "."
                        for x in range(WIDTH)) for y in range(HEIGHT)]
        return first_step(rows, pos, lambda cell, ch: cell in goals, unknown_ok=False,
                          rot=int(agent_id) % 4) or "stay"

    def labelled_questions(self, world: World, view: LocalView, tick: int) -> List[LabelledQuestion]:
        w: ForagingSBWorld = world  # type: ignore[assignment]
        obs = view.observation
        out: List[LabelledQuestion] = []
        if obs["food_at"] is not None:
            out.append(LabelledQuestion(FOOD_CHECK, "judgement", CHECKS[FOOD_CHECK], tuple(obs["food_at"]) in w.food))
        if obs["nest_at"] is not None:
            out.append(LabelledQuestion(NEST_CHECK, "judgement", CHECKS[NEST_CHECK], tuple(obs["nest_at"]) in w.nest))
        out.append(LabelledQuestion("move", "move", MOVE_QUESTION, self.oracle_action(world, view.agent_id, tick)))
        return out

    def describe(self) -> Dict[str, Any]:
        return {"world": self.name, "version": 1, "agents": N_AGENTS, "steps": STEPS, "actions": list(ACTIONS),
                "v1_pickups": V1_PICKUPS, "v2_flip_tick": V2_FLIP_TICK, "score": "deliveries"}


FORAGING_SB = ForagingSB()
