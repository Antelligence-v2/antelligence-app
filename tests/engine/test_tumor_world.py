import asyncio
import contextlib
import io
import json
import math
import random

import numpy as np
import pytest

from antelligence.kernel import Intent, LocalView
from antelligence.kernel import events as ev
from antelligence.kernel import memory as m
from antelligence.kernel.policies import LLMPolicy
from antelligence.providers import FakeProvider
from antelligence.worlds.tumor import ARMS, LLM_ACTIONS, LLM_SIGNAL_KINDS, QUEEN, NanobotPolicy, TumorWorld, build


@pytest.mark.parametrize("seed, steps", [(1, 30), (2, 30), (7, 60)])
def test_legacy_compat_mode_reproduces_the_legacy_simulator_exactly(seed, steps):
    from backend.config import SimulationConfig
    from backend.runtime_factory import run_simulation

    with contextlib.redirect_stdout(io.StringIO()):
        _, legacy = run_simulation(SimulationConfig(num_bots=10, grid_size=60, steps=steps, seed=seed))
    engine = build("rule", seed, max_steps=steps, legacy_payload_deadlock=True, tumor_radius=198.0).run().metrics
    assert engine["kill_rate"] == pytest.approx(legacy["kill_rate"])
    assert engine["total_cells"] == legacy["total_cells"]
    assert engine["apoptotic_cells"] == legacy["cells_killed"]
    assert engine["deliveries"] == legacy["total_deliveries"]


def test_payload_deadlock_fix_lets_bots_reload_and_keep_treating():
    legacy_like = build("rule", 1, max_steps=150, legacy_payload_deadlock=True).run().metrics
    fixed = build("rule", 1, max_steps=150).run().metrics
    assert legacy_like["deliveries"] == 60, "legacy: exactly one payload (6 deliveries) per bot"
    assert fixed["deliveries"] > 60 and fixed["apoptotic_cells"] > legacy_like["apoptotic_cells"]


def test_observation_is_local_and_bounded():
    world = TumorWorld(1)
    obs = world.observe("bot-000", 1).data
    x, y = obs["pos"]
    assert obs["cells"], "bots start near the tumor edge and sense some cells"
    assert all(math.hypot(c["pos"][0] - x, c["pos"][1] - y) <= world.sense_radius + 1e-6 for c in obs["cells"])
    assert len(obs["cells"]) <= 24
    assert not {"tumor_cells", "all_cells", "bodies"} & set(obs)


def test_target_validation():
    world = TumorWorld(1)
    obs = world.observe("bot-000", 1).data
    near = obs["cells"][0]["id"]
    far = next(c.cell_id for c in world.physics.living_cells()
               if math.dist(c.position[:2], world.bodies["bot-000"].position) > world.sense_radius)
    assert world.apply("bot-000", Intent("target", {"cell_id": far}), 1).reason == "cell_not_sensed"
    assert world.apply("bot-000", Intent("target", {"cell_id": "x"}), 1).reason == "bad_cell_id"
    assert world.apply("bot-000", Intent("target", {"cell_id": 99999}), 1).reason == "no_such_living_cell"
    assert world.apply("bot-000", Intent("target", {"cell_id": near}), 1).accepted
    assert world.apply("bot-000", Intent("target", {"cell_id": near}), 1).reason == "busy"
    assert world.apply("bot-000", Intent("move", {"direction": [1, 0]}), 1).reason == "busy"


def test_duplicate_targeting_is_counted():
    world = TumorWorld(1)
    near = world.observe("bot-000", 1).data["cells"][0]
    world.bodies["bot-001"].position = world.bodies["bot-000"].position.copy()
    world.apply("bot-000", Intent("target", {"cell_id": near["id"]}), 1)
    world.apply("bot-001", Intent("target", {"cell_id": near["id"]}), 1)
    assert world.metrics()["duplicate_targets"] == 1


@pytest.mark.parametrize("direction", [None, [1], [0, 0], [True, 1], ["n", "e"]])
def test_bad_moves_are_rejected(direction):
    world = TumorWorld(1)
    assert not world.apply("bot-000", Intent("move", {"direction": direction}), 1).accepted


def test_non_finite_moves_cannot_even_be_expressed():
    with pytest.raises(ValueError):
        Intent("move", {"direction": [float("nan"), 1]})


def test_queen_is_bodiless_and_cannot_act():
    world = TumorWorld(1, queen=True)
    assert world.agents()[-1] == QUEEN
    assert world.observe(QUEEN, 1).data == {"role": QUEEN}
    assert world.apply(QUEEN, Intent("noop"), 1).accepted
    assert world.apply(QUEEN, Intent("move", {"direction": [1, 0]}), 1).reason == "queen_cannot_act"


def test_world_rng_is_isolated_from_global_rng():
    reference = build("rule", 3, max_steps=20).run().metrics

    async def interleaved():
        sched = build("rule", 3, max_steps=20)
        for _ in range(20):
            random.random()
            np.random.rand(5)
            await sched.step()
        return sched

    sched = asyncio.run(interleaved())
    assert sched.world.metrics() == reference


def test_no_bots_arm_is_the_natural_baseline():
    result = build("no_bots", 1, max_steps=20).run()
    assert result.metrics["deliveries"] == 0 and result.metrics["apoptotic_cells"] == 0


def test_arms_are_deterministic_and_have_distinct_configs():
    assert build("signals", 2, max_steps=25).run().trace_hash == build("signals", 2, max_steps=25).run().trace_hash
    assert len({build(arm, 2).config_hash() for arm in ARMS}) == len(ARMS)
    with pytest.raises(ValueError):
        build("nope", 1)


# Golden coordination numbers (rule policies, 150 ticks, seeds 1-3). A change
# means world or kernel semantics changed and results must be re-reviewed.
def _sum(arm, key):
    return sum(build(arm, seed, max_steps=150).run().metrics[key] for seed in (1, 2, 3))


def test_typed_claims_cut_duplicate_targeting():
    rule, signals = _sum("rule", "duplicate_targets"), _sum("signals", "duplicate_targets")
    assert signals < rule / 2


def test_hive_records_zone_evidence_and_kills_invalidate_it():
    sched = build("hive", 1, max_steps=60)
    sched.run()
    changes = sched.log.of_type(ev.MEMORY_CHANGED)
    admitted = [e for e in changes if e.data["to"] == m.ADMITTED]
    invalidated = [e for e in changes if e.data["to"] == m.INVALIDATED]
    assert admitted and all(e.data["subject"].startswith("zone:") for e in admitted)
    assert invalidated and {e.data["reason"] for e in invalidated} <= {"source_replaced", "dependency_invalidated"}
    assert not [e for e in sched.log.of_type(ev.INTENT_BLOCKED) if e.data["reason"] == "stale_evidence"]


def test_hive_queen_emits_cited_recruits():
    sched = build("hive_queen", 1, max_steps=40)
    sched.run()
    recruits = [e for e in sched.log.of_type(ev.SIGNAL_DEPOSITED) if e.data["kind"] == "recruit"]
    assert recruits and all(e.agent_id == QUEEN for e in recruits)


def nanobot_responder(request):
    view = json.loads(request.messages[1]["content"])["view"]
    intent = NanobotPolicy().decide(LocalView(agent_id=view["agent"], tick=view["tick"], revision=0,
                                              seed=request.seed, observation=view["observation"]))
    return json.dumps({"action": intent.action, "params": intent.params})


def test_llm_policy_drives_the_tumor_world():
    policy = LLMPolicy(FakeProvider(nanobot_responder), "stand-in", actions=LLM_ACTIONS,
                       signal_kinds=LLM_SIGNAL_KINDS, max_tokens=64)
    llm = build("rule", 1, max_steps=15, n_nanobots=4, policy_factory=lambda arm: policy).run()
    rule = build("rule", 1, max_steps=15, n_nanobots=4).run()
    assert llm.policy_failures == 0
    assert llm.metrics["deliveries"] == rule.metrics["deliveries"]
