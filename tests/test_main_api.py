"""Contract tests for the frontend-facing FastAPI application."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Import a fresh app against an isolated, offline SQLite database."""
    monkeypatch.setenv("ANTELLIGENCE_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("ANTELLIGENCE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANTELLIGENCE_OFFLINE", "1")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX", "0")
    monkeypatch.setenv("CHAIN_READ_ENABLED", "0")
    monkeypatch.setenv("CHAIN_WRITE_ENABLED", "0")
    monkeypatch.delenv("IO_SECRET_KEY", raising=False)

    sys.modules.pop("backend.main", None)
    module = importlib.import_module("backend.main")
    return module, TestClient(module.app)


def _offline_config(**overrides: object) -> dict[str, object]:
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
    }
    config.update(overrides)
    return config


def test_fresh_process_import_does_not_eagerly_import_blockchain_client(tmp_path: Path):
    code = """
import builtins
real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == "blockchain.client":
        raise AssertionError("blockchain.client imported during API startup")
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
import backend.main
print("frontend-api-import-ok")
"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "PYTHON_DOTENV_DISABLED": "1",
            "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
            "CHAIN_READ_ENABLED": "0",
            "CHAIN_WRITE_ENABLED": "0",
            "ANTELLIGENCE_RUN_DB": str(tmp_path / "import.sqlite3"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "frontend-api-import-ok" in result.stdout


def test_cors_allows_actual_local_frontend_ports(api):
    _, client = api
    for origin in (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ):
        response = client.options(
            "/simulation/tumor/run",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_offline_mode_rejects_llm_requests(api):
    _, client = api
    response = client.post(
        "/simulation/tumor/run",
        json=_offline_config(agent_type="LLM-Powered"),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "type": "offline_mode_rejected",
        "calls": ["llm"],
        "message": "Offline mode rejects LLM and chain calls.",
    }


def test_offline_mode_rejects_chain_requests(api, monkeypatch: pytest.MonkeyPatch):
    _, client = api
    monkeypatch.setenv("CHAIN_READ_ENABLED", "1")
    response = client.post("/simulation/tumor/run", json=_offline_config())
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "type": "offline_mode_rejected",
        "calls": ["chain"],
        "message": "Offline mode rejects LLM and chain calls.",
    }


def test_patient_geometry_is_rejected_instead_of_using_synthetic_geometry(api):
    _, client = api
    response = client.post(
        "/simulation/tumor/run",
        json=_offline_config(use_brats_geometry=True, brats_patient_id="patient-001"),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "type": "unsupported_patient_geometry",
        "message": "Patient-specific geometry is not supported by this API runtime.",
    }


def test_tumor_run_returns_actual_provenance_and_retrieves_from_sqlite(api):
    module, client = api
    request_config = _offline_config()
    response = client.post("/simulation/tumor/run", json=request_config)

    assert response.status_code == 200, response.text
    data = response.json()
    run_id = data["run_id"]
    uuid.UUID(run_id)
    assert data["config"]["seed"] == 17
    expected_config_hash = hashlib.sha256(
        json.dumps(data["config"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert data["config_hash"] == expected_config_hash
    assert data["provenance"]["config"] == data["config"]
    assert data["provenance"]["config_hash"] == expected_config_hash
    assert data["proof_staged"] is True
    assert data["proof_ok"] is False
    assert data["proof_bundle"]["is_mock"] is True
    assert data["mock_bundle"]["proof_bundle"]["run_id"] == run_id
    assert set(data["public_values"]) == {
        "config_hash",
        "kill_rate_bps",
        "nanobot_count",
        "tumor_radius",
        "steps",
    }
    assert data["public_values"]["config_hash"] == expected_config_hash
    assert data["public_values"]["nanobot_count"] == request_config["n_nanobots"]
    assert data["public_values"]["tumor_radius"] == int(request_config["tumor_radius"])
    assert data["public_values"]["steps"] == request_config["max_steps"]

    # Retrieval must work without the module-level in-memory path.
    module._TUMOR_RUNS.clear()
    retrieved = client.get(f"/simulation/tumor/runs/{run_id}")
    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["run_id"] == run_id
    assert retrieved.json()["config"] == data["config"]
    assert retrieved.json()["config_hash"] == data["config_hash"]
    assert retrieved.json()["proof_bundle"] == data["proof_bundle"]
    assert retrieved.json()["public_values"] == data["public_values"]


def test_seed_is_honored_for_repeated_rule_based_runs(api):
    _, client = api
    first = client.post("/simulation/tumor/run", json=_offline_config(seed=23)).json()
    second = client.post("/simulation/tumor/run", json=_offline_config(seed=23)).json()
    assert first["run_id"] != second["run_id"]
    assert first["config_hash"] == second["config_hash"]
    assert first["tumor_statistics"] == second["tumor_statistics"]
    assert first["final_metrics"] == second["final_metrics"]
    assert first["history"] == second["history"]


def test_density_settings_change_generated_geometry(api):
    _, client = api
    sparse = client.post('/simulation/tumor/run', json=_offline_config(cell_density=0.001, vessel_density=0.01)).json()
    dense = client.post('/simulation/tumor/run', json=_offline_config(cell_density=0.004, vessel_density=0.04)).json()
    assert dense['tumor_statistics']['initial_living_cells'] > sparse['tumor_statistics']['initial_living_cells']
    assert len(dense['history'][0]['vessels']) > len(sparse['history'][0]['vessels'])


@pytest.mark.parametrize('overrides', [
    {'enable_immune_system': False}, {'enable_bbb': False},
    {'misspelled_parameter': True}, {'seed': -1},
    {'domain_size': 1e12}, {'cell_density': 1e12},
])
def test_unsupported_or_unbounded_configs_fail_before_simulation(api, overrides, monkeypatch):
    module, client = api
    def forbidden_model(**kwargs):
        raise AssertionError('invalid inputs reached the allocation boundary')
    monkeypatch.setattr(module, 'TumorNanobotModel', forbidden_model)
    response = client.post('/simulation/tumor/run', json=_offline_config(**overrides))
    assert response.status_code == 422


def test_initial_hypoxia_is_captured_before_model_steps(api, monkeypatch):
    module, client = api
    real_model = module.TumorNanobotModel

    def controlled_model(**kwargs):
        model = real_model(**kwargs)
        for cell in model.geometry.tumor_cells:
            cell.phase = type(cell.phase).VIABLE
        cell = model.geometry.tumor_cells[0]
        cell.phase = type(cell.phase).HYPOXIC
        real_step = model.step
        def step():
            real_step()
            for current in model.geometry.tumor_cells:
                current.phase = type(current.phase).VIABLE
        model.step = step
        return model

    monkeypatch.setattr(module, 'TumorNanobotModel', controlled_model)
    response = client.post('/simulation/tumor/run', json=_offline_config())
    assert response.status_code == 200, response.text
    assert response.json()['tumor_statistics']['initial_hypoxic'] == 1
    assert response.json()['tumor_statistics']['final_hypoxic'] == 0


def test_minimal_api_row_is_not_a_tumor_snapshot(api):
    module, client = api
    module.TUMOR_RUN_STORE.run_store.save_run('minimal-only', 'completed', {}, {})
    response = client.get('/simulation/tumor/runs/minimal-only')
    assert response.status_code == 404
    assert module.TUMOR_RUN_STORE.run_store.get_run('minimal-only') is not None


def test_failed_persistence_does_not_publish_a_cached_run(api, monkeypatch):
    module, client = api
    before = set(module._TUMOR_RUNS)
    def fail_save(**kwargs):
        raise OSError('test-only storage failure')
    monkeypatch.setattr(module.TUMOR_RUN_STORE, 'save', fail_save)
    response = client.post('/simulation/tumor/run', json=_offline_config())
    assert response.status_code == 500
    assert set(module._TUMOR_RUNS) == before


def test_comparison_executes_requested_seed_and_real_off_condition(api, monkeypatch):
    module, client = api
    real_model = module.TumorNanobotModel
    built = []
    def record_model(**kwargs):
        model = real_model(**kwargs)
        built.append((kwargs, model, [cell.to_dict() for cell in model.geometry.tumor_cells]))
        return model
    monkeypatch.setattr(module, 'TumorNanobotModel', record_model)
    response = client.post('/simulation/tumor/compare', json=_offline_config(seed=23, comparison_steps=2, cell_density=0.002, vessel_density=0.03))
    assert response.status_code == 200, response.text
    assert [kwargs.get('seed') for kwargs, _, _ in built] == [23, 23]
    assert [model.pheromones_enabled for _, model, _ in built] == [True, False]
    assert built[0][2] == built[1][2]
    assert all(kwargs.get('cell_density') == 0.002 and kwargs.get('vessel_density') == 0.03 for kwargs, _, _ in built)
    assert 'trail_pheromone' not in built[1][1].microenv.substrates


@pytest.mark.parametrize('endpoint', ['performance', 'compare', 'compare-ced'])
@pytest.mark.parametrize('overrides,expected', [({'offline': True, 'agent_type': 'LLM-Powered'}, 409), ({'use_brats_geometry': True}, 422)])
def test_all_tumor_research_routes_share_execution_guards(api, monkeypatch, endpoint, overrides, expected):
    module, client = api
    def forbidden_model(**kwargs):
        raise AssertionError('rejected request must not construct model')
    monkeypatch.setattr(module, 'TumorNanobotModel', forbidden_model)
    response = client.post('/simulation/tumor/' + endpoint, json=_offline_config(**overrides))
    assert response.status_code == expected, response.text


def test_performance_honors_requested_seed_and_density(api, monkeypatch):
    module, client = api
    real_model = module.TumorNanobotModel
    calls = []
    def record_model(**kwargs):
        calls.append(kwargs)
        return real_model(**kwargs)
    monkeypatch.setattr(module, 'TumorNanobotModel', record_model)
    response = client.post('/simulation/tumor/performance', json=_offline_config(seed=23, cell_density=0.002))
    assert response.status_code == 200, response.text
    assert calls[0].get('seed') == 23
    assert calls[0].get('cell_density') == 0.002


def test_comparison_resolves_a_shared_seed_and_rejects_ignored_policy(api):
    _, client = api
    no_seed = client.post('/simulation/tumor/compare', json=_offline_config(seed=None, comparison_steps=1))
    assert no_seed.status_code == 200
    assert no_seed.json()['config']['seed'] == 0


def test_comparison_rejects_ignored_queen_policy(api):
    _, client = api
    ignored_queen = client.post('/simulation/tumor/compare', json=_offline_config(use_queen=True, comparison_steps=1))
    assert ignored_queen.status_code == 422


def test_health_endpoint_remains_available(api):
    _, client = api
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_fresh_process_can_post_and_retrieve_an_offline_run(tmp_path: Path):
    db_path = tmp_path / "fresh-process.sqlite3"
    code = """
import json
from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app)
payload = {
    "domain_size": 100.0,
    "voxel_size": 20.0,
    "n_nanobots": 2,
    "tumor_radius": 30.0,
    "agent_type": "Rule-Based",
    "use_queen": False,
    "use_llm_queen": False,
    "max_steps": 1,
    "seed": 9,
}
created = client.post("/simulation/tumor/run", json=payload)
retrieved = client.get("/simulation/tumor/runs/" + created.json()["run_id"])
print(json.dumps({"post": created.json(), "get": retrieved.json(), "status": [created.status_code, retrieved.status_code]}))
"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "PYTHON_DOTENV_DISABLED": "1",
            "ANTELLIGENCE_OFFLINE": "1",
            "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
            "CHAIN_READ_ENABLED": "0",
            "CHAIN_WRITE_ENABLED": "0",
            "ANTELLIGENCE_RUN_DB": str(db_path),
            "ANTELLIGENCE_CACHE_DIR": str(tmp_path / "cache"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("{"))
    payload = json.loads(line)
    assert payload["status"] == [200, 200]
    assert payload["get"]["run_id"] == payload["post"]["run_id"]
    assert payload["get"]["config_hash"] == payload["post"]["config_hash"]
    assert payload["get"]["proof_ok"] is False
