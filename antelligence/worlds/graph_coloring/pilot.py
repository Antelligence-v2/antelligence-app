"""PilotWorld for graph_coloring: wires world, sensor, scripts, groups, board summary and simulator labels.

Graph family per seed (documented mapping): ``seed % 3`` -> 0 Watts-Strogatz, 1 Barabasi-Albert, 2 Delaunay,
so consecutive seeds cycle through the families; the graph itself (and its Delta + 1 palette) is the same in
every condition of that seed. Two fixed groups for the queen: agents 0-3 ("g1") and 4-7 ("g2").
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from antelligence.experiments.pilot_contract import BoardSummary, LabelledQuestion
from antelligence.kernel.decision import Question, Sensor
from antelligence.kernel.types import NOOP, LocalView, Policy, World
from antelligence.worlds.graph_coloring import scripts
from antelligence.worlds.graph_coloring.sensing import ColoringSensor
from antelligence.worlds.graph_coloring.world import (
    COLOUR_NAMES,
    CONDITIONS,
    LIAR_ID,
    MAX_COLOURS,
    ROUNDS,
    GraphColoringWorld,
    colour_action,
)


class GraphColoringPilot:
    name = "graph_coloring"
    actions: Mapping[str, str] = {
        **{colour_action(i): f"Take {COLOUR_NAMES[i]} (tells your neighbours)" for i in range(MAX_COLOURS)},
        NOOP: "Keep your current colour (silent)",
    }

    def make_world(self, seed: int, condition: str) -> World:
        return GraphColoringWorld(seed, condition)

    def sensor(self) -> Sensor:
        return ColoringSensor()

    def script(self, condition: str, *, adapted: bool) -> Policy:
        if condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        if not adapted:
            return scripts.PatientGreedy(self.sensor())
        if condition == "v1":
            return scripts.ResendUntilAcked(self.sensor())
        if condition == "v2":
            return scripts.IgnoreLiar(self.sensor(), LIAR_ID)
        raise ValueError("S' exists for v1 and v2 only")

    def score(self, world: World) -> float:
        return _w(world).score()

    def groups(self, world: World) -> Mapping[str, Tuple[str, ...]]:
        agents = _w(world).agents()
        half = len(agents) // 2
        return {"g1": tuple(agents[:half]), "g2": tuple(agents[half:])}

    def board_summary(self, world: World, tick: int) -> BoardSummary:
        w = _w(world)
        return BoardSummary(tick, {"round": tick, "conflicts_left": w.conflicts(),
                                   "uncoloured": sum(c is None for c in w.colour.values()),
                                   "edges_scored": len(w.scored_edges())})

    def oracle_action(self, world: World, agent_id: str, tick: int) -> str:
        """Privileged: the first of ``oracle_actions``."""
        return self.oracle_actions(world, agent_id, tick)[0]

    def oracle_actions(self, world: World, agent_id: str, tick: int) -> Tuple[str, ...]:
        """Privileged: NOOP if my colour clashes with no neighbour's true colour, else every palette colour no
        neighbour truly holds now (palette order), else the reference colour."""
        w = _w(world)
        held = {w.colour[u] for u in w.neighbours(agent_id)}
        if w.colour[agent_id] is not None and w.colour[agent_id] not in held:
            return (NOOP,)
        free = tuple(colour_action(c) for c in range(w.palette) if c not in held)
        return free or (colour_action(w.target[agent_id]),)

    def labelled_questions(self, world: World, view: LocalView, tick: int) -> List[LabelledQuestion]:
        w = _w(world)
        sensed = self.sensor().sense(view)
        nbrs = w.neighbours(view.agent_id)
        truth = {"heard_all": all(u in w.fresh[view.agent_id] for u in nbrs),
                 "reports_true": not (w.liar in nbrs and w.liar in w.fresh[view.agent_id])}
        out = [LabelledQuestion(qid, "judgement", q, truth[qid]) for qid, q in sensed.checks.items()]
        move = Question("choice", "Which action should you take now?", tuple(sensed.actions),
                        criteria=dict(sensed.actions))
        good = self.oracle_actions(world, view.agent_id, tick)
        out.append(LabelledQuestion("move", "move", move, good[0], accept=good))
        return out

    def describe(self) -> Dict[str, Any]:
        return {"world": self.name, "conditions": list(CONDITIONS), "liar": LIAR_ID, "max_ticks": ROUNDS,
                "groups": "ids 0-3 / 4-7", "family_by_seed": "seed % 3 -> ws, ba, dt"}


def _w(world: World) -> GraphColoringWorld:
    if not isinstance(world, GraphColoringWorld):
        raise TypeError("expected a GraphColoringWorld")
    return world


GRAPH_COLORING = GraphColoringPilot()
