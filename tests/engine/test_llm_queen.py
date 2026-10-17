import asyncio
import json

import pytest

from antelligence.kernel.decision import REPORT
from antelligence.kernel.policies import DecisionWorker, LLMQueen, framework_policies
from antelligence.kernel.signal import Signal
from antelligence.kernel.types import LocalView
from antelligence.providers.wrappers import FakeProvider
from tests.engine.hive_helpers import ACTIONS, ChoiceSensor, ChoiceWorld, FakeBackend, run


def reply(**groups):
    return json.dumps({"groups": groups})


def queen(responder, every=1, groups=None):
    provider = FakeProvider(responder)
    groups = groups or {"g1": ("w0", "w1"), "g2": ("w2", "w3")}
    return LLMQueen(provider, "q-model", groups=groups, actions=ACTIONS, every=every), provider


def qview(tick, signals=(), counts=None):
    return LocalView("queen", tick, 0, 7, {"tick": tick, "counts": counts or {"hits": 0}}, tuple(signals))


def go(q, v):
    return asyncio.run(q.decide(v))


def report(i, group="g1", reason="food is gone", tick=1):
    return Signal(sender=f"w{i}", scope="s", kind="report", emitted_at=tick, revision=0, ttl=10, topic="board",
                  payload={"group": group, "tick": tick, "reason": reason, "failed": []})


GOOD = reply(g1={"goal": "north", "allowed": ["a", "zzz"]}, g2={"goal": "x" * 300, "allowed": ["b", "c"]})


def test_emits_one_queen_signal_per_group_with_validation():
    q, _ = queen(lambda r: GOOD)
    intent = go(q, qview(1))
    got = {d.payload["group"]: d for d in intent.emit}
    assert set(got) == {"g1",
        "g2"} and all(d.kind == "queen" and d.topic == "board" and d.ttl == 1 for d in got.values())
    assert got["g1"].payload["allowed"] == ["a"]  # unknown action dropped
    assert len(got["g2"].payload["goal"]) == 120  # truncated
    assert intent.meta["spoke"] is True and "request_hash" in intent.meta


def test_prompt_contains_only_board_information():
    q, provider = queen(lambda r: GOOD)
    go(q, qview(1, [report(0, reason="food gone north")], counts={"hits": 3}))
    body = json.loads(provider.requests[0].messages[1]["content"])
    assert set(body) == {"tick", "counts", "groups", "actions", "reports", "your_previous_orders"}
    assert body["counts"] == {"hits": 3} and body["reports"] == [{"from": "w0", "group": "g1",
        "reason": "food gone north"}]
    assert provider.requests[0].temperature == 0 and provider.requests[0].max_tokens == 300


def test_reports_shown_once_then_cleared_and_past_signals_kept():
    q, provider = queen(lambda r: GOOD)
    sig = report(0)
    go(q, qview(1, [sig]))
    go(q, qview(2, [sig]))  # same signal still live: not repeated
    body2 = json.loads(provider.requests[1].messages[1]["content"])
    assert body2["reports"] == [] and body2["your_previous_orders"]["g1"]["allowed"] == ["a"]


def test_cadence_every_10_speaks_on_ticks_1_11_21():
    q, provider = queen(lambda r: GOOD, every=10)
    spoke = [t for t in range(1, 25) if go(q, qview(t)).meta["spoke"]]
    assert spoke == [1, 11, 21] and len(provider.requests) == 3
    assert go(q, qview(12)).emit == ()


def test_reports_between_turns_accumulate():
    q, provider = queen(lambda r: GOOD, every=10)
    go(q, qview(1))
    go(q, qview(4, [report(0, tick=3)]))
    go(q, qview(7, [report(0, tick=3), report(1, tick=6)]))
    go(q, qview(11))
    body = json.loads(provider.requests[1].messages[1]["content"])
    assert len(body["reports"]) == 2


@pytest.mark.parametrize("bad", ["not json", "[]", '{"groups": 3}', reply(g1={"goal": "x", "allowed": []}),
                                 reply(nope={"goal": "x", "allowed": ["a"]}), "{}"])
def test_invalid_reply_keeps_previous(bad):
    replies = iter([GOOD, bad])
    q, _ = queen(lambda r: next(replies))
    first = go(q, qview(1))
    second = go(q, qview(2))
    assert [d.payload for d in second.emit] == [d.payload for d in first.emit]
    assert "kept_previous" in second.meta


def test_invalid_first_reply_emits_nothing():
    q, _ = queen(lambda r: "garbage")
    intent = go(q, qview(1))
    assert intent.emit == () and "kept_previous" in intent.meta


def test_partial_reply_keeps_other_group():
    replies = iter([GOOD, reply(g1={"goal": "south", "allowed": ["b"]})])
    q, _ = queen(lambda r: next(replies))
    go(q, qview(1))
    out = {d.payload["group"]: d.payload for d in go(q, qview(2)).emit}
    assert out["g1"]["allowed"] == ["b"] and out["g2"]["allowed"] == ["b", "c"]


def test_provider_exception_keeps_previous():
    state = {"n": 0}

    def responder(r):
        state["n"] += 1
        if state["n"] > 1:
            raise RuntimeError("down")
        return GOOD

    q, _ = queen(responder)
    go(q, qview(1))
    out = go(q, qview(2))
    assert len(out.emit) == 2 and "RuntimeError" in out.meta["kept_previous"]


def test_fenced_json_accepted():
    q, _ = queen(lambda r: "```json\n" + GOOD + "\n```")
    assert len(go(q, qview(1)).emit) == 2


def test_constructor_validation():
    with pytest.raises(ValueError):
        LLMQueen(FakeProvider(lambda r: ""), "m", groups={"g": ("w0",)}, actions=ACTIONS, every=0)


# --- end to end through the scheduler -----------------------------------------


def hive_policies(backend, qpolicy, use_queen=True):
    world = ChoiceWorld(n=4)
    groups = {"g1": ("w0", "w1"), "g2": ("w2", "w3")}
    agents = world.agents() + (["queen"] if use_queen else [])
    return framework_policies(agents, groups, backend, ChoiceSensor(), "m", use_queen=use_queen, queen=qpolicy)


def test_end_to_end_group_scoping_and_one_tick_delay():
    q, _ = queen(lambda r: reply(g1={"goal": "g", "allowed": ["a"]}, g2={"goal": "g", "allowed": ["b", "c"]}),
        every=100)
    sched = run(ChoiceWorld(n=4), hive_policies(FakeBackend(), q), ticks=3)
    acts = sched.world.inner.acts
    assert set(acts["w0"][1:] + acts["w1"][1:]) <= {"a", "noop"}  # g1 restricted from tick 2
    assert set(acts["w2"][1:] + acts["w3"][1:]) <= {"b", "c", "noop"}
    deposited = [e for e in sched.log.of_type("signal_deposited") if e.data["kind"] == "queen"]
    assert {e.tick for e in deposited} == {1}
    # tick 1 workers had no queen signal yet: all actions offered
    assert set(sched.world.inner.acts["w0"][:1]) <= {"a", "b", "c", "noop"}


def test_end_to_end_queen_receives_reports_next_tick():
    q, provider = queen(lambda r: reply(g1={"goal": "g", "allowed": ["a"]}), every=1, groups={"g1": ("w0", "w1",
        "w2", "w3")})
    backend = FakeBackend(p_yes=0.1)  # every check fails -> every worker reports each tick
    run(ChoiceWorld(n=4), hive_policies(backend, q), ticks=3)
    bodies = [json.loads(r.messages[1]["content"]) for r in provider.requests]
    assert bodies[0]["reports"] == []  # nothing before tick 1 ends
    assert {r["from"] for r in bodies[1]["reports"]} == {"w0", "w1", "w2", "w3"}


def test_workers_do_not_see_reports_and_queen_does_not_see_own_signals():
    q, provider = queen(lambda r: reply(g1={"goal": "g", "allowed": ["a"]}), groups={"g1": ("w0", "w1", "w2", "w3")})
    sched = run(ChoiceWorld(n=4), hive_policies(FakeBackend(p_yes=0.1), q), ticks=3)
    for e in sched.log.of_type("observed"):
        ids = set(e.data["signal_ids"])
        kinds = {s.data["kind"] for s in sched.log.of_type("signal_deposited") if s.data["id"] in ids}
        assert kinds <= ({"report"} if e.agent_id == "queen" else {"queen"})


def test_no_queen_ablation():
    backend = FakeBackend(chooser=lambda req: "c")
    pol = hive_policies(backend, None, use_queen=False)
    assert "queen" not in pol and all(isinstance(p, DecisionWorker) and not p.use_queen for p in pol.values())
    sched = run(ChoiceWorld(n=4), pol, ticks=3, queen=False)
    assert not [e for e in sched.log.of_type("signal_deposited") if e.data["kind"] == "queen"]
    assert all(set(r.questions["move"].options) == set(ACTIONS) | {REPORT} for r in backend.requests)


def test_end_to_end_determinism():
    def once():
        q, _ = queen(lambda r: GOOD)
        return run(ChoiceWorld(n=4), hive_policies(FakeBackend(p_yes=0.3), q), seed=103, ticks=5).log.trace_hash

    assert once() == once()


def test_framework_policies_validation_and_noesc_is_backend_only():
    groups = {"g": ("w0", "w1")}
    with pytest.raises(ValueError):
        framework_policies(["w0", "w1", "w2"], groups, FakeBackend(), ChoiceSensor(), "m", use_queen=False)
    with pytest.raises(ValueError):
        framework_policies(["w0", "w1"], groups, FakeBackend(), ChoiceSensor(), "m", use_queen=True)
    with pytest.raises(ValueError):
        framework_policies(["w0"], {"a": ("w0",), "b": ("w0",)}, FakeBackend(), ChoiceSensor(), "m", use_queen=False)
    no_esc = framework_policies(["w0", "w1"], groups, FakeBackend(), ChoiceSensor(), "m", use_queen=False)
    esc = framework_policies(["w0", "w1"], groups, FakeBackend(escalated=("move",)), ChoiceSensor(), "m",
        use_queen=False)
    assert asyncio.run(no_esc["w0"].decide(qview(1))).meta["escalated"] == []
    assert asyncio.run(esc["w0"].decide(qview(1))).meta["escalated"] == ["move"]


def test_task_instructions_reach_the_queen_prompt_and_framework_workers():
    provider = FakeProvider(lambda r: GOOD)
    q = LLMQueen(provider, "q", groups={"g1": ("w0",)}, actions=ACTIONS, every=1, instructions="Task: score points.")
    go(q, qview(1))
    assert "Task: score points." in provider.requests[0].messages[0]["content"]
    plain, plain_provider = queen(lambda r: GOOD)
    go(plain, qview(1))
    assert plain_provider.requests[0].messages[0]["content"].endswith("}")
    pols = framework_policies(["w0", "queen"], {"g1": ("w0",)}, FakeBackend(), ChoiceSensor(), "m", use_queen=True,
                              queen=q, instructions="Task: score points.")
    assert pols["w0"].instructions == "Task: score points."
