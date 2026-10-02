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


def test_3d_immune_cells_use_true_distance():
    """Review fix: immune cells measured x/y only, so they attacked cells far away in z."""
    from backend.tumor_environment import CellType, ImmuneCell, ImmuneCellType, TumorCell
    target = TumorCell(cell_id=1, position=(0.0, 0.0, 100.0), cell_type=CellType.DIFFERENTIATED)
    immune = ImmuneCell(cell_id=1, position=(0.0, 0.0, 0.0), cell_type=list(ImmuneCellType)[0], activation_level=1.0)
    resistance = target.resistance_level
    immune.update(0.1, [target])
    assert target.resistance_level == resistance  # 100 um away vertically: no attack
    assert immune.position[2] > 0.0  # it moves toward the target along z


def test_3d_daughters_leave_the_parents_plane():
    from backend.tumor_environment import CellType, TumorCell
    w = TumorWorld(2, dimensionality=3)
    parent = TumorCell(cell_id=0, position=(300.0, 300.0, 300.0), cell_type=CellType.DIFFERENTIATED)
    daughter = TumorCell(cell_id=1, position=(320.0, 300.0, 300.0), cell_type=CellType.DIFFERENTIATED)
    with w.physics.rng():
        w.physics._place_daughter_3d(parent, daughter)
    offset = [daughter.position[i] - parent.position[i] for i in range(3)]
    assert math.isclose(math.hypot(*offset), 20.0, rel_tol=1e-9)
    assert abs(offset[2]) > 1e-6


def test_3d_repulsion_pushes_along_z():
    w = TumorWorld(2, dimensionality=3)
    cells = [c for c in w.physics.geometry.tumor_cells if c.is_alive][:2]
    x, y, z = cells[0].position
    cells[1].position = (x, y, z + 10.0)  # stacked vertically, 10 um apart
    for other in w.physics.geometry.tumor_cells[2:]:
        other.is_alive = False
    w.physics._apply_cell_mechanics()
    assert cells[1].position[2] - cells[0].position[2] > 10.0


def test_3d_missing_substrate_gradient_has_three_components():
    w = TumorWorld(2, dimensionality=3)
    assert w.physics.gradient("trail_pheromone", (300.0, 300.0, 300.0)) == (0.0, 0.0, 0.0)


def test_3d_signal_marks_carry_z():
    scheduler, _ = run(arm="signals", dimensionality=3, max_steps=25)
    marks = [m for f in scheduler.frames for m in f["signals"]]
    assert marks and all(len(m) == 6 for m in marks)
