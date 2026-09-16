
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.verify import _derive_trust_tier

def test_trust_tier_derivation():
    # 1. verified_onchain
    assert _derive_trust_tier({"onchain_ok": True}, None, None) == "verified_onchain"
    
    # 2. proof_staged (proof_bundle exists)
    assert _derive_trust_tier({"onchain_ok": False}, {"some": "bundle"}, None) == "proof_staged"
    
    # 3. A self-declared lifecycle stage cannot promote trust without a bundle.
    assert _derive_trust_tier({"onchain_ok": False}, None, {"stage": "proof_generated"}) == "unverified"
    assert _derive_trust_tier(
        {"onchain_ok": False, "integrity_ok": True},
        None,
        {"stage": "proof_generated"},
    ) == "integrity_checked"
    
    # 4. replay_checked
    assert _derive_trust_tier({"onchain_ok": False, "replay_ok": True}, None, None) == "replay_checked"
    
    # 5. integrity_checked
    assert _derive_trust_tier({"onchain_ok": False, "replay_ok": False, "integrity_ok": True}, None, None) == "integrity_checked"
    
    # 6. unverified
    assert _derive_trust_tier({"onchain_ok": False, "replay_ok": False, "integrity_ok": False}, None, None) == "unverified"
    
    print("Trust tier derivation tests passed!")

if __name__ == "__main__":
    test_trust_tier_derivation()
