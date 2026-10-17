"""A tiny fake PilotWorld for the v4 harness tests (no real world is imported).

Three agents pick "up" or "down" for 6 ticks; the score is the share of picks that match the hidden best
action. Base: "up". v1: "down". v2: "down" on odd ticks. The observation carries a ``broken`` hint that
S' reads and S ignores, so S' keeps base performance and S fails the variants. ``harmless=("v2",)`` makes
v2 not hurt S (an invalid variant for the validity check).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from antelligence.experiments.pilot_contract import BoardSummary, LabelledQuestion
from antelligence.kernel.decision import Question, SensedState
from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import Intent, LocalView, Observation, Outcome

TICKS = 6


def best(condition: str, tick: int) -> str:
    return "down" if condition == "v1" or (condition == "v2" and tick % 2 == 1) else "up"


class FakeWorld:
    def __init__(self, seed: int, condition: str, harmless: Tuple[str, ...] = ()) -> None:
        self.seed, self.condition, self.harmless = seed, condition, harmless
        self.hits = 0
        self.picks = 0
        self.t = 0
        self._rev = 0

    @property
    def revision(self) -> int:
        return self._rev

    def agents(self) -> List[str]:
        return ["w0", "w1", "w2"]

    def effective(self, tick: int) -> str:
        return "up" if self.condition in self.harmless else best(self.condition, tick)

    def observe(self, agent_id: str, tick: int) -> Observation:
        return Observation({"tick": tick, "broken": self.effective(tick) == "down"},
                           SenseQuery(topic="board", kinds=frozenset({"queen"})))

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if intent.action in ("up", "down"):
            self.picks += 1
            self.hits += intent.action == self.effective(tick)
        return Outcome(True)  # NOOP and report are accepted with no effect

    def step_environment(self, tick: int) -> None:
        self.t = tick
        self._rev += 1

    def metrics(self) -> Dict[str, Any]:
        return {"hits": self.hits, "picks": self.picks}

    def done(self, tick: int) -> bool:
        return tick >= TICKS

    def describe(self) -> Dict[str, Any]:
        return {"world": "fake", "seed": self.seed, "condition": self.condition, "max_ticks": TICKS}

    def snapshot(self) -> Dict[str, Any]:
        return {"hits": self.hits}

    def scene(self) -> Dict[str, Any]:
        return {"agents": 3}


class FakeSensor:
    def sense(self, view: LocalView) -> SensedState:
        broken = view.observation["broken"]
        return SensedState(f"Tick {view.observation['tick']}. Assumption broken: {'yes' if broken else 'no'}.",
                           {"broken": broken}, {"up": "go up", "down": "go down"},
                           {"intact": Question("noul", "Does the usual rule still hold?")})

    def describe(self) -> Dict[str, Any]:
        return {"sensor": "fake"}


class ScriptPolicy:
    def __init__(self, adapted: bool) -> None:
        self.adapted = adapted

    def decide(self, view: LocalView) -> Intent:
        return Intent("down" if self.adapted and view.observation["broken"] else "up")

    def describe(self) -> Dict[str, Any]:
        return {"script": "fake", "adapted": self.adapted}


class FakePilotWorld:
    actions: Mapping[str, str] = {"up": "go up", "down": "go down"}
    instructions = "Task: go up as often as you can."

    def __init__(self, name: str = "fake_world", harmless: Tuple[str, ...] = ()) -> None:
        self.name, self.harmless = name, harmless

    def make_world(self, seed: int, condition: str) -> FakeWorld:
        return FakeWorld(seed, condition, self.harmless)

    def sensor(self) -> FakeSensor:
        return FakeSensor()

    def script(self, condition: str, *, adapted: bool) -> ScriptPolicy:
        return ScriptPolicy(adapted)

    def score(self, world: FakeWorld) -> float:
        return world.hits / world.picks if world.picks else 0.0

    def groups(self, world: FakeWorld) -> Dict[str, Tuple[str, ...]]:
        return {"g": ("w0", "w1", "w2")}

    def board_summary(self, world: FakeWorld, tick: int) -> BoardSummary:
        return BoardSummary(tick, {"hits": world.hits})

    def oracle_action(self, world: FakeWorld, agent_id: str, tick: int) -> str:
        return world.effective(tick)

    def oracle_actions(self, world: FakeWorld, agent_id: str, tick: int) -> Tuple[str, ...]:
        return (world.effective(tick),)

    def labelled_questions(self, world: FakeWorld, view: LocalView, tick: int) -> List[LabelledQuestion]:
        truth = world.effective(tick)
        return [LabelledQuestion("intact", "judgement", Question("noul", "Does the usual rule still hold?"),
                                 truth == "up"),
                LabelledQuestion("move", "move", Question("choice", "Which action?", ("up", "down")), truth)]

    def describe(self) -> Dict[str, Any]:
        return {"world": self.name, "max_ticks": TICKS}


FAKE_A = FakePilotWorld("fake_a")
FAKE_B = FakePilotWorld("fake_b")
FAKE_BAD = FakePilotWorld("fake_bad", harmless=("v2",))
