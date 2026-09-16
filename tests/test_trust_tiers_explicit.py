
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact
from chain.verify import verify_artifact
from chain.leaderboard import build_leaderboard, derive_trust_tier
from chain.proof_adapter import create_proof_bundle

class TestTrustTiersExplicit:
    def test_trust_tier_differentiation(self, monkeypatch):
        # 1. Mock Trust Tier
        mock_artifact = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        mock_artifact["is_mock"] = True
        # We don't need to monkeypatch verify_artifact because we control the input dict
        # But we want to ensure the logic in verify_artifact handles is_mock correctly.
        result_mock = verify_artifact(mock_artifact, replay=False)
        assert "mock_" in result_mock["trust_tier"]

        # 2. Integrity Checked (Simulated/Local)
        sim_artifact = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        sim_artifact["is_mock"] = False
        # Ensure onchain_ok is False to avoid it jumping to verified_onchain
        monkeypatch.setattr("chain.verify.check_onchain_verification", lambda x: {"ok": False})
        result_sim = verify_artifact(sim_artifact, replay=False)
        assert result_sim["trust_tier"] in ["integrity_checked", "replay_checked", "proof_staged"]
        assert "mock_" not in result_sim["trust_tier"]

        # 3. Verified On-Chain
        onchain_artifact = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        onchain_artifact["is_mock"] = False
        monkeypatch.setattr("chain.verify.check_onchain_verification", lambda x: {"ok": True, "verified": True})
        result_onchain = verify_artifact(onchain_artifact, replay=False)
        assert result_onchain["trust_tier"] == "verified_onchain"

    def test_leaderboard_trust_tier_mapping(self):
        # Test that build_leaderboard correctly propagates the trust tiers
        # using the derive_trust_tier logic.
        
        # Case: On-chain
        v_status = {"onchain_ok": True}
        p_bundle = {}
        p_lifecycle = {}
        assert derive_trust_tier(v_status, p_bundle, p_lifecycle) == "verified_onchain"

        # Case: Proof Staged
        v_status = {"onchain_ok": False}
        p_bundle = {"some": "data"}
        p_lifecycle = {"stage": "proof_generated"}
        assert derive_trust_tier(v_status, p_bundle, p_lifecycle) == "proof_staged"

        # Case: Replay Checked
        v_status = {"onchain_ok": False, "replay_ok": True}
        p_bundle = None
        p_lifecycle = {}
        assert derive_trust_tier(v_status, p_bundle, p_lifecycle) == "replay_checked"

        # Case: Integrity Checked
        v_status = {"onchain_ok": False, "replay_ok": False, "integrity_ok": True}
        p_bundle = None
        p_lifecycle = {}
        assert derive_trust_tier(v_status, p_bundle, p_lifecycle) == "integrity_checked"

        # Case: Unverified
        v_status = {"onchain_ok": False, "replay_ok": False, "integrity_ok": False}
        p_bundle = None
        p_lifecycle = {}
        assert derive_trust_tier(v_status, p_bundle, p_lifecycle) == "unverified"
