"""Regression tests for bounded parameter sweeps."""

import pytest

from scripts.parameter_sweep import run_sweep


def test_run_sweep_rejects_non_positive_grid_size():
    with pytest.raises(ValueError, match="grid_points must be positive"):
        run_sweep(n_bots=5, steps=10, grid_points=0, seed=0, dry_run=True)
