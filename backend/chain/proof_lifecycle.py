"""Proof lifecycle helpers for Antelligence attestations."""

from __future__ import annotations

from typing import Any, Dict


PROOF_STAGES = [
    "bundle_created",
    "proof_pending",
    "proof_generated",
    "submitted_onchain",
    "verified_onchain",
]


def build_lifecycle(stage: str, *, note: str = "", proof_system: str = "sp1+groth16", trust_tier: str = "non-production") -> Dict[str, Any]:
    if stage not in PROOF_STAGES:
        raise ValueError(f"Unknown proof lifecycle stage: {stage}")
    return {
        "stage": stage,
        "proof_system": proof_system,
        "is_final": stage == "verified_onchain",
        "note": note,
        "trust_tier": trust_tier,
    }


def build_verification_status(
    *,
    schema_ok: bool = True,
    integrity_ok: bool = False,
    replay_ok: bool = False,
    proof_ok: bool = False,
    onchain_ok: bool = False,
) -> Dict[str, bool]:
    return {
        "schema_ok": schema_ok,
        "integrity_ok": integrity_ok,
        "replay_ok": replay_ok,
        "proof_ok": proof_ok,
        "onchain_ok": onchain_ok,
    }
