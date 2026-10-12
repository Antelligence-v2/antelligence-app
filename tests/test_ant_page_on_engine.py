"""The original ant page's endpoints now run on the engine ant_colony world, same shapes."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antelligence.providers import FakeProvider, litellm

# The old page's default request (frontend/src/pages/Index.tsx).
PAGE_CONFIG = {
    "grid_width": 15, "grid_height": 10, "n_food": 15, "n_ants": 10, "agent_type": "Rule-Based",
    "selected_model": "meta-llama/Llama-3.3-70B-Instruct", "prompt_style": "Adaptive", "use_queen": True,
    "use_llm_queen": False, "max_steps": 50, "pheromone_decay_rate": 0.05, "trail_deposit": 1.0,
    "alarm_deposit": 2.0, "recruitment_deposit": 1.5, "max_pheromone_value": 10.0, "enable_predators": False,
    "n_predators": 2, "predator_type": "LLM-Powered", "fear_deposit": 3.0,
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTELLIGENCE_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("ANTELLIGENCE_ENGINE_DATA", str(tmp_path / "engine"))
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX", "0")
    monkeypatch.setenv("CHAIN_READ_ENABLED", "0")
    monkeypatch.setenv("CHAIN_WRITE_ENABLED", "0")
    monkeypatch.delenv("IO_SECRET_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setattr(litellm, "_env_loaded", True)
    sys.modules.pop("backend.main", None)
    module = importlib.import_module("backend.main")
    return module, TestClient(module.app)


def test_page_request_runs_on_the_engine_with_the_old_response_shape(client):
    module, http = client
    response = http.post("/simulation/run", json=PAGE_CONFIG)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_steps_run"] == len(body["history"]) > 0
    step = body["history"][0]
    assert {"step", "ants", "predators", "food_positions", "metrics", "queen_report", "nest_position"} <= set(step)
    assert step["ants"][-1]["id"] == "queen" and step["ants"][-1]["is_queen"] is True
    assert step["nest_position"] == [7, 5]
    assert len(body["final_pheromone_data"]["trail"]) == 10 and len(body["final_pheromone_data"]["trail"][0]) == 15
    assert body["history"][0]["pheromone_data"] is not None
    assert body["final_metrics"]["food_collected"] == 15 - len(body["history"][-1]["food_positions"])
    assert "Engine run ant_colony-queen-42-" in body["blockchain_logs"][0]
    run_id = body["blockchain_logs"][0].split()[2]
    stored = http.get(f"/engine/runs/{run_id}")
    assert stored.status_code == 200 and stored.json()["spec"]["params"]["n_food"] == 15


def test_predators_and_queen_report_come_through(client):
    _, http = client
    body = http.post("/simulation/run", json={**PAGE_CONFIG, "enable_predators": True, "predator_type": "Rule-Based",
                                              "max_steps": 30}).json()
    assert len(body["history"][0]["predators"]) == 2
    assert body["history"][0]["predators"][0]["id"] == 1000
    assert "Queen heuristic guidance" in body["history"][-1]["queen_report"]


def test_llm_ants_without_a_key_get_a_clear_503(client):
    _, http = client
    response = http.post("/simulation/run", json={**PAGE_CONFIG, "agent_type": "LLM-Powered"})
    assert response.status_code == 503 and "IO_SECRET_KEY" in response.json()["detail"]


def test_llm_ants_count_api_calls_and_report_failures(client, monkeypatch):
    _, http = client
    monkeypatch.setenv("IO_SECRET_KEY", "k")
    monkeypatch.setattr(litellm, "OpenAICompatProvider", lambda *a, **k: FakeProvider(lambda request: "toward"))
    body = http.post("/simulation/run", json={**PAGE_CONFIG, "agent_type": "LLM-Powered", "use_queen": False}).json()
    assert body["final_metrics"]["total_api_calls"] > 0
    assert body["final_metrics"]["food_collected_by_llm"] == body["final_metrics"]["food_collected"]


def test_queen_comparison_runs_both_arms(client):
    _, http = client
    body = http.post("/simulation/compare", json={**PAGE_CONFIG, "comparison_steps": 40}).json()
    assert body["food_collected_with_queen"] > 0 and body["food_collected_no_queen"] > 0
