
import json
import pytest
import sys
import os

# Add backend to path so we can import chain.verify
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from chain.verify import verify_artifact

class TestTrustTierExplicit:
    def test_trust_tier_mock_prefix(self):
        # Create a mock artifact that is explicitly a mock
        artifact = {
            "type": "antelligence-simulation-v2",
            "run_id": "test-mock-123",
            "is_mock": True,
            "config_hash": "0" * 64,
            "metrics_hash": "0" * 64,
            "artifact_hash": "0" * 64,
            "config": {"tumor_radius": 100},
            "metrics": {"kill_rate": 10.0, "deliveries": 5},
            "verification_status": {
                "integrity_ok": True,
                "replay_ok": True,
                "onchain_ok": False
            },
            "trust_tier": "integrity_checked",
            "trust_metadata": {}
        }
        
        import chain.verify
        
        # Mocking check_onchain_verification to return a safe response
        def mock_check(config_hash):
            return {"ok": True, "verified": False, "raw": "0x0"}
        
        # Mocking verify_artifact_integrity to return a simple PASS
        def mock_integrity(artifact):
            return {"ok": True, "checks": []}

        # Mocking verify_public_values_schema to return a simple PASS
        def mock_pv_schema(artifact):
            return {"ok": True}

        # Mocking verify_proof_bundle_schema to return a simple PASS
        def mock_pb_schema(record):
            return {"ok": True}

        # Mocking verify_artifact_replay to return a simple PASS
        def mock_replay(artifact, tolerance_pct=5.0):
            return {"ok": True, "recomputed_metrics": {"kill_rate": 10.0, "deliveries": 5}}

        with pytest.MonkeyPatch.context() as m:
            m.setattr(chain.verify, "check_onchain_verification", mock_check)
            m.setattr(chain.verify, "verify_artifact_integrity", mock_integrity)
            m.setattr(chain.verify, "verify_public_values_schema", mock_pv_schema)
            m.setattr(chain.verify, "verify_proof_bundle_schema", mock_pb_schema)
            m.setattr(chain.verify, "verify_artifact_replay", mock_replay)
            
            result = verify_artifact(artifact, replay=True)
            
            # The trust_tier should be prefixed with 'mock_' because is_mock is True
            assert "mock_" in result["trust_tier"]
            assert result["trust_metadata"]["is_mock"] is True

    def test_trust_tier_onchain_override(self):
        artifact = {
            "type": "antelligence-simulation-v2",
            "is_mock": False,
            "config_hash": "0" * 64,
            "metrics_hash": "0" * 64,
            "artifact_hash": "0" * 64,
            "config": {"tumor_radius": 100},
            "metrics": {"kill_rate": 10.0, "deliveries": 5},
            "verification_status": {
                "integrity_ok": True,
                "replay_ok": True,
                "onchain_ok": True
            },
            "trust_tier": "unverified"
        }
        
        import chain.verify
        
        def mock_check(config_hash):
            return {"ok": True, "verified": True, "raw": "0x1"}
        def mock_integrity(artifact):
            return {"ok": True, "checks": []}
        def mock_pv_schema(artifact):
            return {"ok": True}
        def mock_pb_schema(record):
            return {"ok": True}
        def mock_replay(artifact, tolerance_pct=5.0):
            return {"ok": True, "recomputed_metrics": {"kill_rate": 10.0, "deliveries": 5}}

        with pytest.MonkeyPatch.context() as m:
            m.setattr(chain.verify, "check_onchain_verification", mock_check)
            m.setattr(chain.verify, "verify_artifact_integrity", mock_integrity)
            m.setattr(chain.verify, "verify_public_values_schema", mock_pv_schema)
            m.setattr(chain.verify, "verify_proof_bundle_schema", mock_pb_schema)
            m.setattr(chain.verify, "verify_artifact_replay", mock_replay)
            
            result = verify_int_artifact_wrapper(artifact, replay=True) if False else verify_artifact(artifact, replay=True)
            assert result["trust_tier"] == "verified_onchain"

# Helper for the test to avoid ambiguity if needed, but we'll just use verify_artifact
def verify_int_artifact_wrapper(artifact, replay=True):
    from chain.verify import verify_artifact
    return verify_artifact(artifact, replay=replay)
