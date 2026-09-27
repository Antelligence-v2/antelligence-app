import dataclasses

import pytest

from antelligence.kernel import events as ev
from antelligence.kernel import (
    GridField,
    Intent,
    LocalView,
    RunConfig,
    Scheduler,
    SignalDraft,
    derive_seed,
)
from tests.engine.toy_world import ForagerPolicy, SlowAsyncForager, ToyWorld


def run(seed=7, policy=None, policies=None, world=None, field=None, arm="default", max_ticks=60, **kw):
    world = world or ToyWorld()
    policies = policies if policies is not None else {a: policy or ForagerPolicy() for a in world.agents()}
    sched = Scheduler(world, policies, field or GridField(), RunConfig("run1", seed=seed, max_ticks=max_ticks, arm=arm), **kw)
    return sched, sched.run()


def test_same_seed_same_trace_different_seed_different_trace():
    _, a = run(seed=7)
    _, b = run(seed=7)
    _, c = run(seed=8)
    assert a.trace_hash == b.trace_hash and a.config_hash == b.config_hash
    assert a.trace_hash != c.trace_hash
    assert a.config_hash != c.config_hash


def test_async_policies_with_random_latency_do_not_change_the_trace():
    _, sync = run(seed=3)
    world = ToyWorld()
    slow = {a: SlowAsyncForager(jitter_seed=i) for i, a in enumerate(reversed(world.agents()))}
    for policy in slow.values():
        policy.describe = ForagerPolicy().describe  # same config identity
    _, asynchronous = run(seed=3, policies=slow, world=world)
    assert asynchronous.trace_hash == sync.trace_hash


def test_policy_mapping_order_does_not_matter():
    world = ToyWorld()
    forward = {a: ForagerPolicy() for a in world.agents()}
    backward = {a: ForagerPolicy() for a in reversed(world.agents())}
    _, a = run(policies=forward)
    _, b = run(policies=backward, world=ToyWorld())
    assert a.trace_hash == b.trace_hash


def test_run_stops_when_world_done_and_reports_metrics():
    _, result = run(max_ticks=500)
    assert result.stopped_reason == "world_done"
    assert result.metrics == {"collected": 2, "remaining": 0}
    assert result.ticks < 500


def test_signals_are_stamped_with_true_sender_and_scope():
    sched, _ = run(max_ticks=40)
    deposited = sched.log.of_type(ev.SIGNAL_DEPOSITED)
    assert deposited, "foragers announce visible food"
    for event in deposited:
        assert event.data["sender"] == event.agent_id
        assert event.data["scope"] == "run1:default"


class Probe:
    """Records views; emits one signal on tick 1 from agent a0 only."""

    def __init__(self):
        self.views = []

    def decide(self, view: LocalView) -> Intent:
        self.views.append(view)
        if view.agent_id == "a0" and view.tick == 1:
            return Intent("noop", emit=(SignalDraft(kind="found", pos=(0, 0), ttl=2),))
        return Intent("noop")

    def describe(self):
        return {"policy": "probe"}


def test_deferred_visibility_and_ttl_through_the_scheduler():
    probe = Probe()
    world = ToyWorld(agents=2, food=[(7, 7)])
    run(world=world, policy=probe, max_ticks=4)
    seen = {(v.tick, v.agent_id): len(v.signals) for v in probe.views}
    assert seen[(1, "a1")] == 0, "not visible in the emitting tick"
    assert seen[(2, "a1")] == 1 and seen[(3, "a1")] == 1
    assert seen[(4, "a1")] == 0, "expired after ttl=2"
    assert all(seen[(t, "a0")] == 0 for t in range(1, 5)), "own signals excluded"


def test_arms_sharing_a_field_are_isolated():
    field = GridField()
    probe_a, probe_b = Probe(), Probe()
    run(world=ToyWorld(agents=2, food=[(7, 7)]), policy=probe_a, field=field, arm="A", max_ticks=3)
    run(world=ToyWorld(agents=2, food=[(7, 7)]), policy=probe_b, field=field, arm="B", max_ticks=3)
    assert all(len(v.signals) == 0 for v in probe_b.views if v.agent_id == "a0")
    assert any(len(v.signals) == 1 for v in probe_b.views if v.agent_id == "a1")
    ids = {s.id for v in probe_b.views for s in v.signals}
    assert all(s.scope == "run1:B" for v in probe_b.views for s in v.signals) and ids


def test_local_view_exposes_no_world_or_field_handles():
    names = {f.name for f in dataclasses.fields(LocalView)}
    assert names == {"agent_id", "tick", "revision", "seed", "observation", "signals", "memory"}


class Exploding:
    def decide(self, view):
        raise RuntimeError("model unavailable")

    def describe(self):
        return {"policy": "exploding"}


class WrongType:
    def decide(self, view):
        return {"action": "move"}

    def describe(self):
        return {"policy": "wrong"}


@pytest.mark.parametrize("bad", [Exploding(), WrongType()])
def test_failing_policy_fails_closed_to_noop(bad):
    world = ToyWorld(agents=2)
    policies = {"a0": bad, "a1": ForagerPolicy()}
    sched, result = run(world=world, policies=policies, max_ticks=5)
    assert result.policy_failures == 5
    failures = sched.log.of_type(ev.POLICY_FAILED)
    assert {e.agent_id for e in failures} == {"a0"}
    assert world.position("a0") == (0, 0), "failed agent never moved"


class Spammer:
    def decide(self, view):
        drafts = tuple(SignalDraft(kind="found", pos=(0, i), ttl=1) for i in range(5))
        drafts += (SignalDraft(kind="found", pos=(0, 0), ttl=1),)  # duplicate of the first
        return Intent("noop", emit=drafts)

    def describe(self):
        return {"policy": "spam"}


def test_emit_budget_and_duplicates_are_rejected():
    world = ToyWorld(agents=1, food=[(7, 7)])
    sched, result = run(world=world, policy=Spammer(), max_ticks=1, )
    sched2 = Scheduler(ToyWorld(agents=1, food=[(7, 7)]), {"a0": Spammer()}, GridField(),
                       RunConfig("run1", max_ticks=1, max_emits_per_tick=3))
    sched2.run()
    reasons = [e.data["reason"] for e in sched2.log.of_type(ev.SIGNAL_REJECTED)]
    assert reasons == ["emit_budget_exceeded"] * 3
    reasons = [e.data["reason"] for e in sched.log.of_type(ev.SIGNAL_REJECTED)]
    assert reasons == ["duplicate"] and result.signals_deposited == 5


class RejectAlarms:
    def check(self, signal, tick):
        return "kind_not_allowed" if signal.kind == "alarm" else None


class Alarmist:
    def decide(self, view):
        return Intent("noop", emit=(SignalDraft(kind="alarm", pos=(0, 0)), SignalDraft(kind="found", pos=(1, 1))))

    def describe(self):
        return {"policy": "alarmist"}


def test_admission_hook_can_veto_signals():
    world = ToyWorld(agents=1, food=[(7, 7)])
    sched, result = run(world=world, policy=Alarmist(), max_ticks=1, admission=RejectAlarms())
    assert result.signals_deposited == 1 and result.signals_rejected == 1
    assert sched.log.of_type(ev.SIGNAL_REJECTED)[0].data["reason"] == "kind_not_allowed"


class StaticMemory:
    def __init__(self):
        self.calls = []

    def recall_for(self, agent_id, scope, tick, observation):
        self.calls.append((agent_id, scope, tick))
        return ()


def test_memory_hook_is_called_with_scope():
    memory = StaticMemory()
    run(world=ToyWorld(agents=1, food=[(7, 7)]), policy=Probe(), max_ticks=2, memory=memory)
    assert memory.calls == [("a0", "run1:default", 1), ("a0", "run1:default", 2)]


def test_signals_help_toy_foraging():
    ticks = {}
    for use in (True, False):
        total = 0
        for seed in range(10):
            world = ToyWorld(size=10, agents=4, food=[(9, 9), (9, 0), (0, 9), (5, 5)])
            _, result = run(seed=seed, world=world, policy=ForagerPolicy(use_signals=use), max_ticks=300)
            total += result.ticks
        ticks[use] = total
    assert ticks[True] <= ticks[False]


def test_derive_seed_is_stable_and_distinct():
    assert derive_seed(1, "a0", 1) == derive_seed(1, "a0", 1)
    assert len({derive_seed(1, a, t) for a in ("a0", "a1") for t in range(50)}) == 100


def test_run_config_validation():
    with pytest.raises(ValueError):
        RunConfig("bad:id")
    with pytest.raises(ValueError):
        RunConfig("ok", max_ticks=0)
    assert RunConfig("r", arm="x").scope == "r:x"


def test_event_log_can_be_persisted_and_verified(tmp_path):
    sched, result = run(max_ticks=10)
    path = tmp_path / "run.jsonl"
    sched.log.write_jsonl(path)
    assert ev.EventLog.read_jsonl(path).trace_hash == result.trace_hash
