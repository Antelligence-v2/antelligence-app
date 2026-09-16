"""Canonical proof/public-values specification for Antelligence.

This module locks the v1 proof boundary so the backend, stored artifacts,
replay verifier, prover, and on-chain contract all speak the same language.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from eth_abi import decode, encode

PROOF_ARTIFACT_VERSION = "proof-bundle-v1"
PUBLIC_VALUES_SCHEMA_VERSION = "public-values-v1"
PROGRAM_VERSION = "tumor-intel-proof-v1"
PROOF_SYSTEM = "sp1+groth16"
PROOF_FORMAT = "groth16"
PROOF_BOUNDARY_VERSION = "sp1-groth16-adapter-v2"
PROOF_ORIGIN_MOCK = "mock"
PROOF_ORIGIN_ADAPTER = "sp1-groth16-adapter"
PROOF_STATUS_MOCK = "mock-generated"
PROOF_STATUS_ADAPTER = "adapter-boundary"
PUBLIC_VALUES_ABI_TYPES: Tuple[str, ...] = ("bytes32", "uint32", "uint32", "uint32", "uint32")

PUBLIC_VALUES_FIELDS = (
    "config_hash",
    "kill_rate_bps",
    "nanobot_count",
    "tumor_radius",
    "steps",
)

TRANSPORT_METADATA_REQUIRED_KEYS = (
    "artifact_version",
    "proof_system",
    "proof_format",
    "proof_origin",
    "prover_status",
    "is_mock",
    "program_version",
    "public_values_schema_version",
    "proof_boundary_version",
    "public_values_bytes",
    "proof_bytes_length",
    "public_values_commitment",
    "proof_bytes_commitment",
    "transport_commitment",
)


def normalize_config_hash(config_hash: str) -> str:
    normalized = config_hash[2:] if config_hash.startswith("0x") else config_hash
    if len(normalized) != 64:
        raise ValueError(f"config_hash must be 32 bytes / 64 hex chars, got {len(normalized)}")
    int(normalized, 16)
    return normalized.lower()


def build_public_values_payload(
    config_hash: str,
    kill_rate_bps: int,
    nanobot_count: int,
    tumor_radius: int,
    steps: int,
) -> Dict[str, int | str]:
    return {
        "config_hash": normalize_config_hash(config_hash),
        "kill_rate_bps": int(kill_rate_bps),
        "nanobot_count": int(nanobot_count),
        "tumor_radius": int(tumor_radius),
        "steps": int(steps),
    }


def validate_public_values_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    payload_keys = set(payload.keys())
    expected_keys = set(PUBLIC_VALUES_FIELDS)
    checks.append({
        "check": "payload_fields_exact",
        "ok": payload_keys == expected_keys,
        "expected": list(PUBLIC_VALUES_FIELDS),
        "actual": sorted(payload_keys),
    })

    try:
        normalized = normalize_config_hash(str(payload.get("config_hash", "")))
        checks.append({
            "check": "config_hash_format",
            "ok": True,
            "actual": normalized,
        })
    except Exception as exc:
        checks.append({
            "check": "config_hash_format",
            "ok": False,
            "reason": str(exc),
        })

    for field in PUBLIC_VALUES_FIELDS[1:]:
        value = payload.get(field)
        try:
            normalized = int(value)
            checks.append({
                "check": f"{field}_non_negative_int",
                "ok": normalized >= 0,
                "actual": normalized,
            })
        except Exception as exc:
            checks.append({
                "check": f"{field}_non_negative_int",
                "ok": False,
                "reason": str(exc),
                "actual": value,
            })

    return checks


def _encode_value(field: str, value: Any) -> Any:
    if field == "config_hash":
        return bytes.fromhex(normalize_config_hash(str(value)))
    return int(value)


def encode_public_values_payload(payload: Dict[str, int | str]) -> str:
    values = [_encode_value(field, payload[field]) for field in PUBLIC_VALUES_FIELDS]
    encoded = encode(PUBLIC_VALUES_ABI_TYPES, values)
    return "0x" + encoded.hex()


def decode_public_values_payload(encoded_public_values: str) -> Dict[str, int | str]:
    encoded = bytes.fromhex(encoded_public_values[2:] if encoded_public_values.startswith("0x") else encoded_public_values)
    decoded = decode(PUBLIC_VALUES_ABI_TYPES, encoded)
    return {
        "config_hash": decoded[0].hex(),
        "kill_rate_bps": int(decoded[1]),
        "nanobot_count": int(decoded[2]),
        "tumor_radius": int(decoded[3]),
        "steps": int(decoded[4]),
    }


def build_public_values_metadata() -> Dict[str, object]:
    return {
        "schema_version": PUBLIC_VALUES_SCHEMA_VERSION,
        "program_version": PROGRAM_VERSION,
        "fields": list(PUBLIC_VALUES_FIELDS),
        "abi_types": list(PUBLIC_VALUES_ABI_TYPES),
    }


def _normalize_hex_bytes(value: str, *, field_name: str) -> str:
    normalized = value[2:] if value.startswith("0x") else value
    if len(normalized) % 2 != 0:
        raise ValueError(f"{field_name} must contain an even number of hex chars")
    bytes.fromhex(normalized)
    return "0x" + normalized.lower()


def compute_transport_commitment(*values: str) -> str:
    payload = "|".join(values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_proof_transport_metadata(*, public_values: str, proof_bytes: str, proof_origin: str, prover_status: str, is_mock: bool) -> Dict[str, object]:
    normalized_public_values = _normalize_hex_bytes(public_values, field_name="public_values")
    normalized_proof_bytes = _normalize_hex_bytes(proof_bytes, field_name="proof_bytes")
    public_values_raw = bytes.fromhex(normalized_public_values[2:])
    proof_bytes_raw = bytes.fromhex(normalized_proof_bytes[2:])
    metadata = {
        "artifact_version": PROOF_ARTIFACT_VERSION,
        "proof_system": PROOF_SYSTEM,
        "proof_format": PROOF_FORMAT,
        "proof_origin": proof_origin,
        "prover_status": prover_status,
        "is_mock": is_mock,
        "program_version": PROGRAM_VERSION,
        "public_values_schema_version": PUBLIC_VALUES_SCHEMA_VERSION,
        "proof_boundary_version": PROOF_BOUNDARY_VERSION,
        "public_values_bytes": len(public_values_raw),
        "proof_bytes_length": len(proof_bytes_raw),
        "public_values_commitment": hashlib.sha256(public_values_raw).hexdigest(),
        "proof_bytes_commitment": hashlib.sha256(proof_bytes_raw).hexdigest(),
        "transport_commitment": compute_transport_commitment(
            normalized_public_values,
            normalized_proof_bytes,
            proof_origin,
            prover_status,
            PROGRAM_VERSION,
            PUBLIC_VALUES_SCHEMA_VERSION,
        ),
    }
    if tuple(metadata) != TRANSPORT_METADATA_REQUIRED_KEYS:
        raise ValueError("transport metadata keys drifted from the proof-spec contract")
    return metadata


def build_proof_artifact_metadata(*, proof_origin: str, is_mock: bool) -> Dict[str, object]:
    return {
        "artifact_version": PROOF_ARTIFACT_VERSION,
        "proof_system": PROOF_SYSTEM,
        "proof_format": PROOF_FORMAT,
        "proof_origin": proof_origin,
        "is_mock": is_mock,
        "program_version": PROGRAM_VERSION,
        "public_values_schema_version": PUBLIC_VALUES_SCHEMA_VERSION,
        "proof_boundary_version": PROOF_BOUNDARY_VERSION,
    }
