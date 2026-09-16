import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add backend to sys.path so we can import the bot's dependencies
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from scripts.attestation_bot import main, run_spot_checks


def test_attestation_bot_dry_run_json_stdout_is_one_document(tmp_path: Path, capsys):
    input_path = tmp_path / "result.json"
    input_path.write_text(
        json.dumps(
            {
                "config": {},
                "results": [
                    {
                        "seed": 1,
                        "patient": "test",
                        "kill_rate_pct": 10.0,
                        "deliveries": 2,
                    }
                ],
            }
        )
    )

    with patch.object(sys, "argv", ["attestation_bot.py", str(input_path), "--dry-run", "--json"]):
        main()

    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["ok"] is False
    assert parsed["status"] == "dry_run_unverified"
    assert parsed["candidate_count"] == 1
    assert parsed["checked"] == 0


def test_attestation_bot_dry_run(tmp_path: Path):
    """
    Test that the attestation bot can process a dummy JSON input
    and report results without needing real blockchain/IPFS side effects.
    """
    # 1. Create a dummy input file
    dummy_input_path = tmp_path / "dummy_results.json"
    dummy_data = {
        "config": {
            "steps": 50,
            "n_bots": 5,
            "with_queen": True,
            "episode_length": 10
        },
        "results": [
            {
                "seed": 42,
                "patient": "test_patient_1",
                "kill_rate_pct": 10.0,
                "deliveries": 5,
                "tumor_radius": 150
            },
            {
                "seed": 123,
                "patient": "test_patient_2",
                "kill_rate_pct": 20.0,
                "deliveries": 10,
                "tumor_radius": 150
            }
        ]
    }
    
    dummy_input_path.write_text(json.dumps(dummy_data))

    try:
        # 2. Run the core logic without replaying live simulations or touching
        # blockchain/IPFS side effects.
        
        # We patch 'spot_check_run' to track if it's called.
        with patch("scripts.attestation_bot.spot_check_run") as mock_spot_check:
            # We also need to mock the return value of the patch if it WERE called, 
            # but since we are testing the 'else' branch (dry_run=True), it shouldn't be called.
            
            def fake_spot_check_return(original, steps, n_bots, with_queen, episode_length):
                return {
                    "kill_rate_pct": original["kill_rate_pct"],
                    "kills": 0,
                    "deliveries": original["deliveries"],
                }
            
            # To make the patch robust, we'll use the side_effect for the 'else' branch 
            # just in case, but our goal is to ensure it's NOT called during dry_run=True.
            mock_spot_check.side_effect = fake_spot_check_return

            # Perform the dry run
            result = run_spot_checks(dummy_data, sample_pct=100, tolerance_pct=5.0, verbose=False, dry_run=True)
            
            # 3. Assertions
            assert result["ok"] is False
            assert result["status"] == "dry_run_unverified"
            assert result["candidate_count"] == 2
            assert result["checked"] == 0
            assert result["passed"] == 0
            
            # CRITICAL: Verify that the heavy 'spot_check_run' was NOT called during dry_run=True.
            # This proves the 'else' branch (the dry-run guard) was taken.
            mock_spot_check.assert_not_called()

            print("Dry run test passed successfully!")

    finally:
        # Cleanup
        if dummy_input_path.exists():
            dummy_input_path.unlink()

if __name__ == "__main__":
    test_attestation_bot_dry_run()
