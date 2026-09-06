"""Research metrics and implicit-policy safety at the shared runtime boundary."""

from types import SimpleNamespace

from backend.config import SimulationConfig
from backend.runtime_factory import compute_metrics


def test_empty_geometry_cannot_report_successful_treatment():
    model = SimpleNamespace(
        metrics={}, step_count=1,
        geometry=SimpleNamespace(get_tumor_statistics=lambda: {"total_cells": 0, "living_cells": 0}),
    )
    metrics = compute_metrics(model)
    assert metrics["total_cells"] == 0
    assert metrics["living_cells"] == 0
    assert metrics["kill_rate"] == 0.0


def test_model_preserves_existing_positional_seed_argument():
    from backend.nanobot_simulation import TumorNanobotModel
    model = TumorNanobotModel(1, 100.0, 20.0, 30.0, "Rule-Based", False, False, "unused", None, 17, None)
    assert model.seed == 17


def test_minimal_api_and_replay_explicitly_choose_rule_based_workers():
    kwargs = SimulationConfig(queen_enabled=True).to_model_kwargs()
    assert kwargs.get("agent_type") == "Rule-Based"
    assert kwargs.get("use_llm_queen") is False
