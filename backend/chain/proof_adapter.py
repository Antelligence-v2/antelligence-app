"""Proof adapter helpers for SP1+Groth16 integration.

This module defines the local artifact format and staging helpers used before the
real prover is plugged in. It keeps the proof boundary explicit so the backend,
contract calls, and future prover all agree on the same payload layout.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .proof_lifecycle import build_lifecycle, build_verification_status
from .proof_spec import (
    PROGRAM_VERSION,
    PROOF_ARTIFACT_VERSION,
    PROOF_BOUNDARY_VERSION,
    PROOF_FORMAT,
    PROOF_ORIGIN_ADAPTER,
    PROOF_STATUS_ADAPTER,
    PROOF_SYSTEM,
    PUBLIC_VALUES_SCHEMA_VERSION,
    build_proof_transport_metadata,
)
from .submit import create_attestation_bundle


@dataclass
class ProofBundle:
    run_id: str
    artifact_hash: str
    config_hash: str
    public_values: str
    proof_bytes: str
    proof_system: str = PROOF_SYSTEM
    proof_format: str = PROOF_FORMAT
    proof_origin: str = PROOF_ORIGIN_ADAPTER
    proof_artifact_version: str = PROOF_ARTIFACT_VERSION
    public_values_schema_version: str = PUBLIC_VALUES_SCHEMA_VERSION
    prover_status: str = PROOF_STATUS_ADAPTER
    is_mock: bool = True
    program_version: str = PROGRAM_VERSION
    proof_boundary_version: str = PROOF_BOUNDARY_VERSION
    trace_commitment: Optional[str] = None
    witness_commitment: Optional[str] = None
    verifier_contract: Optional[str] = None
    adapter: Optional[Dict[str, Any]] = None
    transport_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ProverInterface:
    """Interface for the future SP1/Groth16 prover backend."""
    def generate_proof(self, artifact_hash: str, config_hash: str) -> Dict[str, Any]:
        """Generates a proof for a given artifact and config."""
        raise NotImplementedError("Real prover not yet implemented.")

    def get_status(self) -> str:
        """Returns the current status of the prover."""
        return "idle"







def build_mock_proof_bytes(config_hash: str) -> str:
    """Generates a dummy hex string to represent proof bytes for testing."""
    return "0x" + (config_hash * 2)[:64]

def create_proof_bundle(config: dict, metrics: dict, run_id: Optional[str] = None) -> Dict[str, Any]:
    attestation = create_attestation_bundle(config, metrics, run_id=run_id)
    artifact = attestation["ipfs"]["artifact"]
    proof_bytes = build_mock_proof_bytes(attestation["onchain"]["config_hash"])
    proof_values = attestation["onchain"]["public_values"]
    transport_metadata = build_proof_transport_metadata(
        public_values=proof_values,
        proof_bytes=proof_bytes,
        proof_origin=PROOF_ORIGIN_ADAPTER,
        prover_status=PROOF_STATUS_ADAPTER,
        is_mock=True,
    )
    adapter_dict = {
        "boundary_version": PROOF_BOUNDARY_VERSION,
        "prover": "sp1",
        "verifier": "groth16",
        "mode": "mock",
        "status": PROOF_STATUS_ADAPTER,
        "expected_verifier_call": "verifyProof(bytes,bytes)",
        "proof_transport": "opaque-bytes",
        "cryptographic_verification": False,
        "public_values_commitment": transport_metadata["public_values_commitment"],
        "proof_bytes_commitment": transport_metadata["proof_bytes_commitment"],
        "note": "Staged adapter boundary only. proof_bytes preserves the future opaque SP1/Groth16 transport shape but is not cryptographic output yet.",
    }
    proof_bundle = ProofBundle(
        run_id=artifact["run_id"],
        artifact_hash=artifact["artifact_hash"],
        config_hash=attestation["onchain"]["config_hash"],
        public_values=proof_values,
        proof_bytes=proof_bytes,
        trace_commitment=artifact["artifact_hash"],
        witness_commitment=attestation["onchain"]["config_hash"],
        adapter=adapter_dict,
        transport_metadata=transport_metadata,
    )
    attestation["proof_bundle"] = proof_bundle.to_dict()
    attest_lifecycle = build_lifecycle(
        "proof_generated",
        note="SP1/Groth16 adapter boundary bundle generated locally for schema/transport validation only. Replace with real prover output before claiming cryptographic proof.",
    )
    attestation["proof_lifecycle"] = attest_lifecycle
    attestation["verification_status"] = build_verification_status(
        schema_ok=True,
        integrity_ok=True,
        replay_ok=attestation["verification_status"].get("replay_ok", False),
        proof_ok=False,
        onchain_ok=False,
    )
    attestation["trust_tier"] = "proof_staged"
    return attestation


def write_proof_bundle(output_dir: str | Path, proof_bundle: Dict[str, Any]) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    run_id = proof_bundle.get("proof_bundle", {}).get("run_id", proof_bundle.get("ipfs", {}).get("artifact", {}).get("run_id", "run"))
    path = output / f"{run_id}-proof.json"
    path.write_text(json.dumps(proof_bundle, indent=2))
    return path
