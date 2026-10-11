"""DecisionWorker: a framework-arm agent that asks a decision model one move question per tick.

Per tick: sense -> restrict to the queen's allowed actions -> one request with a ``move``
choice (allowed actions plus REPORT) and up to ``max_checks`` judgement nouls ->
act. The worker cannot pick an action outside the allowed set: the request only offers
those options and the answer is re-checked here. Escalation to a stronger model happens
inside the backend (``response.escalated``); this class only records it.

A REPORT answer, or any check with P(yes) < 0.5, posts a ``report`` signal on the board
(visible to the queen next tick). REPORT acts NOOP. Meta carries no wall-clock, so
traces replay hash-equal. Backend errors fail closed to NOOP with the reason in meta.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from antelligence.kernel.decision import REPORT, DecisionBackend, DecisionRequest, Question, Sensor
from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import NOOP, Intent, LocalView

MAX_REASON = 120
REPORT_DESCRIPTION = "report: my local evidence disagrees"
P_CHECK = 0.5


def _newest_queen_signal(view: LocalView, group: str):
    mine = [s for s in view.signals if s.kind == "queen" and s.payload.get("group") == group]
    return max(mine, key=lambda s: (s.emitted_at, s.id)) if mine else None


def latest_queen_allowed(view: LocalView, group: str) -> Optional[List[str]]:
    """Allowed actions from the newest queen signal for ``group`` in the view, else None."""
    newest = _newest_queen_signal(view, group)
    if newest is None:
        return None
    allowed = newest.payload.get("allowed", [])
    return [a for a in allowed if isinstance(a, str)] if isinstance(allowed, list) else []


def latest_queen_goal(view: LocalView, group: str) -> Optional[str]:
    """The goal text of the newest queen signal for ``group``, else None."""
    newest = _newest_queen_signal(view, group)
    goal = newest.payload.get("goal") if newest is not None else None
    return goal[:MAX_REASON] if isinstance(goal, str) and goal else None


class DecisionWorker:
    def __init__(self, backend: DecisionBackend, sensor: Sensor, group: str, *, model: str,
                 use_queen: bool = True, max_checks: int = 2, report_ttl: int = 10) -> None:
        if max_checks < 0 or report_ttl < 1:
            raise ValueError("max_checks must be >= 0 and report_ttl >= 1")
        self.backend = backend
        self.sensor = sensor
        self.group = group
        self.model = model
        self.use_queen = use_queen
        self.max_checks = max_checks
        self.report_ttl = report_ttl

    def describe(self) -> Dict[str, Any]:
        return {"policy": "decision_worker", "group": self.group, "model": self.model, "use_queen": self.use_queen,
                "max_checks": self.max_checks, "report_ttl": self.report_ttl, "backend": self.backend.describe(),
                "sensor": self.sensor.describe()}

    def _allowed(self, view: LocalView, offered: Mapping[str, str]) -> List[str]:
        queen = latest_queen_allowed(view, self.group) if self.use_queen else None
        if queen is None:
            return sorted(offered)
        return sorted(set(queen) & set(offered))

    def _report(self, view: LocalView, reason: str, failed: List[str]) -> SignalDraft:
        return SignalDraft(kind="report", topic="board", ttl=self.report_ttl,
                           payload={"group": self.group, "tick": view.tick, "failed": failed,
                                    "reason": reason[:MAX_REASON]})

    async def decide(self, view: LocalView) -> Intent:
        sensed = self.sensor.sense(view)
        allowed = self._allowed(view, sensed.actions)
        base: Dict[str, Any] = {"policy": "decision_worker", "group": self.group, "allowed": allowed}
        if not allowed:
            report = self._report(view, "no allowed action applies to my state", [])
            return Intent(NOOP, emit=(report,), meta={**base, "reason": "empty_allowed", "reported": True})
        criteria = {a: sensed.actions[a] for a in allowed}
        criteria[REPORT] = REPORT_DESCRIPTION
        goal = latest_queen_goal(view, self.group) if self.use_queen else None
        instructions = "Which action?" if goal is None else f"Which action? Your group's goal: {goal}"
        questions: Dict[str, Question] = {
            "move": Question("choice", instructions, tuple(allowed) + (REPORT,), criteria)}
        for qid in sorted(sensed.checks)[: self.max_checks]:
            if qid != "move":
                questions[qid] = sensed.checks[qid]
        try:
            request = DecisionRequest.build(self.model, sensed.text, questions, seed=view.seed)
            response = await self.backend.decide(request)
            move = response.answers["move"].value
            if move not in allowed and move != REPORT:
                raise ValueError(f"backend chose {move!r} outside the offered options")
            p_yes = {qid: response.answers[qid].p_yes for qid in questions if qid != "move"}
        except Exception as exc:  # fail closed, loudly: NOOP with the reason recorded
            return Intent(NOOP, meta={**base, "reason": f"backend_error:{type(exc).__name__}:{str(exc)[:100]}",
                                      "reported": False})
        failed = sorted(qid for qid, p in p_yes.items() if p < P_CHECK)
        reported = move == REPORT or bool(failed)
        move_probs = response.answers["move"].probabilities
        meta = {**base, "offered": list(request.questions["move"].options), "answer": move,
                "move_probabilities": {k: round(v, 4) for k, v in sorted(move_probs.items())},
                "p_yes": {k: round(v, 4) for k, v in sorted(p_yes.items())}, "failed_checks": failed,
                "escalated": list(response.escalated), "reported": reported, **response.accounting()}
        emit = ()
        if reported:
            parts = ["I disagree with the allowed actions"] if move == REPORT else []
            parts += [f"{qid}: {questions[qid].instructions[:50]} (p={p_yes[qid]:.2f})" for qid in failed]
            emit = (self._report(view, "; ".join(parts), failed),)
        return Intent(NOOP if move == REPORT else move, emit=emit, meta=meta)
