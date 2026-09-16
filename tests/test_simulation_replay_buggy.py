from unittest.mock import MagicMock

import pytest
from pathlib import Path
from unittest.mock import patch

from backend.run_store import SQLiteRunStore
from backend.simulation_replay import replay_artifact_metrics

def test_simulation_replay_determinism(tmp_path: Path):
    """Verify that replaying a stored run produces the same metrics."""
    db_path = tmp_path / "test_runs.sqlite3"
    store = SQLiteRunStore(db_path)
    
    run_id = "replay-test-001"
    config = {
        "num_bots": 2,
        "steps": 5,
        "domain_size": 100.0,
        "voxel_size": 10.0,
        "seed": 42
    }
    metrics = {
        "kill_rate": 0.0,
        "total_deliveries": 0,
        "cells_killed": 0,
        "step_count": 5
    }
    
    store.save_run(run_id, "completed", config, metrics)
    retrieved_run = store.get_run(run_id)
    assert retrieved_run is not None
    assert retrieved_run["run_id"] == run_id
    assert retrieved_run["status"] == "completed"
    assert retrieved_run["config"]["num_bots"] == 2

    with patch("backend.simulation_replay.build_model_from_config") as mock_build:
        mock_model = MagicMock()
        mock_model.step_count = 5
        mock_build.return_value = (MagicMock(), mock_model)

        with patch("backend.simulation_replay.compute_metrics") as mock_metrics:
            mock_metrics.return_value = metrics
            replayed_metrics = replay_artifact_metrics(retrieved_run)

    assert replayed_metrics["step_count"] == 5
    assert replayed_metrics["kill_rate"] == 0.0
