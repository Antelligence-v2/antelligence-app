"""Unit tests for IPFS pinning utility."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import (
    compute_artifact_hash,
    compute_config_hash,
    create_simulation_artifact,
    pin_simulation,
)


class TestArtifactHash:
    def test_deterministic(self):
        data = {"a": 1, "b": 2}
        h1 = compute_artifact_hash(data)
        h2 = compute_artifact_hash(data)
        assert h1 == h2

    def test_order_independent(self):
        h1 = compute_artifact_hash({"b": 2, "a": 1})
        h2 = compute_artifact_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_data_different_hash(self):
        h1 = compute_artifact_hash({"x": 1})
        h2 = compute_artifact_hash({"x": 2})
        assert h1 != h2

    def test_returns_hex_string(self):
        h = compute_artifact_hash({"test": True})
        assert len(h) == 64  # SHA-256 = 64 hex chars
        assert all(c in "0123456789abcdef" for c in h)


class TestConfigHash:
    def test_basic(self):
        h = compute_config_hash(
            tumor_radius=150,
            nanobot_count=10,
            steps=300,
            oxygen_level=38.0,
            drug_dosage=90.0,
            seed=42,
        )
        assert len(h) == 64

    def test_reproducible(self):
        args = dict(tumor_radius=150, nanobot_count=10, steps=300,
                    oxygen_level=38.0, drug_dosage=90.0, seed=42)
        assert compute_config_hash(**args) == compute_config_hash(**args)

    def test_different_seed_different_hash(self):
        base = dict(tumor_radius=150, nanobot_count=10, steps=300,
                    oxygen_level=38.0, drug_dosage=90.0)
        h1 = compute_config_hash(**base, seed=1)
        h2 = compute_config_hash(**base, seed=2)
        assert h1 != h2


class TestSimulationArtifact:
    def test_create_artifact(self):
        config = {"tumor_radius": 150, "nanobot_count": 10}
        metrics = {"kill_rate": 45.5, "deliveries": 30}
        artifact = create_simulation_artifact(config, metrics)

        assert artifact["version"] == "1.0"
        assert artifact["type"] == "antelligence-simulation-v2"
        assert artifact["config"] == config
        assert artifact["metrics"] == metrics
        assert "config_hash" in artifact
        assert "metrics_hash" in artifact
        assert "artifact_hash" in artifact
        assert "timestamp" in artifact

    def test_custom_run_id(self):
        artifact = create_simulation_artifact(
            config={"x": 1}, metrics={"y": 2}, run_id="test-run-001"
        )
        assert artifact["run_id"] == "test-run-001"


class TestPinSimulation:
    def test_dry_run(self):
        result = pin_simulation(
            config={"tumor_radius": 150},
            metrics={"kill_rate": 45.5},
            backend="dry-run",
        )
        assert result["ok"] is True
        assert result["backend"] == "dry-run"
        assert result["cid"] is None
        assert len(result["artifact_hash"]) == 64
        assert len(result["config_hash"]) == 64

    def test_no_backend_available(self):
        # Remove any IPFS env vars
        old_api = os.environ.pop("PINATA_API_KEY", None)
        old_secret = os.environ.pop("PINATA_SECRET_KEY", None)
        try:
            result = pin_simulation(
                config={"x": 1},
                metrics={"y": 2},
                backend="auto",
            )
            assert result["ok"] is False
            assert result["backend"] == "none"
            assert "artifact_hash" in result
        finally:
            if old_api:
                os.environ["PINATA_API_KEY"] = old_api
            if old_secret:
                os.environ["PINATA_SECRET_KEY"] = old_secret
