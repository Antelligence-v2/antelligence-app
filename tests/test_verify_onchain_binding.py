"""verify_artifact must bind an accepted on-chain proof to *this* artifact's values.

isVerified(configHash) is keyed by config hash only; any artifact can reuse a hash, and
(before the contract fix) submitSimulation() could rewrite a verified record's values. The
binding that cannot be forged is publicValuesHash = keccak256(abi.encode(proven values)).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from chain.onchain_record import public_values_hash, public_values_hash_from_encoded  # noqa: E402
from chain.proof_adapter import create_proof_bundle  # noqa: E402
from chain.verify import onchain_binding, verify_artifact  # noqa: E402

HONEST = (3000, 5, 66, 30)


def _artifact(kill_rate_pct=30.0):
    bundle = create_proof_bundle({"nanobot_count": 5, "tumor_radius": 66, "steps": 30},
                                 {"kill_rate": kill_rate_pct, "deliveries": 3}, run_id="w1-hardening")
    return {**bundle["ipfs"]["artifact"], "onchain": bundle["onchain"], "proof_bundle": bundle["proof_bundle"],
            "proof_lifecycle": bundle["proof_lifecycle"], "verification_status": bundle["verification_status"]}


def _chain_says(artifact, verified=True, pv_hash=None):
    pv_hash = pv_hash or public_values_hash_from_encoded(artifact["onchain"]["public_values"])
    return lambda config_hash: {"ok": True, "verified": verified,
                                "record": {"verified": verified, "public_values_hash": pv_hash}}


def test_artifact_whose_values_were_proven_is_verified_onchain(monkeypatch):
    artifact = _artifact()
    monkeypatch.setattr("chain.verify.check_onchain_verification", _chain_says(artifact))
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    assert result["trust_tier"] == "verified_onchain"
    assert result["onchain"]["binding"]["ok"] is True


def test_isverified_flag_alone_does_not_make_an_artifact_verified_onchain(monkeypatch):
    artifact = _artifact()
    other = public_values_hash("cd" * 32, *HONEST)
    monkeypatch.setattr("chain.verify.check_onchain_verification", _chain_says(artifact, pv_hash=other))
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    assert result["verification_status"]["onchain_ok"] is False
    assert result["trust_tier"] != "verified_onchain"


def test_forged_headline_metric_with_honest_public_values_is_rejected(monkeypatch):
    """Copying a proven artifact's public values does not let a different headline number ride along."""
    artifact = _artifact(kill_rate_pct=30.0)
    chain_says = _chain_says(artifact)  # the chain really did prove these public values (30.00%)
    artifact["metrics"] = dict(artifact["metrics"], kill_rate=99.99)  # ...but the artifact headlines 99.99%
    binding = onchain_binding(artifact, chain_says(artifact["config_hash"]))
    assert binding["ok"] is False
    assert "kill_rate" in binding["reason"]
    monkeypatch.setattr("chain.verify.check_onchain_verification", chain_says)
    result = verify_artifact(artifact, tolerance_pct=100.0, replay=False)
    assert result["trust_tier"] != "verified_onchain"


def test_artifact_without_public_values_cannot_be_verified_onchain():
    artifact = _artifact()
    artifact.pop("onchain")
    assert onchain_binding(artifact, {"ok": True, "verified": True, "record": {"verified": True}})["ok"] is False
