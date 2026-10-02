"""SQLite store for engine runs and experiments, plus on-disk event logs."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.events import EventLog, EventLogError


class EngineStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.events_dir = self.directory / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.directory / "engine.sqlite3", check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, experiment_id TEXT, world TEXT NOT NULL,"
            " arm TEXT NOT NULL, case_id INTEGER NOT NULL, record TEXT NOT NULL, bundle TEXT NOT NULL,"
            " created_at REAL NOT NULL);"
            "CREATE INDEX IF NOT EXISTS runs_experiment ON runs(experiment_id);"
            "CREATE TABLE IF NOT EXISTS experiments (experiment_id TEXT PRIMARY KEY, request TEXT NOT NULL,"
            " report TEXT NOT NULL, created_at REAL NOT NULL);"
        )

    def _events_path(self, run_id: str) -> Path:
        if not run_id or any(c in run_id for c in "/\\") or run_id.startswith("."):
            raise ValueError("invalid run id")
        return self.events_dir / f"{run_id}.jsonl"

    def save_run(self, record: Mapping[str, Any], bundle: Mapping[str, Any], log: EventLog,
                 experiment_id: Optional[str] = None) -> None:
        log.write_jsonl(self._events_path(record["run_id"]))
        spec = record["spec"]
        self._db.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)",
            (record["run_id"], experiment_id, spec["world"], spec["arm"], spec["case"], canonical_json(dict(record)),
             canonical_json(dict(bundle)), time.time()),
        )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT record, bundle FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        return {**json.loads(row["record"]), "bundle": json.loads(row["bundle"])}

    def events(self, run_id: str, offset: int = 0, limit: int = 200) -> Optional[Dict[str, Any]]:
        path = self._events_path(run_id)
        if not path.exists():
            return None
        log = EventLog.read_jsonl(path)  # verifies the hash chain on every read
        record = self.get_run(run_id)
        if record is not None and (len(log) != record["event_count"] or log.trace_hash != record["trace_hash"]):
            # The chain only proves the lines that remain are unaltered; a dropped tail
            # is caught by comparing against the run record.
            raise EventLogError(f"event log for {run_id} is incomplete or does not match its run record "
                                f"({len(log)} of {record['event_count']} events)")
        events = [e.to_dict() for e in log]
        return {"run_id": run_id, "total": len(events), "offset": offset, "trace_hash": log.trace_hash,
                "events": events[offset: offset + limit]}

    def save_experiment(self, experiment_id: str, request: Mapping[str, Any], report: Mapping[str, Any]) -> None:
        self._db.execute("INSERT OR REPLACE INTO experiments VALUES (?,?,?,?)",
                         (experiment_id, canonical_json(dict(request)), canonical_json(dict(report)), time.time()))

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT report FROM experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return json.loads(row["report"]) if row else None

    def list_experiments(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._db.execute(
            "SELECT experiment_id, request, created_at FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,))
        return [{"experiment_id": r["experiment_id"], "request": json.loads(r["request"]), "created_at": r["created_at"]}
                for r in rows]
