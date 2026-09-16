"""Unit tests for leaderboard service."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.ipfs import create_simulation_artifact
from chain.leaderboard import rank_by_kill_rate, build_leaderboard, normalize_leaderboard_artifact
from chain.proof_adapter import create_proof_bundle


class TestRanking:
    def test_rank_by_kill_rate(self):
        entries = [
            {"kill_rate": 30.0, "run_id": "a"},
            {"kill_rate": 50.0, "run_id": "b"},
            {"kill_rate": 10.0, "run_id": "c"},
        ]
        ranked = rank_by_kill_rate(entries)
        assert ranked[0]["run_id"] == "b"
        assert ranked[0]["rank"] == 1
        assert ranked[1]["run_id"] == "a"
        assert ranked[2]["run_id"] == "c"

    def test_empty_list(self):
        ranked = rank_by_kill_rate([])
        assert ranked == []

    def test_single_entry(self):
        ranked = rank_by_kill_rate([{"kill_rate": 45.5}])
        assert ranked[0]["rank"] == 1


class TestBuildLeaderboard:
    def test_from_artifacts(self):
        artifacts = [
            create_simulation_artifact(
                config={"tumor_radius": 150, "nanobot_count": 10, "steps": 300},
                metrics={"kill_rate": 45.5, "deliveries": 30},
                run_id="run-001",
            ),
            create_simulation_artifact(
                config={"tumor_radius": 150, "nanobot_count": 5, "steps": 300},
                metrics={"kill_rate": 22.0, "deliveries": 10},
                run_id="run-002",
            ),
        ]
        result = build_leaderboard(artifacts)
        assert result["ok"] is True
        assert len(result["leaderboard"]) == 2
        assert result["leaderboard"][0]["run_id"] == "run-001"
        assert result["leaderboard"][0]["rank"] == 1
        assert result["summary"]["best_kill_rate"] == 45.5
        assert result["summary"]["total_entries"] == 2

    def test_empty_artifacts(self):
        result = build_leaderboard([])
        assert result["ok"] is True
        assert len(result["leaderboard"]) == 0
        assert result["summary"]["total_entries"] == 0

    def test_summary_stats(self):
        artifacts = [
            create_simulation_artifact(
                config={"tumor_radius": 100},
                metrics={"kill_rate": 40.0},
            ),
            create_simulation_artifact(
                config={"tumor_radius": 100},
                metrics={"kill_rate": 60.0},
            ),
        ]
        result = build_leaderboard(artifacts)
        assert result["summary"]["avg_kill_rate"] == 50.0
        assert result["summary"]["best_kill_rate"] == 60.0

    def test_summary_average_includes_zero_kill_runs(self):
        artifacts = [
            create_simulation_artifact(
                config={"tumor_radius": 100},
                metrics={"kill_rate": 0.0},
            ),
            create_simulation_artifact(
                config={"tumor_radius": 100},
                metrics={"kill_rate": 60.0},
            ),
        ]
        result = build_leaderboard(artifacts)
        assert result["summary"]["avg_kill_rate"] == 30.0

    def test_lifecycle_stage_alone_does_not_promote_leaderboard_trust(self):
        artifact = create_simulation_artifact(
            config={"tumor_radius": 100},
            metrics={"kill_rate": 10.0},
        )
        artifact.pop("trust_tier", None)
        artifact["proof_lifecycle"] = {"stage": "proof_generated"}
        artifact["proof_bundle"] = {}
        artifact["verification_status"] = {"integrity_ok": True}

        result = build_leaderboard([artifact])

        assert result["leaderboard"][0]["trust_tier"] == "integrity_checked"
        assert result["summary"]["staged_proof_entries"] == 0

    def test_staged_proof_entries_are_labeled_honestly(self):
        artifact = create_proof_bundle(
            config={"tumor_radius": 100, "nanobot_count": 3, "steps": 10},
            metrics={"kill_rate": 22.0, "deliveries": 5},
            run_id="proof-stage-1",
        )
        result = build_leaderboard([artifact])
        entry = result["leaderboard"][0]
        assert entry["run_id"] == "proof-stage-1"
        assert entry["kill_rate"] == 22.0
        assert entry["deliveries"] == 5
        assert entry["nanobot_count"] == 3
        assert entry["steps"] == 10
        assert entry["trust_tier"] == "proof_staged"
        assert entry["proof_origin"] == "sp1-groth16-adapter"
        assert entry["proof_ok"] is False
        assert result["summary"]["staged_proof_entries"] == 1

    def test_normalize_leaderboard_artifact_flattens_attestation_bundle(self):
        artifact = create_proof_bundle(
            config={"tumor_radius": 90, "nanobot_count": 7, "steps": 12},
            metrics={"kill_rate": 31.5, "deliveries": 2},
            run_id="proof-stage-2",
        )
        normalized = normalize_leaderboard_artifact(artifact)
        assert normalized["run_id"] == "proof-stage-2"
        assert normalized["metrics"]["kill_rate"] == 31.5
        assert normalized["config"]["nanobot_count"] == 7
        assert normalized["proof_bundle"]["proof_origin"] == "sp1-groth16-adapter"
        assert normalized["verification_status"]["integrity_ok"] is True
