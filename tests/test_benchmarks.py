"""Regression tests for deterministic local evaluation harnesses."""

from contextlib import redirect_stdout
from io import StringIO

import numpy as np

from backend.nanobot_simulation import TumorNanobotModel


PHEROMONE_NAMES = ("trail_pheromone", "alarm_pheromone", "recruitment_pheromone")


def _model(**kwargs):
    """Construct a small model without leaking simulation logs into test output."""
    with redirect_stdout(StringIO()):
        return TumorNanobotModel(
            domain_size=200.0,
            voxel_size=20.0,
            n_nanobots=2,
            tumor_radius=80.0,
            agent_type="Rule-Based",
            with_queen=False,
            use_llm_queen=False,
            **kwargs,
        )


def test_pheromone_flag_disables_secretion_and_following():
    model = _model(pheromones_enabled=False)

    assert model.pheromones_enabled is False
    for bot in model.nanobots:
        assert bot.chemotaxis_weights["trail_pheromone"] == 0.0
        assert bot.chemotaxis_weights["alarm_pheromone"] == 0.0
        assert bot.chemotaxis_weights["recruitment_pheromone"] == 0.0
        assert np.allclose(bot._compute_pheromone_direction(), 0.0)

    # The explicit secretion seam must be inert while disabled.
    model.deposit_pheromone("trail_pheromone", (1, 1, 0), 5.0)
    field = model.microenv.get_substrate("trail_pheromone")
    if field is not None:
        assert np.allclose(field.source_sink, 0.0)
        assert np.allclose(field.concentration, 0.0)


def test_enabled_pheromone_aliases_share_canonical_fields():
    model = _model(pheromones_enabled=True)

    assert model.pheromones_enabled is True
    for canonical, alias in zip(PHEROMONE_NAMES, ("trail", "alarm", "recruitment")):
        canonical_field = model.microenv.get_substrate(canonical)
        alias_field = model.microenv.get_substrate(alias)
        assert canonical_field is not None
        assert alias_field is canonical_field


def test_pheromone_benchmark_stdout_is_one_paired_json_document():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).parents[1]
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_DOTENV_DISABLED": "1",
            "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
            "CHAIN_READ_ENABLED": "0",
            "CHAIN_WRITE_ENABLED": "0",
            "PYTHONPATH": f"{repo}:{repo / 'backend'}",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts" / "benchmark_pheromones.py"),
            "--steps",
            "2",
            "--seeds",
            "1",
            "--bots",
            "1",
            "--radius",
            "80",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data["ok"] is True
    assert data["runs"]["without_pheromones"][0]["seed"] == 0
    assert data["runs"]["with_pheromones"][0]["seed"] == 0
    assert "delta_kill_rate_percentage_points" in data["summary"]
    assert "improvement_pct" not in data["summary"]


def test_queen_trial_uses_model_queen_once(monkeypatch):
    from types import SimpleNamespace

    from scripts import evaluate_queen

    class CountingQueen:
        instances = 0
        step_calls = 0

        def __init__(self, *args, **kwargs):
            type(self).instances += 1
            self.episode_counter = 0
            self.worker_params = {}

        def step(self):
            type(self).step_calls += 1

    class FakeModel:
        def __init__(self, **kwargs):
            self.nanobots = []
            self.microenv = SimpleNamespace(add_substrate=lambda *args, **kwargs: object())
            self.geometry = SimpleNamespace(
                tumor_cells=[object()],
                get_living_cells=lambda: self.geometry.tumor_cells,
            )
            self.queen = CountingQueen() if kwargs["with_queen"] else None

        def step(self):
            return None

    monkeypatch.setattr(evaluate_queen, "TumorNanobotModel", FakeModel)
    monkeypatch.setattr(evaluate_queen, "QueenNanobot", CountingQueen)

    evaluate_queen.run_trial(
        n_steps=2,
        n_bots=1,
        tumor_radius=80.0,
        seed=0,
        with_queen=True,
        episode_length=2,
    )

    assert CountingQueen.instances == 1
    assert CountingQueen.step_calls == 2


def test_pheromone_conditions_use_same_seed_and_keep_on_aliases():
    from scripts import benchmark_pheromones

    off = benchmark_pheromones.run_simulation(20, 2, 80.0, 7, False)
    on = benchmark_pheromones.run_simulation(20, 2, 80.0, 7, True)

    assert off["seed"] == on["seed"] == 7
    assert off["total_cells"] == on["total_cells"] > 0
    assert off["pheromones_enabled"] is False
    assert not any(off["pheromone_fields"].values())
    assert on["pheromones_enabled"] is True
    assert all(on["pheromone_fields"].values())
    assert on["pheromone_aliases_preserved"] is True
    assert all(value == 0.0 for value in off["pheromone_concentration_mass"].values())
    assert any(value > 0.0 for value in on["pheromone_concentration_mass"].values())


def test_queen_evaluation_json_labels_synthetic_scenarios():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).parents[1]
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_DOTENV_DISABLED": "1",
            "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
            "CHAIN_READ_ENABLED": "0",
            "CHAIN_WRITE_ENABLED": "0",
            "PYTHONPATH": f"{repo}:{repo / 'backend'}",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts" / "evaluate_queen.py"),
            "--seeds",
            "1",
            "--scenarios",
            "1",
            "--steps",
            "2",
            "--bots",
            "1",
            "--episode-length",
            "2",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data["ok"] is True
    assert data["scenario_type"] == "synthetic"
    assert data["config"]["n_scenarios"] == 1
    assert data["pairs"]["synthetic_small_tumor"][0]["same_seed_and_config"] is True
    assert "delta_kill_rate_percentage_points" in data["summary"]
    assert "improvement_pct" not in data["summary"]
    assert "success_gate_passed" not in data["summary"]
    assert "patient" not in completed.stdout.lower()


def test_benchmark_rejects_nonpositive_steps_with_json_error():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo}:{repo / 'backend'}"
    completed = subprocess.run(
        [sys.executable, str(repo / "scripts" / "benchmark_pheromones.py"), "--steps", "0"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert completed.returncode == 2
    error = json.loads(completed.stdout)
    assert error["ok"] is False
    assert error["error"]["type"] == "input_validation"


def test_nanobot_module_supports_package_import_without_backend_path():
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo)
    completed = subprocess.run(
        [sys.executable, "-c", "import backend.nanobot_simulation"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_queen_cannot_reenable_disabled_pheromone_following():
    from backend.nanobot_simulation import QueenNanobot

    model = _model(pheromones_enabled=False)
    queen = QueenNanobot(model=model, use_llm=False)
    queen.worker_params["trail_weight"] = 1.5
    queen.worker_params["alarm_weight"] = -0.9
    queen._apply_params_to_workers()

    for bot in model.nanobots:
        assert bot.chemotaxis_weights["trail_pheromone"] == 0.0
        assert bot.chemotaxis_weights["alarm_pheromone"] == 0.0
