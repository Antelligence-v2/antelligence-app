"""Tumor-run provenance and durable storage for the frontend API."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from .run_store import SQLiteRunStore


PUBLIC_VALUES_FIELDS = (
    "config_hash",
    "kill_rate_bps",
    "nanobot_count",
    "tumor_radius",
    "steps",
)


def canonical_config_hash(config: Dict[str, Any]) -> str:
    """Hash the exact JSON-serializable config persisted for a run."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_tumor_provenance(
    *,
    run_id: str,
    config: Dict[str, Any],
    tumor_statistics: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Create an honest staged proof envelope for one completed tumor run."""
    # Import lazily: importing the frontend API must not load blockchain clients.
    from .chain.proof_adapter import create_proof_bundle

    actual_config = dict(config)
    proof_metrics = dict(metrics)
    kill_rate = float(tumor_statistics.get("kill_rate", proof_metrics.get("kill_rate", 0.0)))
    # The existing attestation helper expects percentage points and scales them
    # to basis points itself.  The API's tumor_statistics keeps the historical
    # [0, 1] fraction, so convert only at the proof boundary.
    proof_metrics["kill_rate"] = kill_rate * 100.0

    bundle = create_proof_bundle(actual_config, proof_metrics, run_id=run_id)
    config_hash = bundle["onchain"]["simulation_commitments"]["config_hash"]
    expected_hash = canonical_config_hash(actual_config)
    if config_hash != expected_hash:
        raise ValueError("proof helper config hash does not match the actual tumor request config")

    verification_status = dict(bundle["verification_status"])
    proof_bundle = dict(bundle["proof_bundle"])
    public_values = dict(bundle["onchain"]["public_values_payload"])
    if tuple(public_values) != PUBLIC_VALUES_FIELDS:
        raise ValueError("proof helper public values drifted from the five-field contract")

    return {
        "run_id": run_id,
        "config": actual_config,
        "config_hash": config_hash,
        "trust_tier": bundle["trust_tier"],
        "proof_staged": bundle["trust_tier"] == "proof_staged",
        "proof_ok": bool(verification_status.get("proof_ok", False)),
        "verification_status": verification_status,
        "proof_lifecycle": bundle["proof_lifecycle"],
        "public_values": public_values,
        "onchain": bundle["onchain"],
        "proof_bundle": proof_bundle,
        # Keep the complete helper output available to clients that need the
        # artifact/IPFS metadata, while the proof_bundle field remains focused.
        "mock_bundle": bundle,
    }


def _json_default(value: Any) -> Any:
    """Serialize numpy scalars/arrays without changing stored API values."""
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class TumorRunStore:
    """SQLiteRunStore plus a durable JSON snapshot of the API response."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.run_store = SQLiteRunStore(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tumor_run_results (
                    run_id TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(
        self,
        *,
        run_id: str,
        status: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        provenance: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        self.run_store.save_run(run_id, status, config, metrics, provenance)
        result_json = json.dumps(result, sort_keys=True, default=_json_default)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tumor_run_results (run_id, result_json)
                VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET result_json=excluded.result_json
                """,
                (run_id, result_json),
            )
            conn.commit()

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        persisted = self.run_store.get_run(run_id)
        if persisted is None:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT result_json FROM tumor_run_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is not None:
            persisted["result"] = json.loads(row[0])
        return persisted
