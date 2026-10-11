import asyncio
import random

from antelligence.kernel import Signal
from antelligence.kernel.decision import REPORT
from antelligence.kernel.policies.decision_worker import DecisionWorker
from antelligence.kernel.types import NOOP, LocalView
from tests.engine.hive_helpers import ACTIONS, ChoiceSensor, ChoiceWorld, FakeBackend, decided, run


def queen_signal(group="g", allowed=("a", "b"), tick=1, ttl=5, goal="go") -> Signal:
    return Signal(sender="queen", scope="s", kind="queen", emitted_at=tick, revision=0, ttl=ttl, topic="board",
                  payload={"group": group, "goal": goal, "allowed": list(allowed)})


def view(signals=(), seed=1, tick=2) -> LocalView:
    return LocalView("w0", tick, 0, seed, {"tick": tick}, tuple(signals))


def worker(backend, **kw) -> DecisionWorker:
    return DecisionWorker(backend, ChoiceSensor(), "g", model="m", **kw)


def decide(w, v):
    return asyncio.run(w.decide(v))


def test_without_queen_signal_all_actions_offered():
    backend = FakeBackend()
    decide(worker(backend), view())
    assert set(backend.requests[0].questions["move"].options) == set(ACTIONS) | {REPORT}


def test_use_queen_false_ignores_queen_signal():
    backend = FakeBackend()
    decide(worker(backend, use_queen=False), view([queen_signal(allowed=("a",))]))
    assert set(backend.requests[0].questions["move"].options) == set(ACTIONS) | {REPORT}


def test_never_acts_outside_allowed_property():
    rng = random.Random(0)
    for seed in range(100, 160):
        allowed = rng.sample(sorted(ACTIONS), rng.randint(1, 3))
        # adversarial chooser: prefers an action that is NOT allowed whenever one is offered
        backend = FakeBackend(chooser=lambda req: req.questions["move"].options[-1])
        intent = decide(worker(backend), view([queen_signal(allowed=allowed)], seed=seed))
        assert intent.action in set(allowed) | {NOOP}
        assert intent.meta["allowed"] == sorted(allowed)


def test_backend_choosing_off_list_fails_closed():
    class Rogue(FakeBackend):
        async def decide(self, request):
            resp = await super().decide(request)
            from antelligence.kernel.decision import Answer
            bad = dict(resp.answers)
            bad["move"] = Answer("choice", "c", {"c": 1.0})
            return type(resp)(bad, resp.served_model, resp.request_hash)

    intent = decide(worker(Rogue()), view([queen_signal(allowed=("a",))]))
    assert intent.action == NOOP and intent.meta["reason"].startswith("backend_error")


def test_intersection_with_sensed_actions_and_empty_case():
    backend = FakeBackend()
    intent = decide(worker(backend), view([queen_signal(allowed=("zzz",))]))
    assert intent.action == NOOP and intent.meta["reason"] == "empty_allowed"
    assert [d.kind for d in intent.emit] == ["report"] and not backend.requests


def test_newest_queen_signal_and_other_group_ignored():
    backend = FakeBackend()
    sigs = [queen_signal(allowed=("a",), tick=1), queen_signal(allowed=("b", "c"), tick=3),
            queen_signal(group="other", allowed=("a",), tick=4)]
    intent = decide(worker(backend), view(sigs, tick=5))
    assert intent.meta["allowed"] == ["b", "c"]


def test_report_move_posts_report_and_noops():
    backend = FakeBackend(chooser=lambda req: REPORT)
    intent = decide(worker(backend), view())
    assert intent.action == NOOP and intent.meta["reported"] is True
    (draft,) = intent.emit
    assert draft.kind == "report" and draft.topic == "board"
    assert draft.payload["group"] == "g" and draft.payload["tick"] == 2 and len(draft.payload["reason"]) <= 120


def test_failed_check_posts_report_but_acts():
    backend = FakeBackend(p_yes=0.2)
    intent = decide(worker(backend), view())
    assert intent.action != NOOP and intent.meta["failed_checks"] == ["plan"]
    (draft,) = intent.emit
    assert draft.payload["failed"] == ["plan"] and len(draft.payload["reason"]) <= 120


def test_passing_checks_no_report_and_max_checks():
    backend = FakeBackend(p_yes=0.9)
    intent = decide(worker(backend), view())
    assert intent.emit == () and intent.meta["reported"] is False and "plan" in backend.requests[0].questions
    backend2 = FakeBackend()
    decide(worker(backend2, max_checks=0), view())
    assert set(backend2.requests[0].questions) == {"move"}


def test_backend_error_fails_closed_with_reason():
    intent = decide(worker(FakeBackend(fail=True)), view())
    assert intent.action == NOOP and "backend_error:RuntimeError" in intent.meta["reason"]


def test_meta_records_escalation_and_has_no_wallclock():
    intent = decide(worker(FakeBackend(escalated=("move",))), view())
    assert intent.meta["escalated"] == ["move"] and intent.meta["model"] == "fake-model"
    assert not {"elapsed_s", "cached", "latency_s"} & set(intent.meta)
    assert set(intent.meta["offered"]) == set(ACTIONS) | {REPORT}


def test_options_shuffled_by_seed():
    orders = set()
    for seed in range(100, 120):
        backend = FakeBackend()
        decide(worker(backend), view(seed=seed))
        orders.add(backend.requests[0].questions["move"].options)
    assert len(orders) > 1


def test_deterministic_trace_hash():
    def go():
        pol = {a: worker(FakeBackend(p_yes=0.4)) for a in ChoiceWorld(n=3).agents()}
        return run(ChoiceWorld(n=3), pol, seed=101, queen=False).log.trace_hash

    assert go() == go()


def test_in_scheduler_decided_meta_has_allowed():
    pol = {a: worker(FakeBackend()) for a in ChoiceWorld(n=2).agents()}
    sched = run(ChoiceWorld(n=2), pol, ticks=2, queen=False)
    assert all("allowed" in e.data["meta"] for e in decided(sched, "w0"))


def test_queen_goal_is_put_in_the_move_question():
    backend = FakeBackend()
    decide(worker(backend), view([queen_signal(goal="explore east, the old patch is empty")]))
    assert backend.requests[-1].questions["move"].instructions == (
        "Which action? Your group's goal: explore east, the old patch is empty")
    decide(worker(backend, use_queen=False), view([queen_signal(goal="ignored")]))
    assert backend.requests[-1].questions["move"].instructions == "Which action?"
