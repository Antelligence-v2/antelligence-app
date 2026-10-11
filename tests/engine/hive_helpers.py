"""Tiny choice world, sensor and fake decision backend shared by the hive tests."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional

from antelligence.kernel import BoardField, RunConfig, Scheduler
from antelligence.kernel.decision import Answer, DecisionRequest, DecisionResponse, Question, SensedState, check_answers
from antelligence.kernel.hive import HiveWorld
from antelligence.kernel.types import Intent, LocalView, Observation, Outcome

ACTIONS = {"a": "go to the north patch", "b": "go to the south patch", "c": "wait and rest"}


class ChoiceWorld:
    """Every tick each worker earns a point for the best action. ``best`` is hidden state."""

    def __init__(self, n: int = 4, best: str = "a", switch_at: Optional[int] = None, switch_to: str = "b") -> None:
        self._agents = [f"w{i}" for i in range(n)]
        self.best, self.switch_at, self.switch_to = best, switch_at, switch_to
        self.hits = 0
        self.acts: Dict[str, List[str]] = {}
        self.revision = 0

    def agents(self) -> List[str]:
        return list(self._agents)

    def observe(self, agent_id: str, tick: int) -> Observation:
        return Observation(data={"tick": tick})

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        self.acts.setdefault(agent_id, []).append(intent.action)
        if intent.action == self.best:
            self.hits += 1
        return Outcome(True)

    def step_environment(self, tick: int) -> None:
        if self.switch_at is not None and tick >= self.switch_at:
            self.best = self.switch_to

    def metrics(self) -> Dict[str, Any]:
        return {"hits": self.hits}

    def done(self, tick: int) -> bool:
        return False

    def describe(self) -> Dict[str, Any]:
        return {"world": "choice", "n": len(self._agents), "best": self.best}


class ChoiceSensor:
    def __init__(self, checks: bool = True) -> None:
        self.checks = checks

    def sense(self, view: LocalView) -> SensedState:
        checks = {"plan": Question("noul", "Is the plan you follow still good?")} if self.checks else {}
        return SensedState(f"It is step {view.observation['tick']}. You may pick a patch.", {}, ACTIONS, checks)

    def describe(self) -> Dict[str, Any]:
        return {"sensor": "choice", "checks": self.checks}


def board_summary(world: Any, tick: int) -> Mapping[str, Any]:
    return {"hits": world.hits}


Chooser = Callable[[DecisionRequest], str]


class FakeBackend:
    """Deterministic DecisionBackend: ``chooser`` picks the move, ``p_yes`` answers every noul."""

    def __init__(self, chooser: Optional[Chooser] = None, p_yes: float = 0.9, escalated: tuple = (),
                 fail: bool = False) -> None:
        self.chooser = chooser or (lambda req: next(o for o in req.questions["move"].options if o != "report"))
        self.p_yes, self.escalated, self.fail = p_yes, escalated, fail
        self.requests: List[DecisionRequest] = []

    def describe(self) -> Dict[str, Any]:
        return {"backend": "fake"}

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("backend down")
        answers: Dict[str, Answer] = {}
        for qid, q in request.questions.items():
            if q.type == "noul":
                answers[qid] = Answer("noul", self.p_yes, {"yes": self.p_yes, "no": 1 - self.p_yes})
            else:
                pick = self.chooser(request)
                rest = [o for o in q.options if o != pick]
                probs = {pick: 0.7, **{o: 0.3 / len(rest) for o in rest}}
                answers[qid] = Answer("choice", pick, probs, 0.7)
        check_answers(request, answers)
        return DecisionResponse(answers, "fake-model", request.request_hash, 10, 2, escalated=self.escalated)


def run(world: Any, policies: Mapping[str, Any], seed: int = 100, ticks: int = 6, queen: bool = True) -> Scheduler:
    hive = HiveWorld(world, board_summary, queen=queen)
    sched = Scheduler(hive, policies, BoardField(), RunConfig(seed=seed, max_ticks=ticks, run_id="t", arm="x"))
    sched.run()
    return sched


def decided(sched: Scheduler, agent: str) -> List[Any]:
    return [e for e in sched.log.of_type("decided") if e.agent_id == agent]
