import asyncio
import json

import pytest

from antelligence.kernel import GridField, Intent, LocalView, RunConfig, Scheduler, Signal
from antelligence.kernel import events as ev
from antelligence.kernel.memory import EvidenceMemory, EvidenceRecorder, ScopedRecall
from antelligence.kernel.policies import LLMPolicy, QueenEmitter, ReplyError
from antelligence.providers import Budgeted, Cached, FakeProvider
from tests.engine.toy_world import MOVES, ForagerPolicy, ToyWorld, food_subject

ACTIONS = {"move": "params.dir in n/s/e/w", "collect": "collect food here", "noop": "wait"}
KINDS = {"found": "food location"}


def view(memory=(), signals=(), tick=1, obs=None):
    return LocalView(agent_id="a0", tick=tick, revision=0, seed=99, observation=obs or {"pos": [0, 0], "food": []},
                     signals=tuple(signals), memory=tuple(memory))


def policy(responder, **kw):
    return LLMPolicy(FakeProvider(responder), "m1", actions=ACTIONS, signal_kinds=KINDS, **kw)


def decide(p, v=None):
    return asyncio.run(p.decide(v or view()))


def test_valid_reply_becomes_intent_with_provenance():
    reply = {"action": "move", "params": {"dir": "n"}, "emit": [{"kind": "found", "pos": [1, 2], "ttl": 3}],
             "rationale": "heading north"}
    intent = decide(policy(lambda r: json.dumps(reply)))
    assert intent.action == "move" and intent.params == {"dir": "n"} and intent.rationale == "heading north"
    assert intent.emit[0].pos == (1.0, 2.0) and intent.emit[0].ttl == 3
    assert intent.meta["model"] == "m1" and intent.meta["request_hash"] and intent.meta["prompt_tokens"] > 0


def test_fenced_json_is_accepted():
    assert decide(policy(lambda r: '```json\n{"action": "noop"}\n```')).action == "noop"


@pytest.mark.parametrize(
    "content, error",
    [
        ("not json", "not JSON"),
        ("[1]", "object"),
        ('{"action": "fly"}', "not allowed"),
        ('{"action": "noop", "extra": 1}', "unknown fields"),
        ('{"action": "noop", "params": []}', "params"),
        ('{"action": "noop", "emit": [{"kind": "found", "pos": [0,0]}, {"kind": "found", "pos": [1,1]}, '
         '{"kind": "found", "pos": [2,2]}]}', "at most"),
        ('{"action": "noop", "emit": [{"kind": "alarm", "pos": [0,0]}]}', "kind"),
        ('{"action": "noop", "emit": [{"kind": "found", "pos": [0,0], "ttl": 99}]}', "ttl"),
        ('{"action": "noop", "emit": [{"kind": "found"}]}', "bad signal"),
        ('{"action": "noop", "cites": ["made-up"]}', "not in view"),
    ],
)
def test_invalid_replies_are_refused_without_fallback(content, error):
    with pytest.raises(ReplyError, match=error):
        decide(policy(lambda r: content))


def test_cites_must_come_from_the_view():
    memory = EvidenceMemory()
    record = memory.propose(scope="r:a", kind="claim", author="a1", subject="food:1,1", body={"kind": "found"}, tick=1)
    intent = decide(policy(lambda r: json.dumps({"action": "collect", "cites": [record.id]})), view(memory=[record]))
    assert intent.cites == (record.id,)


def test_fallback_is_used_and_recorded_on_bad_reply():
    p = policy(lambda r: "garbage", fallback=ForagerPolicy())
    intent = decide(p, view(obs={"pos": [0, 0], "food": [[0, 0]]}))
    assert intent.action == "collect"
    assert intent.meta["fallback"].startswith("reply:") and intent.meta["request_hash"]


def test_fallback_on_provider_error_via_budget():
    p = LLMPolicy(Budgeted(FakeProvider(lambda r: '{"action":"noop"}'), max_calls=0), "m1", actions=ACTIONS,
                  fallback=ForagerPolicy())
    intent = decide(p)
    assert intent.meta["fallback"] == "provider:BudgetExceeded" and intent.action == "move"


def test_prompt_contains_only_the_local_view():
    fake = FakeProvider(lambda r: '{"action":"noop"}')
    p = LLMPolicy(fake, "m1", actions=ACTIONS, signal_kinds=KINDS)
    signal = Signal(sender="a1", scope="r:a", kind="found", emitted_at=0, revision=0, ttl=3, pos=(3, 3))
    asyncio.run(p.decide(view(signals=[signal])))
    payload = json.loads(fake.requests[0].messages[1]["content"])
    assert set(payload["view"]) == {"agent", "tick", "observation", "signals", "evidence"}
    assert payload["view"]["signals"][0]["pos"] == [3.0, 3.0] and payload["view"]["signals"][0]["age"] == 1
    assert fake.requests[0].seed == 99 and fake.requests[0].response_format == {"type": "json_object"}


def forager_responder(request):
    """Plays the same rules as ForagerPolicy, from the prompt alone."""
    data = json.loads(request.messages[1]["content"])["view"]
    rule = ForagerPolicy().decide(LocalView(
        agent_id=data["agent"], tick=data["tick"], revision=0,
        seed=request.seed, observation=data["observation"],
        signals=tuple(Signal(sender=s["from"], scope="x:y", kind=s["kind"], emitted_at=0, revision=0, ttl=1,
                             pos=tuple(s["pos"])) for s in data["signals"]),
    ))
    emit = [{"kind": d.kind, "pos": list(d.pos), "ttl": d.ttl} for d in rule.emit]
    return json.dumps({"action": rule.action, "params": rule.params, "emit": emit})


def llm_run(provider, seed=4):
    world = ToyWorld(agents=3)
    llm = LLMPolicy(provider, "m1", actions=ACTIONS, signal_kinds=KINDS, max_ttl=5)
    sched = Scheduler(world, {}, GridField(), RunConfig("r", seed=seed, max_ticks=400), default_policy=llm)
    return sched, sched.run()


def test_llm_swarm_is_deterministic_and_replayable_from_cache(tmp_path):
    path = tmp_path / "llm.jsonl"
    live = Budgeted(Cached(FakeProvider(forager_responder), path))
    sched, first = llm_run(live)
    assert first.stopped_reason == "world_done" and first.policy_failures == 0
    assert live.usage.calls > 0 and live.usage.cached_calls < live.usage.calls
    decided = sched.log.of_type(ev.DECIDED)
    assert all(e.data["meta"]["request_hash"] for e in decided)

    def never(r):
        raise AssertionError("replay must not call the model")

    replay = Cached(FakeProvider(never), path, offline=True)
    _, second = llm_run(replay)
    assert second.trace_hash == first.trace_hash, "cached replay reproduces the exact event log"


def test_budget_exhaustion_mid_run_degrades_to_logged_fallback():
    budget = Budgeted(FakeProvider(forager_responder), max_calls=6)
    world = ToyWorld(agents=3)
    llm = LLMPolicy(budget, "m1", actions=ACTIONS, signal_kinds=KINDS, max_ttl=5, fallback=ForagerPolicy())
    sched = Scheduler(world, {}, GridField(), RunConfig("r", seed=1, max_ticks=30), default_policy=llm)
    result = sched.run()
    fallbacks = [e for e in sched.log.of_type(ev.DECIDED) if e.data["meta"].get("fallback")]
    assert budget.usage.calls == 6 and fallbacks and result.policy_failures == 0


def test_llm_without_fallback_fails_closed_through_the_scheduler():
    world = ToyWorld(agents=1)
    llm = LLMPolicy(FakeProvider(lambda r: "nonsense"), "m1", actions=ACTIONS)
    sched = Scheduler(world, {}, GridField(), RunConfig("r", max_ticks=3), default_policy=llm)
    result = sched.run()
    assert result.policy_failures == 3 and world.position("a0") == (0, 0)


# ------------------------------------------------------------------ queen

def found(sender, pos):
    return Signal(sender=sender, scope="r:a", kind="found", emitted_at=0, revision=0, ttl=5, pos=pos)


def test_queen_recruits_to_the_region_most_reporters_agree_on():
    queen = QueenEmitter(cell_size=10, min_reports=2, every=5)
    signals = [found("a1", (11, 11)), found("a2", (13, 12)), found("a3", (90, 90)), found("a1", (12, 14))]
    intent = queen.decide(view(signals=signals, tick=5))
    [draft] = intent.emit
    assert draft.kind == "recruit" and draft.payload == {"reports": 3, "reporters": 2}
    assert draft.pos == (12.0, 12.333)


def test_queen_is_quiet_off_cycle_and_without_consensus():
    queen = QueenEmitter(cell_size=10, min_reports=2, every=5)
    assert queen.decide(view(signals=[found("a1", (1, 1)), found("a2", (2, 2))], tick=4)).emit == ()
    assert queen.decide(view(signals=[found("a1", (1, 1)), found("a1", (2, 2))], tick=5)).emit == ()


def test_queen_cites_memory_it_relied_on():
    memory = EvidenceMemory()
    records = [memory.propose(scope="r:a", kind="claim", author=a, subject=f"food:{x},1",
                              body={"kind": "found", "pos": [x, 1]}, tick=1) for a, x in (("a1", 1), ("a2", 2))]
    intent = QueenEmitter(cell_size=10, every=1).decide(view(memory=records, tick=1))
    assert set(intent.emit[0].cites) == {r.id for r in records}


def test_queen_in_a_live_run_emits_recruits_admissible_by_citation():
    memory = EvidenceMemory()
    world = ToyWorld(size=6, agents=4, food=[(3, 3), (4, 3), (3, 4)], hearing=20)
    policies = {"a0": QueenEmitter(cell_size=5, min_reports=1, every=2)}
    from antelligence.kernel.admission import AdmissionPolicy
    sched = Scheduler(world, policies, GridField(), RunConfig("r", seed=2, max_ticks=200),
                      default_policy=ForagerPolicy(), memory=ScopedRecall(memory),
                      recorder=EvidenceRecorder(memory, {"found": lambda s: food_subject(s.pos)}),
                      admission=AdmissionPolicy(cite_resolver=memory.is_usable))
    sched.run()
    recruits = [e for e in sched.log.of_type(ev.SIGNAL_DEPOSITED) if e.data["kind"] == "recruit"]
    assert recruits and all(e.agent_id == "a0" for e in recruits)
