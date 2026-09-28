"""Per-tick visualization frames: complete, deterministic, and outside the evidence chain."""

import base64
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from antelligence.api.app import create_app
from antelligence.experiments.registry import RunSpec, world
from antelligence.kernel.frames import encode_field

SPATIAL = [
    RunSpec("tumor", "pheromone", 1, {"max_steps": 15, "n_nanobots": 5}),
    RunSpec("foraging", "hive_memory_signals", 101, {"max_steps": 25}),
]


def build(spec, record=True):
    scheduler = world(spec.world).build(spec, f"frames-{spec.world}")
    scheduler.record_frames = scheduler.record_frames and record
    return scheduler


@pytest.mark.parametrize("spec", SPATIAL, ids=lambda s: s.world)
def test_frames_do_not_change_the_trace(spec):
    with_frames, without = build(spec), build(spec, record=False)
    a, b = with_frames.run(), without.run()
    assert a.trace_hash == b.trace_hash
    assert a.event_count == b.event_count
    assert without.frames == []


@pytest.mark.parametrize("spec", SPATIAL, ids=lambda s: s.world)
def test_one_frame_per_tick_plus_initial_state(spec):
    scheduler = build(spec)
    result = scheduler.run()
    assert [f["tick"] for f in scheduler.frames] == list(range(0, result.ticks + 1))
    assert scheduler.scene["kind"] in {"tumor", "grid"}


@pytest.mark.parametrize("spec", SPATIAL, ids=lambda s: s.world)
def test_frames_are_deterministic(spec):
    first, second = build(spec), build(spec)
    first.run()
    second.run()
    assert first.frames == second.frames


def test_tumor_frames_carry_bots_cells_and_fields():
    scheduler = build(SPATIAL[0])
    scheduler.run()
    frame = scheduler.frames[-1]["world"]
    assert len(frame["bots"]) == 5
    assert frame["cells"] and all(len(c) == 4 for c in frame["cells"])
    assert {"drug", "oxygen", "trail_pheromone"} <= set(frame["fields"])
    nx, ny = scheduler.scene["field_shape"]
    assert len(base64.b64decode(frame["fields"]["drug"]["b64"])) == nx * ny


def test_foraging_frames_show_signals_and_movement():
    scheduler = build(SPATIAL[1])
    scheduler.run()
    assert any(f["signals"] for f in scheduler.frames)
    positions = [tuple(map(tuple, f["world"]["agents"])) for f in scheduler.frames]
    assert len(set(positions)) > 1


def test_encode_field_quantizes_to_its_own_max():
    grid = np.arange(16, dtype=float).reshape(4, 4, 1)
    encoded = encode_field(grid, stride=2)
    values = np.frombuffer(base64.b64decode(encoded["b64"]), dtype=np.uint8).reshape(2, 2)
    assert encoded["max"] == 10.0
    assert values[1, 1] == 255 and values[0, 0] == 0
    assert encode_field(np.zeros((3, 3)))["max"] == 0.0


def test_frames_api():
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    run = client.post("/engine/runs", json={"world": "foraging", "arm": "signals", "case": 101, "params": {"max_steps": 20}}).json()
    body = client.get(f"/engine/runs/{run['run_id']}/frames")
    assert body.status_code == 200
    data = body.json()
    assert data["scene"]["grid"] == [10, 10]
    assert len(data["frames"]) == run["ticks"] + 1

    dag = client.post("/engine/runs", json={"world": "task_dag", "arm": "solo_planner", "case": 1}).json()
    missing = client.get(f"/engine/runs/{dag['run_id']}/frames")
    assert missing.status_code == 404
    assert "no frames" in missing.json()["detail"]
    assert client.get("/engine/runs/nope/frames").json()["detail"] == "run not found"
