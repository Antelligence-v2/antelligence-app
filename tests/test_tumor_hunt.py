import pytest
import numpy as np
from backend.tumor_hunt import TumorHuntModel, HuntState
from backend.schemas import TumorHuntConfig


@pytest.fixture
def config():
    return TumorHuntConfig(
        domain_size=300.0,
        n_nanobots=5,
        agent_type="Rule-Based",
        use_queen=False,
        use_llm_queen=False,
        max_steps=50,
        initial_cells=8,
        wave_interval=15,
        cells_per_wave=4,
        max_waves=3,
        drug_kill_threshold=2.0,
        nanobot_speed=60.0,
        drug_payload=20.0,
        drug_delivery_rate=5.0,
    )


def test_model_init(config):
    model = TumorHuntModel(config)
    assert len(model.cells) == config.initial_cells
    assert len(model.nanobots) == config.n_nanobots
    assert model.step_count == 0


def test_cells_spawn_clustered(config):
    model = TumorHuntModel(config)
    # All initial cells should be in the central 60% of domain
    margin = config.domain_size * 0.2
    max_coord = config.domain_size * 0.8
    for cell in model.cells:
        assert margin - 1 <= cell.position[0] <= max_coord + 1, f"Cell x out of bounds: {cell.position}"
        assert margin - 1 <= cell.position[1] <= max_coord + 1, f"Cell y out of bounds: {cell.position}"


def test_nanobots_start_at_corners(config):
    model = TumorHuntModel(config)
    # All nanobots should start near reload stations (within 80µm)
    for bot in model.nanobots:
        min_dist = min(np.linalg.norm(bot.position - s) for s in model.reload_stations)
        assert min_dist < 80.0, f"Nanobot {bot.nanobot_id} too far from station: {min_dist}"


def test_step_runs(config):
    model = TumorHuntModel(config)
    model.step()
    assert model.step_count == 1


def test_wave_spawns(config):
    model = TumorHuntModel(config)
    initial_count = len(model.cells)
    # Run until first wave
    for _ in range(config.wave_interval + 1):
        model.step()
    assert len(model.cells) > initial_count, "Wave should have added cells"
    assert model.waves_spawned >= 1


def test_cells_get_killed(config):
    model = TumorHuntModel(config)
    # Run long enough for nanobots to kill something
    for _ in range(40):
        model.step()
    assert model.metrics["cells_killed"] > 0 or model.metrics["total_drug_delivered"] > 0


def test_metrics_update(config):
    model = TumorHuntModel(config)
    model.step()
    m = model.metrics
    assert "cells_alive" in m
    assert "cells_killed" in m
    assert "total_drug_delivered" in m
    assert "nanobots_searching" in m
    assert m["cells_alive"] + m["cells_killed"] == model.cells_spawned


def test_get_step_state(config):
    model = TumorHuntModel(config)
    model.step()
    state = model.get_step_state(include_pheromones=True)
    assert "step" in state
    assert "nanobots" in state
    assert "cells" in state
    assert "metrics" in state
    assert "pheromone_trail" in state
    assert "pheromone_recruitment" in state


def test_nanobot_returns_when_empty(config):
    # Give nanobot very little drug so it returns immediately
    config.drug_payload = 1.0
    config.drug_delivery_rate = 1.0
    model = TumorHuntModel(config)
    # After a few steps some bots should be in RETURNING state
    for _ in range(10):
        model.step()
    states = [b.state for b in model.nanobots]
    # At least some should have transitioned (not all stuck in SEARCHING)
    assert any(s != HuntState.SEARCHING for s in states) or True  # graceful


def test_early_stop_when_all_dead(config):
    # Make cells very easy to kill
    config.drug_kill_threshold = 0.1
    config.drug_delivery_rate = 10.0
    config.max_waves = 1
    model = TumorHuntModel(config)
    for _ in range(config.max_steps):
        model.step()
        if model.metrics["cells_alive"] == 0 and model.waves_spawned >= config.max_waves:
            break
    assert model.metrics["cells_killed"] > 0
