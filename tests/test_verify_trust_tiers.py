"""Unit tests for trust tier logic in verification."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact
from chain.verify import verify_artifact

def test_verify_artifact_trust_tier_for_mock():
    """Verify that artifacts marked as is_mock have the correct trust tier prefix."""
    artifact = create_simulation_artifact(
        config={"tumor_radius": 150, "nanobot_count": 10},
        metrics={"kill_rate": 45.5, "deliveries": 30},
    )
    artifact["is_mock"] = True
    
    # We use replay=False to isolate trust tier logic from replay/onchain logic
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    
    assert "mock_" in result["trust_tier"]
    assert result["trust_metadata"]["is_mock"] is True

def test_verify_artifact_trust_tier_for_replay_checked():
    """Verify that artifacts with replay_ok but no proof are 'replay_checked'."""
    artifact = create_simulation_artifact(
        config={"tumor_radius": 150, "nanobot_count": 10},
        metrics={"kill_rate": 45.5, "deliveries": 30},
    )
    # Manually inject a verification status that looks like replay was checked
    artifact["verification_status"] = {"replay_ok": True}
    
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    
    assert result["trust_tier"] == "replay_checked"

def test_verify_artifact_trust_tier_for_integrity_checked():
    """Verify that artifacts with integrity_ok but no replay/proof are 'integrity_checked'."""
    artifact = create_simulation_artifact(
        config={"tumor_radius": 150, "nanobot_count": 10},
        metrics={"kill_rate": 45.5, "deliveries": 30},
    )
    artifact["verification_status"] = {"integrity_ok": True, "replay_ok": False}
    
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    
    assert result["trust_tier"] == "integrity_checked"


def test_verify_artifact_rejects_unknown_trust_tier_with_structured_error():
    """Verifier API must not silently default unsupported trust tiers to a permissive tier."""
    artifact = create_simulation_artifact(
        config={"tumor_radius": 150, "nanobot_count": 10},
        metrics={"kill_rate": 45.5, "deliveries": 30},
    )
    artifact["trust_tier"] = "verified_by_vibes"

    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)

    assert result["ok"] is False
    assert result["trust_tier"] == "unsupported"
    assert result["error"] == {
        "code": "unsupported_trust_tier",
        "message": "Unsupported trust tier: verified_by_vibes",
        "trust_tier": "verified_by_vibes",
        "supported_trust_tiers": [
            "integrity_checked",
            "proof_staged",
            "replay_checked",
            "unverified",
            "verified_onchain",
        ],
    }
