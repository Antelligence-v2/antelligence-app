"""Regression guard for proof transport metadata."""

import hashlib

from backend.chain.proof_spec import (
    PROOF_BOUNDARY_VERSION,
    TRANSPORT_METADATA_REQUIRED_KEYS,
    build_proof_transport_metadata,
    build_public_values_payload,
    encode_public_values_payload,
)


def test_build_proof_transport_metadata_matches_required_key_contract():
    metadata = build_proof_transport_metadata(
        public_values="0x" + ("12" * 32),
        proof_bytes="0x" + ("34" * 48),
        proof_origin="mock",
        prover_status="mock-generated",
        is_mock=True,
    )

    assert set(metadata) == set(TRANSPORT_METADATA_REQUIRED_KEYS)
    assert list(metadata) == list(TRANSPORT_METADATA_REQUIRED_KEYS)


def test_transport_metadata_commitments_are_stable_and_bound_to_config_hash():
    payload = build_public_values_payload(
        config_hash="ab" * 32,
        kill_rate_bps=1200,
        nanobot_count=4,
        tumor_radius=100,
        steps=20,
    )
    public_values = encode_public_values_payload(payload)
    proof_bytes = "0x" + ("34" * 48)

    metadata = build_proof_transport_metadata(
        public_values=public_values,
        proof_bytes=proof_bytes,
        proof_origin="mock",
        prover_status="mock-generated",
        is_mock=True,
    )

    changed_config_values = encode_public_values_payload({**payload, "config_hash": "cd" * 32})
    changed_config_metadata = build_proof_transport_metadata(
        public_values=changed_config_values,
        proof_bytes=proof_bytes,
        proof_origin="mock",
        prover_status="mock-generated",
        is_mock=True,
    )

    assert changed_config_metadata["transport_commitment"] != metadata["transport_commitment"]
    assert metadata["public_values_commitment"] == hashlib.sha256(bytes.fromhex(public_values[2:])).hexdigest()
    assert metadata["proof_bytes_commitment"] == hashlib.sha256(bytes.fromhex(proof_bytes[2:])).hexdigest()
    assert changed_config_metadata["public_values_commitment"] != metadata["public_values_commitment"]


def test_shared_memory_result_matches_proof_commitment():
    payload = build_public_values_payload(
        config_hash="ab" * 32,
        kill_rate_bps=1200,
        nanobot_count=4,
        tumor_radius=100,
        steps=20,
    )
    public_values = encode_public_values_payload(payload)
    proof_bytes = "0x" + ("34" * 48)

    metadata = build_proof_transport_metadata(
        public_values=public_values,
        proof_bytes=proof_bytes,
        proof_origin="mock",
        prover_status="mock-generated",
        is_mock=True,
    )

    changed_payload = build_public_values_payload(
        config_hash="cd" * 32,
        kill_rate_bps=1200,
        nanobot_count=4,
        tumor_radius=100,
        steps=20,
    )
    changed_public_values = encode_public_values_payload(changed_payload)

    changed_metadata = build_proof_transport_metadata(
        public_values=changed_public_values,
        proof_bytes=proof_bytes,
        proof_origin="mock",
        prover_status="mock-generated",
        is_mock=True,
    )

    assert metadata["transport_commitment"] != changed_metadata["transport_commitment"], \
        "Transport commitment must change when public values change"

    assert changed_metadata["transport_commitment"] != build_proof_transport_metadata(
        public_values=public_values,
        proof_bytes=proof_bytes,
        proof_origin="different-origin",
        prover_status="mode-generated",
        is_mock=
        True,
    )["transport_commitment"], "Transport commitment must change if origin/protocol context changes"

    # RED STEP: Verify that the transport commitment is sensitive to the
    # public_values_schema_version. This assertion will fail.
    from backend.chain.proof_spec import _normalize_hex_bytes
    
    norm_pv = _normalize_hex_bytes(public_values, field_name="public_values")
    norm_pb = _normalize_hex_bytes(proof_bytes, field_name="proof_bytes")
    origin = "mock"
    status = "mock-generated"
    prog_ver = "tumor-intel-proof-v1"
    schema_ver = metadata["public_values_schema_version"]
    
    assert PROOF_BOUNDARY_VERSION == "sp1-groth16-adapter-v2"
    assert metadata["proof_boundary_version"] == PROOF_BOUNDARY_VERSION
    correct_commitment_with_schema = hashlib.sha256(
        f"{norm_pv}|{norm_pb}|{origin}|{status}|{prog_ver}|{schema_ver}".encode("utf-8")
    ).hexdigest()
    
    assert metadata["transport_commitment"] == correct_commitment_with_schema, \
        "Transport commitment must be sensitive to the public_values_schema_version"
