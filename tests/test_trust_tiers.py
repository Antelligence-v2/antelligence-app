
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact
from chain.proof_adapter import create_proof_bundle
from chain.verify import verify_artifact

class TestVerifyTrustTiers:
    def test_trust_tier_differentiation(self):
        import chain.verify as verify_module

        # 1. Mock/Unverified
        artifact_unverified = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        artifact_unverified["is_mock"] = True
        result_unverified = verify_artifact(artifact_unverified, replay=False)
        assert "mock" in result_unverified["trust_tier"]

        # 2. Integrity Checked (No proof, no onchain)
        artifact_integrity = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        result_integrity = verify_artifact(artifact_integrity, replay=False)
        assert result_integrity["trust_tier"] == "integrity_checked"

        # 3. Proof Staged
        bundle = create_proof_bundle(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
            run_id="proof-test"
        )
        artifact_staged = {
            **bundle["ipfs"]["artifact"],
            "onchain": bundle["onchain"],
            "proof_bundle": bundle["proof_bundle"],
            "proof_lifecycle": bundle["proof_lifecycle"],
            "verification_status": bundle["verification_status"],
            "trust_tier": "proof_staged"
        }
        result_staged = verify_artifact(artifact_staged, replay=False)
        assert result_staged["trust_tier"] == "proof_staged"

        # 4. Verified Onchain
        original_check = verify_module.check_onchain_verification
        verify_module.check_onchain_verification = lambda config_hash: {"ok": True, "verified": True}
        
        try:
            result_onchain = verify_artifact(artifact_staged, replay=False)
            assert result_onchain["trust_tier"] == "verified_onchain"
        finally:
            verify_module.check_onchain_verification = original_check

    def test_trust_metadata_explicit(self):
        from chain.verify import verify_artifact
        from chain.ipfs import create_simulation_artifact

        artifact = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        artifact["is_mock"] = True
        result = verify_artifact(artifact, replay=False)
        
        assert "trust_metadata" in result
        assert result["trust_metadata"]["is_mock"] is True
        assert result["trust_metadata"]["is_cryptographic"] is False
