"""Unit tests for submission CLI."""

import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.submit import (
    TUMOR_INTEL_ADDRESS,
    create_attestation_bundle,
    encode_public_values,
    submit_via_cast,
)


class TestAttestationBundle:
    def test_create_bundle(self):
        config = {"tumor_radius": 150, "nanobot_count": 10, "steps": 300}
        metrics = {"kill_rate": 45.5, "deliveries": 30}
        bundle = create_attestation_bundle(config, metrics)

        assert bundle["ok"] is True
        assert bundle["onchain"]["contract"] == TUMOR_INTEL_ADDRESS
        assert bundle["onchain"]["chain_id"] == 84532
        assert bundle["onchain"]["kill_rate_bps"] == 4550
        assert bundle["onchain"]["nanobot_count"] == 10
        assert bundle["onchain"]["tumor_radius"] == 150
        assert bundle["onchain"]["steps"] == 300
        assert len(bundle["onchain"]["config_hash"]) == 64

    def test_bundle_has_ipfs(self):
        bundle = create_attestation_bundle(
            config={"x": 1},
            metrics={"kill_rate": 10.0},
        )
        assert "ipfs" in bundle
        assert "artifact_hash" in bundle["ipfs"]

    def test_bundle_status(self):
        bundle = create_attestation_bundle(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 30.0},
        )
        assert bundle["status"] == "ready_for_submission"
        assert bundle["proof_lifecycle"]["stage"] == "bundle_created"
        assert bundle["proof_lifecycle"]["proof_system"] == "sp1+groth16"
        assert bundle["verification_status"]["integrity_ok"] is True
        assert "verifySimulation" in bundle["next_step"]
        # New requirement: non-production trust tier must be recorded
        assert "trust_tier" in bundle["proof_lifecycle"]
        # This assertion will fail if trust_tier is not present or wrong
        assert bundle["proof_lifecycle"]["trust_tier"] == "non-production"

    def test_bundle_contains_public_values(self):
        bundle = create_attestation_bundle(
            config={"tumor_radius": 100, "nanobot_count": 4, "steps": 20},
            metrics={"kill_rate": 12.0},
        )
        assert bundle["onchain"]["public_values"].startswith("0x")
        assert len(bundle["onchain"]["public_values"]) > 10
        assert bundle["onchain"]["public_values_schema_version"] == "public-values-v1"
        assert bundle["onchain"]["public_values_metadata"]["program_version"] == "tumor-intel-proof-v1"

    def test_bundle_onchain_metadata_preserves_simulation_commitments(self):
        bundle = create_attestation_bundle(
            config={"tumor_radius": 100, "nanobot_count": 4, "steps": 20},
            metrics={"kill_rate": 12.0, "deliveries": 7},
            run_id="commitment-contract",
        )

        artifact = bundle["ipfs"]["artifact"]
        commitments = bundle["onchain"]["simulation_commitments"]
        assert commitments == {
            "config_hash": artifact["config_hash"],
            "metrics_hash": artifact["metrics_hash"],
            "artifact_hash": artifact["artifact_hash"],
        }
        assert bundle["onchain"]["config_hash"] == commitments["config_hash"]
        assert bundle["onchain"]["public_values_payload"]["config_hash"] == commitments["config_hash"]

    def test_encode_public_values(self):
        encoded = encode_public_values("00" * 32, 1234, 5, 150, 40)
        assert encoded.startswith("0x")

    @patch("chain.submit.subprocess.run")
    def test_submit_via_cast_preserves_existing_0x_prefix(self, mock_run):
        mock_run.return_value.stdout = "21000\n"
        result = submit_via_cast(
            config_hash="0x" + ("ab" * 32),
            kill_rate=1234,
            nanobot_count=5,
            tumor_radius=150,
            steps=40,
            rpc_url="http://rpc.test",
            private_key="0xprivate",
            dry_run=True,
        )

        assert result["ok"] is True
        cast_args = mock_run.call_args.args[0]
        assert cast_args[4] == "0x" + ("ab" * 32)

    @patch("chain.submit.subprocess.run")
    def test_submit_via_cast_updates_lifecycle(self, mock_run):
        mock_run.return_value.stdout = '{"tx_hash": "0x123"}'
        result = submit_via_cast(
            config_hash="0x" + ("ab" * 32),
            kill_rate=1234,
            nanobot_count=5,
            tumor_radius=150,
            steps=40,
            rpc_url="http://rpc.test",
            private_key="0xprivate",
            dry_run=False,
        )
        assert result["ok"] is True
        assert result["proof_lifecycle"]["stage"] == "submitted_onchain"
        assert "trust_tier" in result["proof_lifecycle"]
        assert result["proof_lifecycle"]["trust_tier"] in ["production", "non-production"]
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["cast", "send"],
            stderr="proof transition failed",
        )

        result = submit_via_cast(
            config_hash="0x" + ("cd" * 32),
            kill_rate=1234,
            nanobot_count=5,
            tumor_radius=150,
            steps=40,
            rpc_url="http://rpc.test",
            private_key="0xprivate",
            dry_run=False,
        )

        assert result["ok"] is False
        assert result["error"].startswith("Live submission failed:")
        assert "tx" not in result
        assert result["proof_lifecycle"] == {
            "stage": "bundle_created",
            "proof_system": "sp1+groth16",
            "is_final": False,
            "note": "Bundle created locally but on-chain submission failed.",
            "trust_tier": "non-production",
        }
        assert result["proof_lifecycle"]["stage"] != "submitted_onchain"
