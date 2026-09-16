"""SQLite-backed run store for durable API simulation results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class SQLiteRunStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    provenance_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
            if "provenance_json" not in columns:
                conn.execute("ALTER TABLE runs ADD COLUMN provenance_json TEXT")
            conn.commit()

    def save_run(
        self,
        run_id: str,
        status: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, status, config_json, metrics_json, provenance_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    config_json=excluded.config_json,
                    metrics_json=excluded.metrics_json,
                    provenance_json=excluded.provenance_json
                """,
                (run_id, status, json.dumps(config), json.dumps(metrics), json.dumps(provenance) if provenance else None),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id, status, config_json, metrics_json, provenance_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row[0],
            "status": row[1],
            "config": json.loads(row[2]),
            "metrics": json.loads(row[3]),
            "provenance": json.loads(row[4]) if row[4] else None,
        }
