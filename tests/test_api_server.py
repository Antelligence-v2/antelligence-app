"""Tests for backend/api_server.py using FastAPI TestClient."""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api_server import RUN_STORE, app, _RUNS


client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_model_factory(**kwargs):
    """Return a lightweight mock TumorNanobotModel."""
    model = MagicMock()
    model.step_count = 5
    model.metrics = {
        "total_deliveries": 2,
        "total_drug_delivered": 10.0,
        "cells_killed": 1,
        "hypoxic_cells": 3,
        "viable_cells": 50,
        "neetcotic_cells": 0,
        "apoptotic_cells": 1,
        "total_api_calls": 0,
        "food_collected_by_llm": 0,
        "food_collected_by_rule": 2,
        "deliveries_by_llm": 0,
        "deliveries_by_rule": 2,
    }
    model.geometry.get_tumor_statistics.return_value = {
        "total_cells": 60,
        "living_cells": 55,
    }
    return model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestSimulateEndpoint:
    def test_simulate_returns_run_id(self):
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "completed"

    def test_simulate_returns_metrics(self):
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 3})
        data = resp.json()
        assert "metrics" in data
        assert "kill_rate" in data["metrics"]

    def test_simulate_scales_fractional_kill_rate_to_basis_points(self):
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 3})

        data = resp.json()
        assert data["metrics"]["kill_rate"] == pytest.approx(5 / 60)
        assert data["provenance"]["onchain"]["kill_rate_bps"] == int((5 / 60) * 10_000)
        assert data["provenance"]["onchain"]["public_values_payload"]["kill_rate_bps"] == int(
            (5 / 60) * 10_000
        )

    def test_pheromone_request_rejects_unknown_field(self):
        """
        GREEN STEP: This test proves the server rejects an unknown field.
        """
        resp = client.post(
            "/simulate",
            json={
                "num_bots": 2,
                "rel_dead_field": True,  # This is the unknown field
                "grid_size": 5,
                "steps": 3,
                "pheromone_params": {"trail_decay": 0.1}
            },
        )
        # We expect 422 because the SimulateRequest model uses ConfigDict(extra="forbid")
        assert resp.status_code == 422

    def test_simulate_config_trace_names_stored_run_and_proof_input_hashes(self):
        payload = {"num_bots": 3, "grid_size": 7, "steps": 4, "queen_enabled": True, "seed": 321}
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        trace = data["provenance"]["config_trace"]
        expected_stored_hash = hashlib.sha256(
            json.dumps(data["provenance"]["config"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        assert trace["stored_run_id"] == data["run_id"]
        assert trace["proof_bundle_run_id"] == data["run_id"]
        assert trace["stored_config_hash"] == expected_stored_hash
        assert trace["proof_input_config_hash"] == data["provenance"]["proof_bundle"]["config_hash"]
        assert trace["stored_matches_proof_input"] is False

        _RUNS.pop(data["run_id"])
        persisted = client.get(f"/runs/{data['run_id']}").json()
        assert persisted["provenance"]["config_trace"] == trace

    def test_simulate_config_trace_declares_machine_readable_config_sources(self):
        payload = {"num_bots": 3, "grid_size": 7, "steps": 4, "queen_enabled": True, "seed": 321}
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        trace = data["provenance"]["config_trace"]

        assert trace["schema_version"] == "config-trace-v1"
        assert trace["config_sources"] == {
            "request": {
                "kind": "api_request_config",
                "path": "provenance.config",
                "hash": trace["request_config_hash"],
            },
            "stored_run": {
                "kind": "persisted_run_record",
                "path": f"runs/{data['run_id']}.config",
                "run_id": data["run_id"],
                "hash": trace["stored_config_hash"],
            },
            "proof_input": {
                "kind": "proof_bundle_input",
                "path": "provenance.proof_bundle.config_hash",
                "run_id": data["run_id"],
                "hash": trace["proof_input_config_hash"],
            },
            "onchain_commitment": {
                "kind": "onchain_commitment",
                "path": "provenance.onchain.simulation_commitments.config_hash",
                "hash": trace["onchain_config_hash"],
            },
        }

    def test_simulate_config_trace_source_kinds_are_machine_readable(self):
        payload = {"num_bots": 3, "grid_size": 7, "steps": 4, "queen_enabled": True, "seed": 321}
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json=payload)

        assert resp.status_code == 200
        sources = resp.json()["provenance"]["config_trace"]["config_sources"]

        assert sources["request"]["kind"] == "api_request_config"
        assert sources["stored_run"]["kind"] == "persisted_run_record"
        assert sources["proof_input"]["kind"] == "proof_bundle_input"
        assert sources["onchain_commitment"]["kind"] == "onchain_commitment"

    def test_simulate_config_trace_declares_machine_readable_trace_edges(self):
        payload = {"num_bots": 3, "grid_size": 7, "steps": 4, "queen_enabled": True, "seed": 321}
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json=payload)

        assert resp.status_code == 200
        trace = resp.json()["provenance"]["config_trace"]

        assert trace["trace_edges"] == [
            {
                "from": "request",
                "to": "stored_run",
                "relationship": "persisted_as",
                "match": True,
                "from_hash": trace["request_config_hash"],
                "to_hash": trace["stored_config_hash"],
            },
            {
                "from": "stored_run",
                "to": "proof_input",
                "relationship": "normalized_for_proof",
                "match": False,
                "from_hash": trace["stored_config_hash"],
                "to_hash": trace["proof_input_config_hash"],
            },
            {
                "from": "proof_input",
                "to": "onchain_commitment",
                "relationship": "committed_as",
                "match": True,
                "from_hash": trace["proof_config_hash"],
                "to_hash": trace["onchain_config_hash"],
            },
        ]

    def test_simulate_with_seed(self):
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})
        assert resp.status_code == 200


class TestGetRunEndpoint:
    def test_get_run_not_found(self):
        resp = client.get("/runs/nonexistent-run-id")
        assert resp.status_code == 404
        assert resp.json()["detail"] == {
            "type": "run_not_found",
            "run_id": "nonexistent-run-id",
            "message": "Run 'nonexistent-run-id' not found.",
        }

    def test_get_run_returns_stored_result(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2})
        run_id = post_resp.json()["run_id"]
        get_resp = client.get(f"/runs/{run_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["run_id"] == run_id
        assert data["status"] == "completed"
        assert "config" in data
        assert "metrics" in data

    def test_legacy_run_without_provenance_remains_retrievable_but_untrusted(self):
        run_id = "legacy-run-without-provenance"
        RUN_STORE.save_run(
            run_id,
            "completed",
            {"num_bots": 2, "grid_size": 5, "steps": 2},
            {"kill_rate": 0.5},
            provenance=None,
        )
        _RUNS.pop(run_id, None)

        get_resp = client.get(f"/runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["provenance"] is None

        trace_resp = client.get(f"/runs/{run_id}/config-trace")
        assert trace_resp.status_code == 404
        assert trace_resp.json()["detail"]["type"] == "config_trace_not_found"

    def test_persisted_run_provenance_matches_simulate_contract(self):
        required_fields = {
            "run_id",
            "config",
            "config_hash",
            "trust_tier",
            "verification_status",
            "proof_lifecycle",
            "onchain",
            "proof_bundle",
        }
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post(
                "/simulate",
                json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42},
            )

        post_data = post_resp.json()
        run_id = post_data["run_id"]
        _RUNS.pop(run_id)
        get_resp = client.get(f"/runs/{run_id}")

        assert get_resp.status_code == 200
        persisted_provenance = get_resp.json()["provenance"]
        assert required_fields <= persisted_provenance.keys()
        assert {
            field: persisted_provenance[field] for field in required_fields
        } == {
            field: post_data["provenance"][field] for field in required_fields
        }

        malformed = RUN_STORE.get_run(run_id)
        assert malformed is not None
        malformed["provenance"].pop("verification_status")
        RUN_STORE.save_run(
            run_id,
            malformed["status"],
            malformed["config"],
            malformed["metrics"],
            malformed["provenance"],
        )
        _RUNS.pop(run_id)

        malformed_resp = client.get(f"/runs/{run_id}")
        assert malformed_resp.status_code == 500
        assert malformed_resp.json()["detail"] == {
            "type": "invalid_run_provenance",
            "run_id": run_id,
            "missing_fields": ["verification_status"],
            "message": "Persisted run provenance is incomplete.",
        }

    def test_get_run_config_trace_reads_persisted_trace_edges(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        expected_trace = post_resp.json()["provenance"]["config_trace"]
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["run_id"] == run_id
        assert trace_resp.json()["config_trace"] == expected_trace

    def test_get_run_config_trace_validates_persisted_source_path_and_hash(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["source_validation"]["stored_run"] == {
            "kind": "persisted_run_record",
            "kind_matches_source": True,
            "path": f"runs/{run_id}.config",
            "path_matches_run": True,
            "hash_matches_stored_config": True,
        }

    def test_get_run_config_trace_validates_request_source(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        expected_hash = post_resp.json()["provenance"]["request_config_hash"]
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["source_validation"]["request"] == {
            "kind": "api_request_config",
            "kind_matches_source": True,
            "path": "provenance.config",
            "path_matches_config": True,
            "config_matches_stored_run": True,
            "hash_matches_config": True,
            "hash": expected_hash,
        }
        assert trace_resp.json()["source_validation"]["all_sources_valid"] is True

    def test_get_run_config_trace_rejects_tampered_persisted_request_source_hash(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["config_sources"]["request"]["hash"] = "tampered"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["source_validation"]["request"]["hash_matches_config"] is False
        assert trace_resp.json()["source_validation"]["all_sources_valid"] is False

    def test_get_run_config_trace_names_tampered_provenance_config_source(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config"]["steps"] = 999
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["request"]["config_matches_stored_run"] is False
        assert validation["invalid_sources"] == ["request"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_names_tampered_proof_input_source(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["config_sources"]["proof_input"]["run_id"] = "tampered"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["proof_input"]["run_id_matches_run"] is False
        assert validation["invalid_sources"] == ["proof_input"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_names_tampered_source_kind(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["config_sources"]["stored_run"]["kind"] = "api_request_config"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["stored_run"]["kind"] == "api_request_config"
        assert validation["stored_run"]["kind_matches_source"] is False
        assert validation["invalid_sources"] == ["stored_run"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_names_tampered_trace_summary(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["stored_run_id"] = "tampered"
        persisted["provenance"]["config_trace"]["onchain_config_hash"] = "tampered"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["trace_summary"]["stored_run_id_matches_run"] is False
        assert validation["trace_summary"]["onchain_config_hash_matches_commitment"] is False
        assert validation["invalid_sources"] == ["trace_summary"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_rejects_tampered_schema_version(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["schema_version"] = "config-trace-v999"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["trace_summary"]["schema_version"] == "config-trace-v999"
        assert validation["trace_summary"]["schema_version_supported"] is False
        assert validation["invalid_sources"] == ["trace_summary"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_names_tampered_trace_edges(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        persisted = RUN_STORE.get_run(run_id)
        assert persisted is not None
        persisted["provenance"]["config_trace"]["trace_edges"][0]["relationship"] = "tampered"
        RUN_STORE.save_run(
            run_id,
            persisted["status"],
            persisted["config"],
            persisted["metrics"],
            persisted["provenance"],
        )
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        validation = trace_resp.json()["source_validation"]
        assert validation["trace_edges"] == {
            "edge_count": 3,
            "expected_edge_count": 3,
            "edges_match_expected": False,
        }
        assert validation["invalid_sources"] == ["trace_edges"]
        assert validation["all_sources_valid"] is False

    def test_get_run_config_trace_validates_proof_input_source(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["source_validation"]["proof_input"] == {
            "kind": "proof_bundle_input",
            "kind_matches_source": True,
            "path": "provenance.proof_bundle.config_hash",
            "path_matches_proof_bundle": True,
            "run_id": run_id,
            "run_id_matches_run": True,
            "hash_matches_proof_bundle": True,
        }

    def test_get_run_config_trace_validates_onchain_commitment_source(self):
        _RUNS.clear()
        with patch("backend.api_server.TumorNanobotModel", side_effect=_fake_model_factory):
            post_resp = client.post("/simulate", json={"num_bots": 2, "grid_size": 5, "steps": 2, "seed": 42})

        run_id = post_resp.json()["run_id"]
        expected_hash = post_resp.json()["provenance"]["proof_bundle"]["config_hash"]
        _RUNS.pop(run_id)

        trace_resp = client.get(f"/runs/{run_id}/config-trace")

        assert trace_resp.status_code == 200
        assert trace_resp.json()["source_validation"]["onchain_commitment"] == {
            "kind": "onchain_commitment",
            "kind_matches_source": True,
            "path": "provenance.onchain.simulation_commitments.config_hash",
            "path_matches_commitment": True,
            "hash": expected_hash,
            "hash_matches_proof_bundle": True,
        }
