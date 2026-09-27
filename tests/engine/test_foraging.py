import asyncio
import json
from pathlib import Path

import pytest

from antelligence.kernel import Intent
from antelligence.kernel import events as ev
from antelligence.kernel.policies import LLMPolicy
from antelligence.kernel.verifier import SUCCESS, classify_episode
from antelligence.providers import Budgeted, FakeProvider
from antelligence.worlds.foraging import (
    ARMS,
    LLM_ACTIONS,
    LLM_SIGNAL_KINDS,
    SEEDS,
    ChainForager,
    ChainForagingWorld,
    build,
    env_for,
    oracle_check,
)
from antelligence.worlds.foraging.fixtures import sweep_path

ORACLE = Path(__file__).resolve().parents[2] / "docs/research/desci-paper-20260915/e13-chain/oracle.json"


def test_fixture_and_oracle_parity_with_published_e13():
    published = {r["seed"]: r["steps_to_success"] for r in json.loads(ORACLE.read_text())["results"]}
    assert {seed: oracle_check(seed)[1] for seed in SEEDS} == published


def test_fixture_constraints():
    for seed in SEEDS:
        starts, nest, foods, index = env_for(seed)
        assert len(set(foods)) == 3 and nest not in foods
        assert all(max(abs(f[0] - s[0]), abs(f[1] - s[1])) > 2 for f in foods for s in starts)
        assert sorted(index.values()) == [0, 1, 2]


def test_sweep_path_covers_grid_once():
    path = sweep_path((3, 7))
    assert len(path) == 100 and len(set(path)) == 100 and path[0][1] == 7


def place(world, agent, pos):
    world.positions[agent] = pos


def test_pickup_replaces_the_food_source_and_chain_order_is_enforced():
    world = ChainForagingWorld(101)
    f0, f1 = world.foods[0], world.foods[1]
    # Agent 0 already carries food 1 and stands on the nest: food 0 must go first.
    world.remaining.remove(f1)
    world.carrying["0"].add(f1)
    place(world, "0", world.nest)
    assert world.apply("0", Intent("noop"), 1).accepted
    world._pick_and_drop("0", world.nest, 1)
    assert world.delivered == 0 and world.carrying["0"] == {f1}
    # Agent 1 steps onto food 0: auto-pick, and the food:0 source is replaced.
    near = (f0[0] - 1, f0[1]) if f0[0] > 0 else (f0[0] + 1, f0[1])
    place(world, "1", near)
    outcome = world.apply("1", Intent("follow", {"target": list(f0)}), 2)
    assert world.positions["1"] == f0 and outcome.effects["subjects_changed"] == ["food:0"]
    # Delivering food 0 unlocks food 1.
    world._pick_and_drop("1", world.nest, 3)
    world._pick_and_drop("0", world.nest, 3)
    assert world.delivered == 2 and world.next_needed == 2


@pytest.mark.parametrize("target", [None, [1], [10, 0], ["a", 1], [1.5, 2]])
def test_bad_follow_targets_are_rejected(target):
    world = ChainForagingWorld(101)
    outcome = world.apply("0", Intent("follow", {"target": target}), 1)
    assert not outcome.accepted and outcome.reason == "bad_target"
    assert not world.apply("0", Intent("teleport"), 1).accepted


def test_observation_is_local():
    world = ChainForagingWorld(101)
    obs = world.observe("0", 1).data
    pos = obs["pos"]
    assert all(abs(f[0] - pos[0]) <= 2 and abs(f[1] - pos[1]) <= 2 for f in obs["visible_foods"])
    assert "foods" not in obs and "remaining" not in obs


def run_arm(arm):
    results, logs = {}, {}
    for seed in SEEDS:
        sched = build(arm, seed)
        results[seed] = sched.run()
        logs[seed] = sched.log
    return results, logs


# Golden values for the rule policies (deterministic). A change here means the
# world or kernel semantics changed and results must be re-reviewed.
GOLDEN_SWEEP = {"baseline": 2506, "hive_memory": 1705, "signals": 2279, "hive_memory_signals": 1701}


@pytest.mark.parametrize("arm", ARMS)
def test_arm_golden_results_and_verdicts(arm):
    results, logs = run_arm(arm)
    assert sum(r.metrics["sweep_moves"] for r in results.values()) == GOLDEN_SWEEP[arm]
    assert all(r.metrics["success"] for r in results.values())
    for seed, log in logs.items():
        verdict = classify_episode(log, goal_reached=True)
        assert verdict.verdict == SUCCESS and verdict.unsafe_applied == 0 and verdict.blocked_attempts == 0


def test_hive_memory_beats_baseline_seed_by_seed():
    base, _ = run_arm("baseline")
    hive, _ = run_arm("hive_memory")
    wins = sum(hive[s].metrics["sweep_moves"] < base[s].metrics["sweep_moves"] for s in SEEDS)
    losses = sum(hive[s].metrics["sweep_moves"] > base[s].metrics["sweep_moves"] for s in SEEDS)
    assert (wins, losses) == (17, 2)


def test_memory_arm_cites_evidence_and_records_races():
    sched = build("hive_memory", 101)
    sched.run()
    cited = [e for e in sched.log.of_type(ev.DECIDED) if e.data["cites"]]
    assert cited and all(e.data["action"] == "follow" for e in cited)
    reasons = {e.data["reason"] for e in sched.log.of_type(ev.INTENT_BLOCKED)}
    assert reasons <= {"evidence_changed_this_tick"}


def test_arms_are_deterministic_and_distinct():
    assert build("baseline", 101).run().trace_hash == build("baseline", 101).run().trace_hash
    hashes = {arm: build(arm, 101).config_hash() for arm in ARMS}
    assert len(set(hashes.values())) == len(ARMS)


def test_unknown_arm():
    with pytest.raises(ValueError):
        build("nope", 101)


def rule_responder(request):
    """LLM stand-in: returns what ChainForager would decide from the prompt."""
    from antelligence.kernel import LocalView
    view = json.loads(request.messages[1]["content"])["view"]
    intent = ChainForager().decide(LocalView(agent_id=view["agent"], tick=view["tick"], revision=0, seed=0,
                                             observation=view["observation"]))
    return json.dumps({"action": intent.action, "params": intent.params})


def test_llm_policy_drives_the_foraging_world():
    budget = Budgeted(FakeProvider(rule_responder))
    policy = LLMPolicy(budget, "stand-in", actions=LLM_ACTIONS, signal_kinds=LLM_SIGNAL_KINDS)
    llm = build("baseline", 101, policy_factory=lambda arm: policy).run()
    rule = build("baseline", 101).run()
    assert llm.metrics == rule.metrics and llm.policy_failures == 0
    assert budget.usage.calls == 3 * llm.ticks
