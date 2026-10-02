"""A tiny grid-foraging world used to exercise the kernel contracts."""

from __future__ import annotations

import asyncio
import random
from typing import Dict, List, Tuple

from antelligence.kernel import Intent, LocalView, Observation, Outcome, SenseQuery, SignalDraft

MOVES = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "w": (-1, 0)}


class ToyWorld:
    def __init__(self, size: int = 8, agents: int = 3, food: List[Tuple[int, int]] | None = None,
                 sight: int = 1, hearing: float = 6.0, hazardous_misfire: bool = False) -> None:
        # hazardous_misfire: collecting where there is no food "succeeds" but is
        # unsafe (models delivering payload to healthy tissue).
        self.hazardous_misfire = hazardous_misfire
        self.size = size
        self.sight = sight
        self.hearing = hearing
        self._agents: Dict[str, Tuple[int, int]] = {f"a{i}": (0, i % size) for i in range(agents)}
        self.food = set(food if food is not None else [(size - 1, size - 1), (size - 2, 1)])
        self._initial_food = sorted(self.food)
        self.collected = 0
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return list(self._agents)

    def position(self, agent_id: str) -> Tuple[int, int]:
        return self._agents[agent_id]

    def observe(self, agent_id: str, tick: int) -> Observation:
        x, y = self._agents[agent_id]
        visible = sorted(f for f in self.food if abs(f[0] - x) <= self.sight and abs(f[1] - y) <= self.sight)
        return Observation(
            data={"pos": [x, y], "food": [list(f) for f in visible], "size": self.size},
            sense=SenseQuery(pos=(x, y), radius=self.hearing),
        )

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        x, y = self._agents[agent_id]
        if intent.action == "noop":
            return Outcome(True)
        if intent.action == "move":
            dx, dy = MOVES.get(intent.params.get("dir"), (None, None))
            if dx is None:
                return Outcome(False, "bad_direction")
            nx, ny = x + dx, y + dy
            if not (0 <= nx < self.size and 0 <= ny < self.size):
                return Outcome(False, "out_of_bounds")
            self._agents[agent_id] = (nx, ny)
            return Outcome(True, effects={"pos": [nx, ny]})
        if intent.action == "collect":
            if (x, y) not in self.food:
                if self.hazardous_misfire:
                    return Outcome(True, "misfire", effects={"unsafe": True, "misfire": [x, y]})
                return Outcome(False, "no_food_here")
            self.food.discard((x, y))
            self.collected += 1
            self._revision += 1
            return Outcome(True, effects={"collected": [x, y], "subjects_changed": [food_subject((x, y))]})
        return Outcome(False, "unknown_action")

    def step_environment(self, tick: int) -> None:
        pass

    def metrics(self) -> Dict[str, int]:
        return {"collected": self.collected, "remaining": len(self.food)}

    def done(self, tick: int) -> bool:
        return not self.food

    def describe(self) -> Dict[str, object]:
        return {"world": "toy", "size": self.size, "agents": len(self._agents),
                "food": [list(f) for f in self._initial_food], "sight": self.sight, "hearing": self.hearing,
                "hazardous_misfire": self.hazardous_misfire}


def food_subject(pos) -> str:
    return f"food:{int(pos[0])},{int(pos[1])}"


def _step_toward(pos, target) -> str:
    if target[0] > pos[0]:
        return "e"
    if target[0] < pos[0]:
        return "w"
    return "n" if target[1] > pos[1] else "s"


class ForagerPolicy:
    """Collect visible food, announce it, follow heard announcements, else wander."""

    def __init__(self, use_signals: bool = True) -> None:
        self.use_signals = use_signals

    def decide(self, view: LocalView) -> Intent:
        pos = tuple(view.observation["pos"])
        food = [tuple(f) for f in view.observation["food"]]
        if pos in food:
            return Intent("collect")
        if food:
            target = min(food)
            emit = (SignalDraft(kind="found", pos=target, ttl=5),) if self.use_signals else ()
            return Intent("move", {"dir": _step_toward(pos, target)}, emit=emit)
        if self.use_signals and view.signals:
            target = tuple(int(c) for c in view.signals[0].pos)
            if target != pos:
                return Intent("move", {"dir": _step_toward(pos, target)})
        rng = random.Random(view.seed)
        return Intent("move", {"dir": rng.choice(sorted(MOVES))})

    def describe(self) -> Dict[str, object]:
        return {"policy": "forager", "use_signals": self.use_signals}


class SlowAsyncForager(ForagerPolicy):
    """Same decisions, but answers after a random delay (simulates LLM latency)."""

    def __init__(self, jitter_seed: int, use_signals: bool = True) -> None:
        super().__init__(use_signals)
        self._jitter = random.Random(jitter_seed)

    async def decide(self, view: LocalView) -> Intent:  # type: ignore[override]
        await asyncio.sleep(self._jitter.random() * 0.002)
        return ForagerPolicy.decide(self, view)


class RememberingForager(ForagerPolicy):
    """Acts on recalled food claims and cites them.

    With ``private_cache=True`` it also keeps its own copy of every record it
    has seen and keeps acting on it after the shared memory invalidated it —
    the stale-memory failure the evidence gate must block.
    """

    def __init__(self, private_cache: bool = False) -> None:
        super().__init__(use_signals=True)
        self.private_cache = private_cache
        self.cache = {}

    def decide(self, view: LocalView) -> Intent:
        pos = tuple(view.observation["pos"])
        visible = [tuple(f) for f in view.observation["food"]]
        for record in view.memory:
            self.cache[view.agent_id, record.subject] = record
        known = [r for r in view.memory if r.body.get("kind") == "found"]
        if self.private_cache:
            known = [r for (agent, _), r in sorted(self.cache.items()) if agent == view.agent_id]
        for record in sorted(known, key=lambda r: (r.subject, r.id)):
            target = tuple(int(c) for c in record.body["pos"])
            if target == pos:
                return Intent("collect", cites=(record.id,))
        if pos in visible:
            return Intent("collect")
        if visible:
            target = min(visible)
            return Intent("move", {"dir": _step_toward(pos, target)},
                          emit=(SignalDraft(kind="found", pos=target, ttl=5),))
        if known:
            target = tuple(int(c) for c in sorted(known, key=lambda r: r.subject)[0].body["pos"])
            return Intent("move", {"dir": _step_toward(pos, target)})
        rng = random.Random(view.seed)
        return Intent("move", {"dir": rng.choice(sorted(MOVES))})

    def describe(self) -> Dict[str, object]:
        return {"policy": "remembering", "private_cache": self.private_cache}
