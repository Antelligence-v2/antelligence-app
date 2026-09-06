"""TDD contract tests for the vision-linked Experiment Lab backend."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "experiments.sqlite3"
    monkeypatch.setenv("ANTELLIGENCE_RUN_DB", str(db_path))
    monkeypatch.setenv("ANTELLIGENCE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANTELLIGENCE_OFFLINE", "1")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX", "0")
    monkeypatch.setenv("CHAIN_READ_ENABLED", "0")
    monkeypatch.setenv("CHAIN_WRITE_ENABLED", "0")
    monkeypatch.delenv("IO_SECRET_KEY", raising=False)
    sys.modules.pop("backend.main", None)
    module = importlib.import_module("backend.main")
    assert Path(module.__file__).resolve().parent == REPO_ROOT / "backend"
    return module, TestClient(module.app), db_path


def experiment_payload(**config_overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "domain_size": 100.0,
        "voxel_size": 20.0,
        "n_nanobots": 2,
        "tumor_radius": 30.0,
        "agent_type": "Rule-Based",
        "use_queen": False,
        "use_llm_queen": False,
        "max_steps": 2,
        "seed": 17,
        "offline": True,
        "cell_density": 0.001,
        "vessel_density": 0.01,
    }
    config.update(config_overrides)
    return {"name": "tiny baseline", "seeds": [17, 23], "config": config}


def test_experiment_runs_real_three_arm_same_seed_cases_and_persists(api):
    module, client, _ = api
    response = client.post("/experiments", json=experiment_payload())
    assert response.status_code == 200, response.text
    experiment = response.json()

    assert experiment["status"] == "completed"
    assert experiment["case_count"] == 6
    assert [case["case_id"] for case in experiment["cases"]] == [
        "no_bots:17", "fixed:17", "pheromone:17",
        "no_bots:23", "fixed:23", "pheromone:23",
    ]
    assert {case["arm"] for case in experiment["cases"]} == {"no_bots", "fixed", "pheromone"}
    assert all(case["proof_ok"] is not True for case in experiment["cases"] if "proof_ok" in case)
    for seed in experiment["request"]["seeds"]:
        same_seed = [case for case in experiment["cases"] if case["seed"] == seed]
        assert len({case["initial_geometry_hash"] for case in same_seed}) == 1
        assert same_seed[0]["config"]["n_nanobots"] == 0
        assert same_seed[0]["config"]["pheromones_enabled"] is False
        assert same_seed[1]["config"]["n_nanobots"] == 2
        assert same_seed[1]["config"]["pheromones_enabled"] is False
        assert same_seed[2]["config"]["n_nanobots"] == 2
        assert same_seed[2]["config"]["pheromones_enabled"] is True
        assert same_seed[0]["run_id"]
        run = client.get(f"/simulation/tumor/runs/{same_seed[2]['run_id']}")
        assert run.status_code == 200
        assert run.json()["config"]["pheromones_enabled"] is True

    listed = client.get("/experiments").json()
    assert listed["has_more"] is False
    assert listed["experiments"][0]["experiment_id"] == experiment["experiment_id"]
    loaded = client.get(f"/experiments/{experiment['experiment_id']}")
    assert loaded.status_code == 200
    assert loaded.json() == experiment


def test_replay_is_real_and_persists_match(api):
    _, client, _ = api
    created = client.post("/experiments", json=experiment_payload()).json()
    case = created["cases"][2]
    replay = client.post(f"/experiments/{created['experiment_id']}/replay/{case['case_id']}")
    assert replay.status_code == 200, replay.text
    result = replay.json()
    assert result["status"] == "matched"
    assert result["expected_trace_hash"] == case["trace_hash"]
    assert result["actual_trace_hash"] == case["trace_hash"]
    assert result["replay_run_id"] != case["run_id"]
    loaded = client.get(f"/experiments/{created['experiment_id']}").json()
    assert loaded["replay_checks"][-1] == result


def test_experiment_rejects_forbidden_policy_and_budget_before_models(api, monkeypatch):
    module, client, _ = api
    monkeypatch.setattr(module, "TumorNanobotModel", lambda **_: (_ for _ in ()).throw(AssertionError("constructed")))
    for overrides in (
        {"agent_type": "LLM-Powered"},
        {"offline": False},
        {"use_queen": True},
        {"use_llm_queen": True},
        {"domain_size": 1000.0, "voxel_size": 1.0},
        {"n_nanobots": 26},
        {"max_steps": 201},
    ):
        response = client.post("/experiments", json=experiment_payload(**overrides))
        assert response.status_code == 422, (overrides, response.text)


def test_failed_batch_is_durable_and_not_completed(api, monkeypatch):
    module, client, db_path = api
    real_runner = module.run_tumor_simulation
    calls = 0

    async def fail_second(config):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("tiny model failed")
        return await real_runner(config)

    monkeypatch.setattr(module, "run_tumor_simulation", fail_second)
    response = client.post("/experiments", json=experiment_payload())
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["experiment_id"]
    failed = client.get(f"/experiments/{detail['experiment_id']}").json()
    assert failed["status"] == "failed"
    assert failed["case_count"] == 1
    assert failed["error"] == "tiny model failed"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT status FROM experiments WHERE experiment_id = ?", (detail["experiment_id"],)).fetchone()
    assert row == ("failed",)


def test_tampered_trace_never_reports_matched(api):
    module, client, db_path = api
    created = client.post("/experiments", json=experiment_payload()).json()
    experiment_id = created["experiment_id"]
    case = created["cases"][0]
    with sqlite3.connect(db_path) as conn:
        raw = conn.execute("SELECT response_json FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()[0]
        document = json.loads(raw)
        document["cases"][0]["trace_hash"] = "tampered"
        conn.execute("UPDATE experiments SET response_json = ? WHERE experiment_id = ?", (json.dumps(document), experiment_id))
        conn.commit()
    replay = client.post(f"/experiments/{experiment_id}/replay/{case['case_id']}")
    assert replay.status_code == 200
    assert replay.json()["status"] in {"mismatch", "error"}
    assert replay.json()["status"] != "matched"


def test_legacy_tumor_snapshot_get_does_not_gain_new_default_fields(api):
    module, client, _ = api
    legacy = {
        "config": {
            "domain_size": 100.0,
            "voxel_size": 20.0,
            "n_nanobots": 1,
            "tumor_radius": 30.0,
            "agent_type": "Rule-Based",
            "use_queen": False,
            "use_llm_queen": False,
            "max_steps": 1,
            "seed": 17,
            "offline": True,
        },
        "total_steps_run": 1,
        "total_time": 0.1,
        "final_metrics": {},
        "history": [],
        "tumor_statistics": {},
        "final_substrate_data": None,
        "blockchain_logs": [],
        "run_id": "legacy-run",
        "config_hash": "legacy-config",
        "proof_staged": True,
        "proof_ok": False,
        "public_values": {},
        "proof_bundle": {},
        "mock_bundle": {},
        "provenance": {},
    }
    module.TUMOR_RUN_STORE.run_store.save_run("legacy-run", "completed", legacy["config"], {})
    with sqlite3.connect(module.TUMOR_RUN_STORE.db_path) as conn:
        conn.execute(
            "INSERT INTO tumor_run_results (run_id, result_json) VALUES (?, ?)",
            ("legacy-run", json.dumps(legacy)),
        )
        conn.commit()
    response = client.get("/simulation/tumor/runs/legacy-run")
    assert response.status_code == 200
    assert response.json() == legacy


def test_new_tumor_post_and_get_preserve_exact_snapshot(api):
    _, client, _ = api
    payload = experiment_payload()["config"]
    posted = client.post("/simulation/tumor/run", json=payload)
    assert posted.status_code == 200, posted.text
    run_id = posted.json()["run_id"]
    retrieved = client.get(f"/simulation/tumor/runs/{run_id}")
    assert retrieved.status_code == 200
    assert retrieved.json() == posted.json()


def test_fresh_process_reloads_experiment_library(tmp_path: Path):
    db_path = tmp_path / "fresh.sqlite3"
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHON_DOTENV_DISABLED": "1",
        "ANTELLIGENCE_OFFLINE": "1",
        "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
        "CHAIN_READ_ENABLED": "0",
        "CHAIN_WRITE_ENABLED": "0",
        "ANTELLIGENCE_RUN_DB": str(db_path),
    })
    code = """
from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app)
payload = {
  'name': 'fresh', 'seeds': [17], 'config': {
    'domain_size': 100.0, 'voxel_size': 20.0, 'n_nanobots': 1,
    'tumor_radius': 30.0, 'agent_type': 'Rule-Based', 'use_queen': False,
    'use_llm_queen': False, 'max_steps': 1, 'seed': 17, 'offline': True,
    'cell_density': 0.001, 'vessel_density': 0.01
  }
}
created = client.post('/experiments', json=payload)
print(created.status_code)
print(client.get('/experiments/' + created.json()['experiment_id']).status_code)
print(client.get('/experiments').json()['experiments'][0]['case_count'])
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "200\n200\n3" in result.stdout
