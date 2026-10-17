"""Graph-colouring world: a seeded, deterministic port of AgentsNet's coloring task.

Credit: AgentsNet (Grotschla et al., MIT; https://github.com/floriangroetschla/AgentsNet,
https://arxiv.org/abs/2507.08616). See README.md for the list of departures.

Round rule, as ported from AgentsNet's ``Coloring`` / ``pass_messages`` (LiteralMessagePassing.py):

* ``rounds`` synchronous rounds (default 4, AgentsNet's default for graphs of <= 16 nodes). One round = one tick.
* In round ``r`` every agent acts at the same time, from what it received at the start of the round. What it
  announces in round ``r`` reaches its neighbours at the start of round ``r + 1`` (messages are never seen in
  the round they are sent). Round 1 therefore starts with nothing heard, and round ``rounds`` is the last
  decision: the colour held after it is the final answer, read once, after round ``rounds``.
* Palette = max degree + 1 colours, so a proper colouring always exists. An agent with no colour at the end
  counts every edge touching it as improper (AgentsNet scores an invalid answer as 0).

Messages are world-owned. Taking a colour (even the colour already held) announces it: the colour is
delivered to every neighbour at the start of the next round, together with an acknowledgement (the colour
the sender last heard from that neighbour). ``noop`` keeps the colour silently. Conditions:

* ``base``  every message is delivered.
* ``v1``    "lost messages": each message is dropped with probability ``DROP_P`` (seeded).
* ``v2``    "one liar": agent ``LIAR_ID`` announces a random colour to each neighbour every round (it
            chatters, whatever it does). The scorer counts only edges between honest agents; this is part of
            what the variant means (the liar's own colour is not scored), the scorer is otherwise identical.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import NOOP, Intent, Observation, Outcome
from antelligence.worlds.graph_coloring.graphs import Graph, family_for_seed, make_graph

N_AGENTS = 8
ROUNDS = 4
DROP_P = 0.3
LIAR_ID = "1"
CONDITIONS = ("base", "v1", "v2")
COLOUR_NAMES = ("red", "blue", "green", "yellow", "orange", "purple", "pink", "brown",
                "teal", "grey", "black", "white", "gold", "navy", "lime", "olive")
MAX_COLOURS = N_AGENTS  # palette is Delta + 1 <= n


def colour_action(index: int) -> str:
    """Action id for colour ``index`` (0-based): colour_1, colour_2, ..."""
    return f"colour_{index + 1}"


def parse_colour_action(action: str, palette: int) -> Optional[int]:
    """Exact lookup of a typed action id; never pattern-matches, so ``colour_10`` can never read as ``colour_1``."""
    return {colour_action(i): i for i in range(palette)}.get(action)


class GraphColoringWorld:
    def __init__(self, seed: int, condition: str = "base", *, n_agents: int = N_AGENTS, rounds: int = ROUNDS,
                 drop_p: float = DROP_P, liar: str = LIAR_ID, family: Optional[str] = None,
                 graph: Optional[Graph] = None) -> None:
        if condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        self.seed, self.condition, self.rounds, self.drop_p = seed, condition, rounds, drop_p
        self.liar = liar if condition == "v2" else None
        self.graph: Graph = graph or make_graph(family or family_for_seed(seed), n_agents, seed)
        self._adj = {str(i): [str(j) for j in nb] for i, nb in self.graph.neighbours().items()}
        self.palette = self.graph.max_degree + 1
        self.colour: Dict[str, Optional[int]] = {a: None for a in self._adj}
        # known[v][u]: last message v received from u (colour, ack, round heard, previous colour)
        self.known: Dict[str, Dict[str, Dict[str, Any]]] = {a: {} for a in self._adj}
        self.fresh: Dict[str, set] = {a: set() for a in self._adj}
        self._drop_rng = random.Random(f"drop:{seed}")
        self._lie_rng = random.Random(f"lie:{seed}")
        self._announcing: set = set()
        self._revision = 0
        self.counters = {"sent": 0, "dropped": 0, "lied": 0, "invalid_actions": 0}
        self.target = self._greedy_target()

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self._adj)

    def neighbours(self, agent_id: str) -> List[str]:
        return list(self._adj[agent_id])

    def describe(self) -> Dict[str, Any]:
        return {"world": "graph_coloring", "version": 1, "seed": self.seed, "condition": self.condition,
                "family": self.graph.family, "n": self.graph.n, "rounds": self.rounds, "palette": self.palette,
                "drop_p": self.drop_p if self.condition == "v1" else 0.0, "liar": self.liar}

    def scene(self) -> Dict[str, Any]:
        return {"kind": "graph", "family": self.graph.family, "palette": self.palette,
                "colours": list(COLOUR_NAMES[: self.palette]), "rounds": self.rounds,
                "nodes": [[a, *self.graph.positions[int(a)]] for a in self.agents()],
                "edges": [[str(u), str(v)] for u, v in self.graph.edges], "liar": self.liar}

    def snapshot(self) -> Dict[str, Any]:
        return {"colours": [self.colour[a] for a in self.agents()], "conflicts": self.conflicts(),
                "uncoloured": sum(c is None for c in self.colour.values()),
                "lost": self.counters["dropped"]}

    def observe(self, agent_id: str, tick: int) -> Observation:
        heard = {}
        for u in self._adj[agent_id]:
            msg = self.known[agent_id].get(u)
            heard[u] = {"colour": msg["colour"] if msg else None, "ack": msg["ack"] if msg else None,
                        "prev": msg["prev"] if msg else None, "round": msg["round"] if msg else None,
                        "fresh": u in self.fresh[agent_id]}
        data = {"agent": agent_id, "round": tick, "rounds": self.rounds, "palette": self.palette,
                "colour": self.colour[agent_id], "neighbours": list(self._adj[agent_id]), "heard": heard}
        return Observation(data=data, sense=SenseQuery(pos=None, radius=0, kinds=frozenset()))

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if intent.action == NOOP:
            return Outcome(True)
        index = parse_colour_action(intent.action, self.palette)
        if index is None:
            self.counters["invalid_actions"] += 1
            return Outcome(False, "unknown_action")
        if self.colour[agent_id] != index:
            self.colour[agent_id] = index
            self._revision += 1
        self._announcing.add(agent_id)  # taking a colour (even the current one) tells the neighbours
        return Outcome(True, effects={"colour": index})

    def step_environment(self, tick: int) -> None:
        """Deliver this round's announcements; they are read at the start of the next round."""
        outgoing = []
        for u in self.agents():
            if u not in self._announcing and u != self.liar:
                continue  # a liar chatters every round; honest agents only when they take a colour
            for v in self._adj[u]:
                announced = self.colour[u]
                if u == self.liar:
                    announced = self._lie_rng.randrange(self.palette)
                    self.counters["lied"] += 1
                if announced is None:
                    continue
                prior = self.known[u].get(v)
                outgoing.append((u, v, announced, prior["colour"] if prior else None))
        self._announcing = set()
        self.fresh = {a: set() for a in self._adj}
        for u, v, announced, ack in outgoing:
            self.counters["sent"] += 1
            if self.condition == "v1" and self._drop_rng.random() < self.drop_p:
                self.counters["dropped"] += 1
                continue
            old = self.known[v].get(u)
            self.known[v][u] = {"colour": announced, "ack": ack, "round": tick,
                                "prev": old["colour"] if old else None}
            self.fresh[v].add(u)
        self._revision += 1

    def done(self, tick: int) -> bool:
        return tick >= self.rounds

    def metrics(self) -> Dict[str, Any]:
        return {"score": self.score(), "conflicts": self.conflicts(),
                "uncoloured": sum(c is None for c in self.colour.values()), **self.counters}

    # -------------------------------------------------------------- scoring
    def scored_edges(self) -> List[Tuple[str, str]]:
        """Edges that count: all of them, except (v2) those touching the liar."""
        return [(str(u), str(v)) for u, v in self.graph.edges if self.liar not in (str(u), str(v))]

    def conflicts(self) -> int:
        return sum(not self._proper(u, v) for u, v in self.scored_edges())

    def score(self) -> float:
        """Fraction of scored edges whose two endpoints hold different colours (exact; no colour = improper)."""
        edges = self.scored_edges()
        return sum(self._proper(u, v) for u, v in edges) / len(edges) if edges else 1.0

    def _proper(self, u: str, v: str) -> bool:
        cu, cv = self.colour[u], self.colour[v]
        return cu is not None and cv is not None and cu != cv

    def _greedy_target(self) -> Dict[str, int]:
        """A proper colouring by name priority (lowest id first); the simulator's reference answer."""
        target: Dict[str, int] = {}
        for a in self.agents():
            used = {target[b] for b in self._adj[a] if b in target}
            target[a] = next(c for c in range(self.palette) if c not in used)
        return target
