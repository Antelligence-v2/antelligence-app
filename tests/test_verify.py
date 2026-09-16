"""Unit tests for verification CLI."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact, compute_artifact_hash
from chain.proof_adapter import create_proof_bundle
from chain.verify import (
    check_onchain_verification,
    verify_artifact,
    verify_artifact_integrity,
    verify_artifact_replay,
    verify_metrics_tolerance,
    verify_proof_bundle_schema,
    verify_public_values_schema,
)


class TestVerifyIntegrity:
    def test_valid_artifact(self):
        artifact = create_simulation_artifact(
            config={"tumor_radius": 150, "nanobots": 10},
            metrics={"kill_rate": 45.5, "deliveries": 30},
        )
        result = verify_artifact_integrity(artifact)
        assert result["ok"] is True
        assert all(c["ok"] for c in result["checks"])

    def test_tampered_config_hash(self):
        artifact = create_simulation_artifact(
            config={"tumor_radius": 150},
            metrics={"kill_rate": 45.5},
        )
        artifact["config_hash"] = "deadbeef" * 8
        result = verify_artifact_integrity(artifact)
        assert result["ok"] is False
        failed = [c for c in result["checks"] if not c["ok"]]
        assert any(c["check"] == "config_hash" for c in failed)

    def test_tampered_metrics(self):
        artifact = create_simulation_artifact(
            config={"x": 1},
            metrics={"kill_rate": 45.5},
        )
        # Tamper with metrics after creation
        artifact["metrics"]["kill_rate"] = 99.9
        result = verify_artifact_integrity(artifact)
        assert result["ok"] is False

    def test_missing_field(self):
        artifact = {"config": {}, "metrics": {}}
        result = verify_artifact_integrity(artifact)
        assert result["ok"] is False


class TestMetricsTolerance:
    def test_within_tolerance(self):
        claimed = {"kill_rate": 45.5, "deliveries": 30}
        recomputed = {"kill_rate": 44.0, "deliveries": 29}
        result = verify_metrics_tolerance(claimed, recomputed, tolerance_pct=5.0)
        assert result["ok"] is True

    def test_outside_tolerance(self):
        claimed = {"kill_rate": 45.5}
        recomputed = {"kill_rate": 20.0}
        result = verify_metrics_tolerance(claimed, recomputed, tolerance_pct=5.0)
        assert result["ok"] is False

    def test_exact_match(self):
        claimed = {"kill_rate": 45.5}
        recomputed = {"kill_rate": 45.5}
        result = verify_metrics_tolerance(claimed, recomputed)
        assert result["ok"] is True
        assert result["checks"][0]["deviation_pct"] == 0.0

    def test_empty_metrics(self):
        result = verify_metrics_tolerance({}, {})
        assert result["ok"] is True

    def test_missing_recomputed_numeric_metric_fails(self):
        result = verify_metrics_tolerance({"kill_rate": 45.5}, {})
        assert result["ok"] is False
        assert result["checks"] == [
            {
                "metric": "kill_rate",
                "claimed": 45.5,
                "recomputed": None,
                "deviation_pct": None,
                "ok": False,
                "reason": "missing_recomputed_metric",
            }
        ]


class TestReplayVerification:
    def test_replay_returns_metrics(self):
        artifact = create_simulation_artifact(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2, "seed": 7, "domain_size": 40, "voxel_size": 20},
            metrics={"kill_rate": 0.0, "deliveries": 0},
        )
        result = verify_artifact_replay(artifact, tolerance_pct=100.0)
        assert "recomputed_metrics" in result
        assert "kill_rate" in result["recomputed_metrics"]
        assert "deliveries" in result["recomputed_metrics"]

    def test_full_verification_includes_replay(self):
        from chain.submit import create_attestation_bundle
        artifact = create_attestation_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2, "seed": 7, "domain_size": 40, "voxel_size": 20},
            metrics={"kill_rate": 0.0, "deliveries": 0},
        )
        artifact = {**artifact["ipfs"]["artifact"], "onchain": artifact["onchain"]}
        result = verify_artifact(artifact, tolerance_pct=100.0, replay=True)
        assert "integrity" in result
        assert "public_values" in result
        assert "replay" in result
        assert "onchain" in result
        assert result["integrity"]["ok"] is True
        assert result["public_values"]["ok"] is True
        assert result["replay"] is not None

    def test_public_values_schema_validation(self):
        from chain.submit import create_attestation_bundle
        artifact = create_attestation_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
        )
        result = verify_public_values_schema({"config_hash": artifact["ipfs"]["artifact"]["config_hash"], "onchain": artifact["onchain"]})
        assert result["ok"] is True
        assert len(result["checks"]) >= 6

    def test_public_values_schema_rejects_artifact_config_hash_mismatch(self):
        from chain.submit import create_attestation_bundle
        artifact = create_attestation_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
        )
        result = verify_public_values_schema({"config_hash": "ff" * 32, "onchain": artifact["onchain"]})
        assert result["ok"] is False
        assert any(check["check"] == "artifact_config_hash_matches_payload" and check["ok"] is False for check in result["checks"])

    def test_public_values_schema_rejects_onchain_config_hash_mismatch(self):
        from chain.submit import create_attestation_bundle
        artifact = create_attestation_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
        )
        artifact["onchain"]["config_hash"] = "aa" * 32
        result = verify_public_values_schema({"config_hash": artifact["ipfs"]["artifact"]["config_hash"], "onchain": artifact["onchain"]})
        assert result["ok"] is False
        assert any(check["check"] == "onchain_config_hash_matches_payload" and check["ok"] is False for check in result["checks"])

    def test_proof_bundle_schema_validation(self):
        bundle = create_proof_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
            run_id="proof-verify-1",
        )
        result = verify_proof_bundle_schema(bundle)
        assert result["ok"] is True
        assert any(check["check"] == "proof_artifact_version" and check["ok"] is True for check in result["checks"])
        assert any(check["check"] == "transport_commitment" and check["ok"] is True for check in result["checks"])
        assert result["decoded_public_values"]["config_hash"] == bundle["proof_bundle"]["config_hash"]

    def test_proof_bundle_schema_rejects_transport_commitment_mismatch(self):
        bundle = create_proof_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
            run_id="proof-verify-2",
        )
        bundle["proof_bundle"]["transport_metadata"]["transport_commitment"] = "deadbeef"
        result = verify_proof_bundle_schema(bundle)
        assert result["ok"] is False
        assert any(check["check"] == "transport_commitment" and check["ok"] is False for check in result["checks"])

    def test_valid_mock_proof_bundle_with_lifecycle_promotes_to_proof_staged(self, monkeypatch):
        bundle = create_proof_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2},
            metrics={"kill_rate": 0.0, "deliveries": 0},
            run_id="proof-verify-mock",
        )
        artifact = {
            **bundle["ipfs"]["artifact"],
            "onchain": bundle["onchain"],
            "proof_bundle": bundle["proof_bundle"],
            "proof_lifecycle": bundle["proof_lifecycle"],
            "verification_status": bundle["verification_status"],
            "trust_tier": "proof_staged",
        }
        result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
        assert result["trust_tier"] == "proof_staged"
        assert result["verification_status"]["proof_ok"] is False
        # This check will fail because 'is_trusted_tier' is not implemented yet
        assert result["verification_status"]["is_trusted_tier"] is True

        bundle = create_proof_bundle(
            config={"tumor_radius": 40, "nanobot_count": 2, "steps": 2, "seed": 7, "domain_size": 40, "voxel_size": 20},
            metrics={"kill_rate": 0.0, "deliveries": 0},
            run_id="proof-verify-3",
        )
        artifact = {
            **bundle["ipfs"]["artifact"],
            "onchain": bundle["onchain"],
            "proof_bundle": bundle["proof_bundle"],
            "proof_lifecycle": bundle["proof_lifecycle"],
            "verification_status": bundle["verification_status"],
            "trust_tier": bundle["trust_tier"],
        }
        result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
        assert "proof_bundle" in result
        assert result["proof_bundle"]["ok"] is True
        assert result["verification_status"]["schema_ok"] is True
        assert result["verification_status"]["integrity_ok"] is True
        assert result["verification_status"]["proof_ok"] is False
        assert result["verification_status"]["onchain_ok"] is False
        assert result["proof_lifecycle"]["stage"] == "proof_generated"
        assert result["trust_tier"] == "proof_staged"
        assert result["verification_status"]["is_trusted_tier"] is True

    def test_verify_artifact_marks_verified_onchain_only_when_chain_accepts(self, monkeypatch):
        bundle = create_proof_bundle(
            config={"tumor_radius": 55, "nanobot_count": 3, "steps": 4},
            metrics={"kill_rate": 12.5, "deliveries": 1},
            run_id="proof-verify-4",
        )
        artifact = {
            **bundle["ipfs"]["artifact"],
            "onchain": bundle["onchain"],
            "proof_bundle": bundle["proof_bundle"],
            "proof_lifecycle": bundle["proof_lifecycle"],
            "verification_status": bundle["verification_status"],
        }

        monkeypatch.setattr("chain.verify.check_onchain_verification", lambda config_hash: {"ok": True, "verified": True, "raw": "true"})
        result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)

        assert result["proof_bundle"]["ok"] is True
        assert result["verification_status"]["proof_ok"] is True
        assert result["verification_status"]["onchain_ok"] is True
        assert result["proof_lifecycle"]["stage"] == "verified_onchain"
        assert result["trust_tier"] == "verified_onchain"

    def test_onchain_check_returns_shape(self):
        result = check_onchain_verification("00" * 32)
        assert "ok" in result