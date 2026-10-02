"""Provenance outbox: publish bundles *after* runs, never inside the tick loop.

Runs enqueue their bundle (idempotent by bundle hash). A separate drain step
hands pending bundles to a publisher and records a receipt or the failure;
failed items are retried up to ``max_attempts``. Publishers shipped here:

* :class:`LocalFilePublisher` — content-addressed JSON files (default).
* :class:`LocalIPFSPublisher` — a local IPFS node's ``/api/v0/add``.

There is intentionally no chain publisher: on-chain submission changes
external state and stays an explicit operator action via ``backend.chain``.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol

from antelligence.kernel.canonical import canonical_json, content_hash

PENDING, PUBLISHED, FAILED = "pending", "published", "failed"


class Publisher(Protocol):
    name: str

    async def publish(self, bundle: Mapping[str, Any]) -> Dict[str, Any]: ...


class LocalFilePublisher:
    name = "local_file"

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    async def publish(self, bundle: Mapping[str, Any]) -> Dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        text = canonical_json(dict(bundle))
        path = self.directory / f"{bundle['bundle_hash']}.json"
        path.write_text(text, encoding="utf-8")
        return {"uri": path.resolve().as_uri(), "sha256": content_hash(dict(bundle))}


class LocalIPFSPublisher:
    name = "local_ipfs"

    def __init__(self, api_url: str = "http://127.0.0.1:5001") -> None:
        self.api_url = api_url

    async def publish(self, bundle: Mapping[str, Any]) -> Dict[str, Any]:
        from backend.chain.ipfs import pin_to_local_ipfs

        cid, error = await asyncio.to_thread(pin_to_local_ipfs, dict(bundle), self.api_url)
        if error or not cid:
            raise RuntimeError(error or "no CID returned")
        return {"cid": cid, "uri": f"ipfs://{cid}"}


class ProvenanceOutbox:
    def __init__(self, path: str = ":memory:", *, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS outbox (bundle_hash TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
            "bundle TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, "
            "publisher TEXT, receipt TEXT, last_error TEXT, updated_at REAL NOT NULL)"
        )

    def enqueue(self, bundle: Mapping[str, Any]) -> bool:
        """Returns False if this exact bundle is already queued/published."""
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO outbox(bundle_hash, run_id, bundle, status, updated_at) VALUES (?,?,?,?,?)",
            (bundle["bundle_hash"], bundle["run_id"], canonical_json(dict(bundle)), PENDING, time.time()),
        )
        return cursor.rowcount == 1

    def status(self, bundle_hash: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM outbox WHERE bundle_hash=?", (bundle_hash,)).fetchone()
        if row is None:
            return None
        return {"bundle_hash": row["bundle_hash"], "run_id": row["run_id"], "status": row["status"],
                "attempts": row["attempts"], "publisher": row["publisher"],
                "receipt": json.loads(row["receipt"]) if row["receipt"] else None, "last_error": row["last_error"]}

    def pending(self) -> List[str]:
        return [r["bundle_hash"] for r in self._db.execute(
            "SELECT bundle_hash FROM outbox WHERE status=? ORDER BY updated_at, bundle_hash", (PENDING,))]

    async def drain(self, publisher: Publisher, *, limit: int = 100) -> Dict[str, int]:
        counts = {PUBLISHED: 0, FAILED: 0, "retrying": 0}
        for bundle_hash in self.pending()[:limit]:
            row = self._db.execute("SELECT bundle, attempts FROM outbox WHERE bundle_hash=?", (bundle_hash,)).fetchone()
            bundle = json.loads(row["bundle"])
            attempts = row["attempts"] + 1
            try:
                receipt = await publisher.publish(bundle)
            except Exception as exc:  # recorded, retried, never raised into the caller's run
                status = FAILED if attempts >= self.max_attempts else PENDING
                counts[FAILED if status == FAILED else "retrying"] += 1
                self._db.execute(
                    "UPDATE outbox SET status=?, attempts=?, publisher=?, last_error=?, updated_at=? WHERE bundle_hash=?",
                    (status, attempts, publisher.name, f"{type(exc).__name__}: {exc}"[:500], time.time(), bundle_hash),
                )
                continue
            counts[PUBLISHED] += 1
            self._db.execute(
                "UPDATE outbox SET status=?, attempts=?, publisher=?, receipt=?, last_error=NULL, updated_at=? "
                "WHERE bundle_hash=?",
                (PUBLISHED, attempts, publisher.name, canonical_json(receipt), time.time(), bundle_hash),
            )
        return counts
