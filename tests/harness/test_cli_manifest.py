"""Tests for antelligence-harness CLI and manifest.lock.json snapshotter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from antelligence.harness.cli import main, write_manifest
from antelligence.harness.scorecard import Outcome, OutcomeLog


def test_manifest_snapshotter_writes_lock_json(tmp_path):
    data_file = tmp_path / "tasks.jsonl"
    data_file.write_text('{"id":"t1"}\n', encoding="utf-8")
    studies_dir = tmp_path / "studies"

    out = write_manifest(
        "triage-v1",
        studies_dir=studies_dir,
        study_date="2026-11-26",
        inputs=[data_file],
        cutoff_at="2026-11-01T00:00:00Z",
        notes="initial curated triage run",
    )
    assert out == studies_dir / "2026-11-26-triage-v1" / "manifest.lock.json"
    assert out.is_file()

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["study"]["slug"] == "triage-v1"
    assert payload["study"]["date"] == "2026-11-26"
    assert payload["study"]["cutoff_at"] == "2026-11-01T00:00:00Z"
    assert payload["inputs"][str(data_file)] is not None
    assert "numpy" in payload["runtime"]["packages"]


def test_cli_snapshot_and_score_subcommands(tmp_path, capsys):
    rc = main(["snapshot", "smoke", "--date", "2026-11-26", "--studies-dir", str(tmp_path / "studies")])
    assert rc == 0
    snap_out = json.loads(capsys.readouterr().out)
    assert Path(snap_out["manifest"]).is_file()

    log_path = tmp_path / "outcomes.jsonl"
    log = OutcomeLog(log_path)
    log.add(Outcome(task="t1", kind="ops", variant="baseline", score=0.0, tokens_in=100, tokens_out=20, seconds=1.0))
    log.add(Outcome(task="t1", kind="ops", variant="ours", score=1.0, tokens_in=50, tokens_out=10, seconds=0.5))

    rc2 = main(["score", str(log_path), "--baseline", "baseline"])
    assert rc2 == 0
    score_out = json.loads(capsys.readouterr().out)
    assert "ours" in score_out["summary"]
    assert score_out["pareto"] == ["ours"]


def test_cli_help_subprocess():
    res = subprocess.run([sys.executable, "-m", "antelligence.harness.cli", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "snapshot" in res.stdout
    assert "score" in res.stdout
