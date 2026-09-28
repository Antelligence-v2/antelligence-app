"""The tumor world in 3D: same rules, one more axis; 2D runs are untouched."""

import math

import pytest

from antelligence.experiments.registry import RunSpec, world
from antelligence.worlds.tumor import TumorWorld


def run(arm="rule", case=3, **params):
    scheduler = world("tumor").build(RunSpec("tumor", arm, case, params), f"t3-{arm}-{case}")
    return scheduler, scheduler.run()


def test_3d_run_completes_and_kills_cells():
    scheduler, result = run(dimensionality=3, max_steps=120)
    assert result.metrics["initial_living_cells"] > 50
    assert result.metrics["deliveries"] > 0
    assert result.metrics["kill_rate"] > 0.2


def test_3d_positions_and_frames_have_z():
    scheduler, _ = run(dimensionality=3, max_steps=20)
    assert scheduler.scene["dimensionality"] == 3
    assert len(scheduler.scene["center"]) == 3 and all(len(v) == 3 for v in scheduler.scene["vessels"])
    frame = scheduler.frames[-1]["world"]
    assert all(len(b) == 6 for b in frame["bots"])   # x, y, state, payload, target, z
    assert all(len(c) == 5 for c in frame["cells"])  # x, y, phase, id, z
    zs = {round(c[4]) for c in frame["cells"]}
    assert len(zs) > 5  # cells fill a volume, not a plane


def test_3d_bots_move_in_z():
    scheduler, _ = run(dimensionality=3, max_steps=40)
    z = [f["world"]["bots"][0][5] for f in scheduler.frames]
    assert max(z) - min(z) > 10


def test_3d_is_deterministic():
    (_, a), (_, b) = run(dimensionality=3, max_steps=30), run(dimensionality=3, max_steps=30)
    assert a.trace_hash == b.trace_hash


def test_2d_config_is_unchanged_by_the_new_parameter():
    _, implicit = run(max_steps=30)
    _, explicit = run(max_steps=30, dimensionality=2)
    assert implicit.trace_hash == explicit.trace_hash
    assert "dimensionality" not in TumorWorld(1).describe()
    assert TumorWorld(1, dimensionality=3).describe()["dimensionality"] == 3


def test_3d_rejects_2d_moves_and_bad_dimensions():
    w = TumorWorld(1, dimensionality=3, n_nanobots=1)
    from antelligence.kernel.types import Intent
    w.observe("bot-000", 1)
    assert w.apply("bot-000", Intent("move", {"direction": [1.0, 0.0]}), 1).reason == "bad_direction"
    assert w.apply("bot-000", Intent("move", {"direction": [0.0, 0.0, 1.0]}), 1).accepted
    with pytest.raises(ValueError):
        TumorWorld(1, dimensionality=4)


def test_3d_signals_use_3d_positions():
    scheduler, _ = run(arm="signals", dimensionality=3, max_steps=25)
    deposited = [e for e in scheduler.log if e.type == "signal_deposited"]
    assert deposited and all(len(e.data["pos"]) == 3 for e in deposited)
    assert all(math.isfinite(c) for e in deposited for c in e.data["pos"])


@pytest.mark.parametrize("arm", ["no_bots", "rule", "pheromone", "signals", "hive", "hive_queen"])
def test_every_arm_runs_in_3d(arm):
    _, result = run(arm=arm, dimensionality=3, max_steps=40)
    assert result.ticks > 0
    assert result.metrics["unsafe_act_count" if "unsafe_act_count" in result.metrics else "invalid_actions"] == 0
