"""Tests for SQLite-backed run persistence."""

from pathlib import Path

from backend.run_store import SQLiteRunStore


class TestSQLiteRunStore:
    def test_save_and_get_run(self, tmp_path: Path):
        store = SQLiteRunStore(tmp_path / "runs.sqlite3")
        store.save_run(
            "run-123",
            "completed",
            {"num_bots": 2, "steps": 3},
            {"kill_rate": 0.5, "step_count": 3},
        )
        result = store.get_run("run-123")
        assert result is not None
        assert result["run_id"] == "run-123"
        assert result["status"] == "completed"
        assert result["config"]["num_bots"] == 2
        assert result["metrics"]["step_count"] == 3

    def test_get_missing_run_returns_none(self, tmp_path: Path):
        store = SQLiteRunStore(tmp_path / "runs.sqlite3")
        assert store.get_run("missing") is None
