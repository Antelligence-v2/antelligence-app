"""Tests for proof adapter helpers."""

from copy import deepcopy
from pathlib import Path

from backend.chain.proof_adapter import create_proof_bundle, write_proof_bundle, ProverInterface
from backend.chain.verify import verify_proof_bundle_schema

class TestProofAdapter:
    def test_create_proof_bundle(self):
        bundle = create_proof_bundle(
            config={"tumor_radius": 120, "nanobot_count": 4, "steps": 20},
            metrics={"kill_rate": 18.5},
            run_id="run-proof-1",
        )
        proof = bundle["proof_bundle"]
        assert proof["run_id"] == "run-proof-1"
        assert proof["public_values"].startswith("0x")
        assert proof["proof_bytes"].startswith("0x")
        assert proof["proof_origin"] == "sp1-groth16-adapter"
        assert proof["proof_artifact_version"] == "proof-bundle-v1"
        assert proof["public_values_schema_version"] == "public-values-v1"
        assert proof["program_version"] == "tumor-intel-proof-v1"
        assert proof["proof_boundary_version"] == "sp1-groth16-adapter-v2"
        assert proof["adapter"]["expected_verifier_call"] == "verifyProof(bytes,bytes)"
        assert proof["adapter"]["proof_transport"] == "opaque-bytes"
        assert proof["adapter"]["cryptographic_verification"] is False
        assert proof["adapter"]["public_values_commitment"] == proof["transport_metadata"]["public_values_commitment"]
        assert proof["adapter"]["proof_bytes_commitment"] == proof["transport_metadata"]["proof_bytes_commitment"]
        assert bundle["proof_lifecycle"]["stage"] == "proof_generated"
        assert bundle["verification_status"]["proof_ok"] is False
        assert bundle["trust_tier"] == "proof_staged"
        # Guard: Ensure transport metadata contains required fields
        assert "proof_origin" in proof["transport_metadata"]
        assert "prover_status" in proof["transport_metadata"]
        assert "is_mock" in proof["transport_metadata"]

    def test_prover_interface_not_implemented(self):
        prover = ProverInterface()
        import pytest
        with pytest.raises(NotImplementedError):
            prover.generate_proof("hash1", "hash2")
        assert prover.get_status() == "idle"

    def test_public_values_roundtrip(self):
        from backend.chain.proof_spec import (
            build_public_values_payload,
            decode_public_values_payload,
            encode_public_values_payload,
        )

        config_hash = "0x" + "a" * 64
        payload = build_public_values_payload(
            config_hash=config_hash,
            kill_rate_bps=15,
            nanobot_count=10,
            tumor_radius=100,
            steps=50,
        )

        encoded = encode_public_values_payload(payload)
        decoded = decode_public_values_payload(encoded)

        actual_hex = decoded["config_hash"][2:] if decoded["config_hash"].startswith("0x") else decoded["config_hash"]
        assert actual_hex == config_hash[2:]
        assert len(actual_hex) == 64
        assert decoded["kill_rate_bps"] == 15
        assert decoded["nanobot_count"] == 10
        assert decoded["tumor_radius"] == 100
        assert decoded["steps"] == 50

    def test_public_values_edge_cases(self):
        from backend.chain.proof_spec import (
            build_public_values_payload,
            decode_public_values_payload,
            encode_public_values_payload,
        )

        config_hash = "0x" + "f" * 64
        payload = build_public_values_payload(
            config_hash=config_hash,
            kill_rate_bps=0,
            nanobot_count=0,
            tumor_radius=0,
            steps=0,
        )

        encoded = encode_public_values_payload(payload)
        decoded = decode_public_values_payload(encoded)

        actual_hex = decoded["config_hash"][2:] if decoded["config_hash"].startswith("0x") else "0x" + decoded["config_hash"]
        assert actual_hex.lower() == config_hash.lower()
        assert decoded["kill_rate_bps"] == 0
        assert decoded["nanobot_count"] == 0
        assert decoded["tumor_radius"] == 0
        assert decoded["steps"] == 0

    def test_write_proof_bundle(self, tmp_path: Path):
        bundle = create_proof_bundle(
            config={"tumor_radius": 120, "nanobot_count": 4, "steps": 20},
            metrics={"kill_rate": 18.5},
            run_id="run-proof-2",
        )
        path = write_proof_bundle(tmp_path, bundle)
        assert path.exists()
        assert path.name == "run-proof-2-proof.json"
        assert path.read_text().startswith("{")
    def test_proof_bundle_schema_guard(self):
        """
        Guard: Ensure proof bundle contains stable version, origin, transport, commitment, and trust-tier fields.
        """
        run_id = "test-guard-run"
        bundle = create_proof_bundle(
            config={"tumor_radius": 100, "nanobot_count": 5, "steps": 10},
            metrics={"kill_rate": 10.0},
            run_id=run_id,
        )
        proof = bundle["proof_bundle"]
        transport = proof["transport_metadata"]
        adapter = proof["adapter"]
        
        # 1. Check stable versions and origin in the proof itself
        assert "proof_artifact_version" in proof
        assert "proof_origin" in proof
        assert "program_version" in proof
        assert "proof_boundary_version" in proof
        
        # 2. Check transport metadata commitments and metadata
        assert "public_values_commitment" in transport
        assert "proof_bytes_commitment" in transport
        assert "transport_commitment" in transport
        assert "artifact_version" in transport
        assert "proof_system" in transport
        # Ensure transport metadata also contains the origin and status
        assert "proof_origin" in transport
        assert "prover_status" in transport
        assert "is_mock" in transport
        
        # 3. Check adapter fields
        assert "expected_verifier_call" in adapter
        assert "trust_tier" in bundle
        assert bundle["trust_tier"] == "proof_staged"

        # 4. TAMPER TEST: Verify that changing the transport metadata signature is detected
        trusted_bundle = create_proof_bundle(
            config={"tumor_radius": 125, "nanobot_count": 8, "steps": 12},
            metrics={"kill_rate": 22.0},
            run_id="trusted-proof-run",
        )
        substituted_bundle = create_proof_bundle(
            config={"tumor_radius": 130, "not_a_real_field": 9, "steps": 13},
            metrics={"kill_rate": 25.0},
            run_id="substituted-proof-run",
        )

        tampered_bundle = deepcopy(substituted_bundle)
        # Force the transport metadata to match a different bundle (corrupting the commitment)
        tampered_bundle["proof_bundle"]["transport_metadata"] = trusted_bundle["proof_bundle"]["transport_metadata"]

        result = verify_proof_bundle_schema(tampered_bundle)

        assert result["ok"] is False
        assert any(
            check["check"] == "transport_commitment" and check["ok"] is False
            for check in result["checks"]
        )

    def test_proof_bundle_schema_rejects_missing_required_field(self):
        bundle = create_proof_bundle(
            config={"tumor_radius": 100, "nanobot_count": 5, "steps": 10},
            metrics={"kill_rate": 10.0},
            run_id="missing-field-run",
        )
        del bundle["proof_bundle"]["run_id"]

        result = verify_proof_bundle_schema(bundle)

        assert result["ok"] is False
        assert any(
            check["check"] == "proof_bundle_required_fields"
            and check["ok"] is False
            and "run_id" in check["missing"]
            for check in result["checks"]
        )


