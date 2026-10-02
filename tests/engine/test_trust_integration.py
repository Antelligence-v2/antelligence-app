"""End-to-end trust layer: signals -> memory -> gate -> verdict."""

from antelligence.kernel import GridField, Intent, RunConfig, Scheduler, SignalDraft
from antelligence.kernel import events as ev
from antelligence.kernel import memory as m
from antelligence.kernel.admission import AdmissionPolicy
from antelligence.kernel.memory import EvidenceMemory, EvidenceRecorder, ScopedRecall
from antelligence.kernel.verifier import (
    ATTEMPTED_UNSAFE,
    SAFE_INCOMPLETE,
    STATE_VIOLATION,
    SUCCESS,
    EvidenceGate,
    classify_episode,
)
from tests.engine.toy_world import RememberingForager, ToyWorld, food_subject


def trust_stack(min_confirmations=1):
    memory = EvidenceMemory(min_confirmations=min_confirmations)
    return dict(
        memory=ScopedRecall(memory),
        recorder=EvidenceRecorder(memory, {"found": lambda s: food_subject(s.pos)}),
        admission=AdmissionPolicy(kinds={"found": None}, max_ttl=10, cite_resolver=memory.is_usable),
    ), memory


class Script:
    """a0 announces food under itself, then eats it. a1 caches the claim and acts on it late."""

    def __init__(self):
        self.remembered = None

    def decide(self, view):
        if view.agent_id == "a0":
            if view.tick == 1:
                return Intent("noop", emit=(SignalDraft(kind="found", pos=(0, 0), ttl=5),))
            if view.tick == 2:
                return Intent("collect")
            return Intent("noop")
        if view.tick == 2:
            self.remembered = view.memory[0].id
            return Intent("move", {"dir": "s"})
        if view.tick == 3:
            return Intent("collect", cites=(self.remembered,), params={"accepted": True, "done": True})
        return Intent("noop")

    def describe(self):
        return {"policy": "script"}


def run_script(gated, hazardous=True):
    stack, memory = trust_stack()
    world = ToyWorld(agents=2, food=[(0, 0), (7, 7)], hazardous_misfire=hazardous)
    gate = EvidenceGate(memory.is_usable, require_citations_for=()) if gated else None
    script = Script()
    sched = Scheduler(world, {}, GridField(), RunConfig("r", max_ticks=4), default_policy=script, gate=gate, **stack)
    result = sched.run()
    return sched, result, memory, script


def test_stale_cited_action_is_blocked_before_it_reaches_the_world():
    sched, result, memory, script = run_script(gated=True)
    record = memory.get(script.remembered)
    assert record.status == m.INVALIDATED and record.reason == "source_replaced"
    [blocked] = sched.log.of_type(ev.INTENT_BLOCKED)
    assert blocked.agent_id == "a1" and blocked.tick == 3 and blocked.data["reason"] == "stale_evidence"
    assert result.extra["intents_blocked"] == 1
    verdict = classify_episode(sched.log, goal_reached=False)
    assert verdict.verdict == ATTEMPTED_UNSAFE and verdict.unsafe_applied == 0


def test_without_the_gate_the_same_stale_action_causes_a_state_violation():
    sched, result, _, _ = run_script(gated=False)
    verdict = classify_episode(sched.log, goal_reached=False)
    assert verdict.verdict == STATE_VIOLATION and verdict.unsafe_applied == 1


def test_agent_self_claims_do_not_change_the_outcome():
    sched, _, _, _ = run_script(gated=False, hazardous=False)
    outcome = [e for e in sched.log.of_type(ev.OUTCOME) if e.agent_id == "a1" and e.tick == 3][0]
    assert outcome.data["accepted"] is False and outcome.data["reason"] == "no_food_here"
    assert classify_episode(sched.log, goal_reached=False).verdict == SAFE_INCOMPLETE


def test_memory_transitions_are_in_the_event_log():
    sched, _, _, _ = run_script(gated=True)
    changes = [(e.tick, e.data["from"], e.data["to"]) for e in sched.log.of_type(ev.MEMORY_CHANGED)]
    assert (1, None, m.CANDIDATE) in changes and (1, m.CANDIDATE, m.ADMITTED) in changes
    assert (2, m.ADMITTED, m.INVALIDATED) in changes


def test_uncited_actions_can_be_required_to_cite():
    stack, memory = trust_stack()
    world = ToyWorld(agents=1, food=[(0, 0)])
    gate = EvidenceGate(memory.is_usable, require_citations_for={"collect"})

    class Collector:
        def decide(self, view):
            return Intent("collect")

        def describe(self):
            return {}

    sched = Scheduler(world, {"a0": Collector()}, GridField(), RunConfig("r", max_ticks=2), gate=gate, **stack)
    sched.run()
    assert {e.data["reason"] for e in sched.log.of_type(ev.INTENT_BLOCKED)} == {"uncited_action"}
    assert world.collected == 0


def test_gate_world_check_hook():
    gate = EvidenceGate(lambda rid: True, world_check=lambda agent, intent, tick: "forbidden" if intent.action == "x" else None)
    assert gate.check("a", Intent("x"), 1) == "forbidden"
    assert gate.check("a", Intent("y"), 1) is None


def test_cross_seed_gate_eliminates_unsafe_acts_from_private_stale_caches():
    unsafe = {True: 0, False: 0}
    blocked = {True: 0, False: 0}
    for gated in (True, False):
        for seed in range(8):
            stack, memory = trust_stack()
            world = ToyWorld(size=6, agents=4, food=[(5, 5), (5, 0), (0, 5), (3, 3)], hazardous_misfire=True)
            gate = EvidenceGate(memory.is_usable) if gated else None
            sched = Scheduler(world, {}, GridField(), RunConfig("r", seed=seed, max_ticks=80),
                              default_policy=RememberingForager(private_cache=True), gate=gate, **stack)
            sched.run()
            verdict = classify_episode(sched.log, goal_reached=world.done(0))
            unsafe[gated] += verdict.unsafe_applied
            blocked[gated] += verdict.blocked_attempts
    assert unsafe[True] == 0 and blocked[True] > 0
    assert unsafe[False] > 0


def test_success_verdict_for_clean_completion():
    stack, memory = trust_stack()
    world = ToyWorld(agents=3)
    sched = Scheduler(world, {}, GridField(), RunConfig("r", seed=1, max_ticks=300),
                      default_policy=RememberingForager(), gate=EvidenceGate(memory.is_usable), **stack)
    result = sched.run()
    assert result.stopped_reason == "world_done"
    assert classify_episode(sched.log, goal_reached=True).verdict == SUCCESS


def test_trust_components_change_the_config_hash():
    stack, memory = trust_stack()
    plain = Scheduler(ToyWorld(), {}, GridField(), RunConfig("r"), default_policy=RememberingForager())
    trusted = Scheduler(ToyWorld(), {}, GridField(), RunConfig("r"), default_policy=RememberingForager(),
                        gate=EvidenceGate(memory.is_usable), **stack)
    assert plain.config_hash() != trusted.config_hash()
