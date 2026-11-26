"""SQLite (WAL) response cache with immutable superset capability matching.

Rows are insert-only, keyed by ``(request_hash, telemetry_flags)``. A lookup that requires telemetry ``R`` (for
example ``{"logprobs"}``) hits any usable row whose flags ``F`` satisfy ``R <= F``; a miss calls the provider and
inserts a NEW row, so asking for more telemetry never rewrites or busts older ``content``.

* ``finish_reason == "length"`` (:class:`ProviderTruncated`) is stored with ``format_ok=False`` at its real tokens,
  latency and cost, and raised again on a hit. It is never billed as zero.
* Any other :class:`ProviderError` is never stored as usable (it is not stored at all).
* The database must live on a local disk: paths under ``/Volumes`` (external drives, network mounts) are refused,
  because a frozen drive under SQLite WAL stalls the whole run.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, Optional, Union

from antelligence.kernel.canonical import canonical_json
from antelligence.providers.base import ChatRequest, ChatResponse, Provider, ProviderError, ProviderTruncated

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_hash TEXT NOT NULL,
    telemetry TEXT NOT NULL,
    usable INTEGER NOT NULL,
    row TEXT NOT NULL,
    UNIQUE (request_hash, telemetry)
);
CREATE INDEX IF NOT EXISTS responses_hash ON responses (request_hash);
"""


class UnsafeCachePath(ValueError):
    """The cache path is on an external or network volume."""


def check_local_path(path: Union[str, Path]) -> Path:
    resolved = Path(path).expanduser().resolve()
    parts = resolved.parts
    if len(parts) > 1 and parts[1] == "Volumes":
        raise UnsafeCachePath(f"refusing cache on external/network volume: {resolved} (use a local SSD path)")
    return resolved


def telemetry_flags(extra: Optional[Dict[str, Any]]) -> FrozenSet[str]:
    return frozenset(k for k in ("logprobs", "cached_tokens", "cost") if (extra or {}).get(k) is not None)


class SqliteCache:
    """Transparent caching wrapper; ``describe()`` is the inner provider's, so replays share the config hash."""

    def __init__(self, inner: Optional[Provider], path: Union[str, Path], *, required_telemetry: Iterable[str] = (),
                 offline: bool = False) -> None:
        self.inner = inner
        self.path = check_local_path(path)
        self.required = frozenset(required_telemetry)
        self.offline = offline
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)
        self._locks: Dict[str, asyncio.Lock] = {}

    def close(self) -> None:
        self._db.close()

    def __len__(self) -> int:
        return self._db.execute("SELECT COUNT(DISTINCT request_hash) FROM responses WHERE usable = 1").fetchone()[0]

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe() if self.inner is not None else {"provider": "cache_only"}

    def lookup(self, request_hash: str, required: Optional[FrozenSet[str]] = None) -> Optional[Dict[str, Any]]:
        need = self.required if required is None else required
        for (telemetry, row) in self._db.execute(
                "SELECT telemetry, row FROM responses WHERE request_hash = ? AND usable = 1 ORDER BY id", (request_hash,)):
            if need <= frozenset(json.loads(telemetry)):
                return json.loads(row)
        return None

    def _truncated_row(self, request_hash: str) -> Optional[Dict[str, Any]]:
        found = self._db.execute("SELECT row FROM responses WHERE request_hash = ? AND usable = 0 ORDER BY id",
                                 (request_hash,)).fetchone()
        return json.loads(found[0]) if found else None

    def insert(self, row: Dict[str, Any], *, usable: bool = True) -> bool:
        flags = sorted(telemetry_flags(row.get("extra")))
        cur = self._db.execute("INSERT OR IGNORE INTO responses (request_hash, telemetry, usable, row) VALUES (?,?,?,?)",
                               (row["request_hash"], json.dumps(flags), int(usable), canonical_json({**row, "cached": False})))
        return cur.rowcount == 1

    async def complete(self, request: ChatRequest) -> ChatResponse:
        key = request.request_hash
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:  # identical concurrent requests hit the model once
            hit = self.lookup(key)
            if hit is not None:
                return ChatResponse.from_dict(hit, cached=True)
            stored_cut = self._truncated_row(key)
            if stored_cut is not None:
                raise ProviderTruncated("cached truncated generation (length)",
                                        response=ChatResponse.from_dict(stored_cut, cached=True))
            if self.offline or self.inner is None:
                raise ProviderError(f"cache miss in offline mode ({key[:12]})")
            try:
                response = await self.inner.complete(request)
            except ProviderTruncated as exc:
                if exc.response is not None:  # honest billing: keep what the cut-off reply cost, flagged unusable
                    row = exc.response.to_dict()
                    row["extra"] = {**row.get("extra", {}), "format_ok": False}
                    self.insert(row, usable=False)
                raise
            self.insert(response.to_dict(), usable=True)
            return response


def import_legacy_jsonl(cache: SqliteCache, jsonl_path: Union[str, Path]) -> Dict[str, int]:
    """Import rows written by the legacy JSONL ``Cached`` wrapper. Zero provider calls, zero dollars."""
    counts = {"imported": 0, "skipped_duplicate": 0, "skipped_unusable": 0}
    for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("finish_reason") != "stop" or "content" not in row or "request_hash" not in row:
            counts["skipped_unusable"] += 1
            continue
        counts["imported" if cache.insert(row) else "skipped_duplicate"] += 1
    return counts


def main(argv: Optional[list] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m antelligence.providers.cache")
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import-legacy", help="import a legacy JSONL cache into the SQLite cache")
    imp.add_argument("jsonl")
    imp.add_argument("--db", required=True)
    args = ap.parse_args(argv)
    cache = SqliteCache(None, args.db, offline=True)
    print(json.dumps(import_legacy_jsonl(cache, args.jsonl)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
