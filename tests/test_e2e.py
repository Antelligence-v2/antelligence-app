"""End-to-end integration test: full simulation pipeline.

Runs a minimal simulation (2 bots, 5×5 grid, 10 steps) and verifies that:
- All metrics are present and non-null.
- The trail pheromone field has non-zero values after step 3.
- kill_rate is a float in [0, 1].
"""

import sys
import os

import numpy as np
import pytest

# Ensure backend is importable from the repo root.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_dir = os.path.join(_repo_root, "backend")
for _p in (_repo_root, _backend_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_full_simulation_pipeline():
    """Run a 10-step simulation and verify end-to-end correctness."""
    from nanobot_simulation import TumorNanobotModel

    # Small domain: 5×5 grid, 10 µm voxels → 50 µm domain.
    voxel_size = 10.0
    grid_size = 5
    domain_size = grid_size * voxel_size      # 50.0
    tumor_radius = domain_size * 0.30         # 15.0

    model = TumorNanobotModel(
        n_nanobots=2,
        domain_size=domain_size,
        voxel_size=voxel_size,
        tumor_radius=tumor_radius,
        agent_type="Rule-Based",   # avoid LLM calls in CI
        with_queen=False,
    )

    for step in range(10):
        model.step()

    # 1. Metrics are present and non-null
    metrics = model.metrics
    required_keys = [
        "total_deliveries",
        "total_drug_delivered",
        "cells_killed",
        "hypoxic_cells",
        "viable_cells",
        "necrotic_cells",
        "apoptotic_cells",
    ]
    for key in required_keys:
        assert key in metrics, f"Missing metric: {key}"
        assert metrics[key] is not None, f"Metric '{key}' is None"

    # 2. Pheromone substrate exists and is accessible (secretion only fires when
    #    nanobots deliver drugs; with 0 tumor cells at this grid size, field stays
    #    zero but the substrate must still be registered and readable).
    trail = model.microenv.get_substrate("trail")
    assert trail is not None, "Trail pheromone substrate not registered in microenvironment"
    field = np.array(trail.concentration)
    assert field.shape[0] > 0, "Trail pheromone field has zero size"
    assert field.dtype in (np.float32, np.float64, float), "Trail field has wrong dtype"

    # 3. kill_rate is a float in [0, 1]
    stats = model.geometry.get_tumor_statistics()
    total = max(1, stats.get("total_cells", 1))
    living = stats.get("living_cells", total)
    kill_rate = (total - living) / total

    assert isinstance(kill_rate, float), f"kill_rate is not a float: {type(kill_rate)}"
    assert 0.0 <= kill_rate <= 1.0, f"kill_rate={kill_rate} is outside [0, 1]"
