
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact
from chain.leaderboard import build_leaderboard


def test_leaderboard_preserves_worker_parameters_for_dpo_training():
    artifact = create_simulation_artifact(
        config={
            "tumor_radius": 100,
            "pheromone_params": {"trail_decay": 0.08, "recruitment_diffusion": 1e-6},
        },
        metrics={"kill_rate": 50.0},
        run_id="dpo-config-test",
    )
    artifact["verification_status"] = {"replay_ok": True}

    entry = build_leaderboard([artifact])["leaderboard"][0]

    assert entry["pheromone_params"] == {
        "trail_decay": 0.08,
        "recruitment_diffusion": 1e-6,
    }

def test_onchain_verification_propagation():
    """Verify that onchain_ok status propagates to verified_onchain and trust_perm."""
    artifact = create_simulation_artifact(
        config={"tumor_radius": 100},
        metrics={"kill_rate": 50.0},
        run_id="onchain-test"
    )
    # Inject verification_status
    artifact["verification_status"] = {"onchain_ok": True}
    
    result = build_leaderboard([artifact])
    entry = result["leaderboard"][0]
    
    assert entry["verified_onchain"] is True
    assert entry["trust_tier"] == "verified_onchain"

def test_downgrade_propagation_regression():
    """
    Regression test for Objective A1:
    When a prover is downgraded (e.g., from 'verified_onchain' to 'replay_checked' or 'unverified'),
    the leaderboard must reflect the new, lower trust tier instead of staying cached.
    """
    # 1. Create an initial high-trust artifact
    artifact = create_simulation_artifact(
        config={"tumor_radius": 100},
        metrics={"kill_rate": 80.0},
        run_id="high-trust-run"
    )
    artifact["verification_status"] = {"onchain_ok": True}
    
    # Initial leaderboard build
    result_initial = build_leaderboard([artifact])
    initial_entry = result_initial["leaderboard"][0]
    assert initial_entry["trust_tier"] == "verified_onchain"

    # 2. Simulate a downgrade: The verification status is updated to reflect a lower tier
    # (e.g., onchain verification failed or was revoked, but replay is still ok)
    artifact["verification_status"] = {"onchain_ok": False, "replay_ok": True}
    
    # 3. Re-build leaderboard with the updated artifact
    result_updated = build_leaderboard([artifact])
    updated_entry = result_updated["leaderboard"][0]
    
    # ASSERTION: The trust_tier MUST propagate the downgrade.
    # If the system is broken, it might still show 'verified_onchain' from a stale cache.
    assert updated_entry["trust_tier"] == "replay_checked"
    assert updated_entry["trust_tier"] != "verified_onchain"
    
    # NEW RED STEP: Assert that the verification_status fields are also correctly updated
    # to reflect the downgrade in the flattened record.
    # If the implementation is broken, 'verified_onchain' might still be True from a stale cache.
    assert updated_entry["verified_onchain"] is False
    assert updated_entry["replay_ok"] is True
    assert updated_entry["trust_tier"] == "replay_checked"

