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
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Union

from antelligence.kernel.canonical import canonical_json, content_hash
from antelligence.providers.base import ChatRequest, ChatResponse, Provider, ProviderError, ProviderTruncated

TELEMETRY_BODY_KEYS: FrozenSet[str] = frozenset({"logprobs", "top_logprobs", "stream_options"})

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


def base_request_hash(request: ChatRequest) -> str:
    """Cache lookup key with telemetry-only ``extra_body`` keys stripped.

    Leaves :attr:`ChatRequest.request_hash` unchanged while ensuring requests that differ only in
    telemetry options (``logprobs``, ``top_logprobs``, ``stream_options``) share one superset bucket.
    """
    if not request.extra_body or not any(k in request.extra_body for k in TELEMETRY_BODY_KEYS):
        return request.request_hash
    body = request.payload()
    for key in TELEMETRY_BODY_KEYS:
        body.pop(key, None)
    return content_hash(body)


def telemetry_flags(extra: Optional[Dict[str, Any]]) -> FrozenSet[str]:
    return frozenset(k for k in ("logprobs", "cached_tokens", "cost", "usage") if (extra or {}).get(k) is not None)


def _provider_extra_body(provider: Optional[Provider]) -> Dict[str, Any]:
    """Collect provider-level ``extra_body`` across any ``.inner`` wrapper chain (outer overrides inner)."""
    chain = []
    seen: set = set()
    cur: Any = provider
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(cur)
        cur = getattr(cur, "inner", None)
    merged: Dict[str, Any] = {}
    for node in reversed(chain):
        eb = getattr(node, "extra_body", None)
        if isinstance(eb, Mapping):
            merged.update(eb)
    return merged


def required_telemetry_from_extra_body(extra_body: Optional[Mapping[str, Any]]) -> FrozenSet[str]:
    """Infer required telemetry flags requested via an effective ``extra_body`` mapping."""
    if not extra_body:
        return frozenset()
    flags = set()
    logprobs_val = extra_body.get("logprobs")
    if logprobs_val or (logprobs_val is None and extra_body.get("top_logprobs")):
        flags.add("logprobs")
    stream_opts = extra_body.get("stream_options")
    if isinstance(stream_opts, Mapping) and stream_opts.get("include_usage"):
        flags.add("usage")
    return frozenset(flags)


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

    def required_for(self, request: Optional[ChatRequest] = None) -> FrozenSet[str]:
        effective = _provider_extra_body(self.inner)
        if request is not None and request.extra_body:
            effective.update(request.extra_body)
        return self.required | required_telemetry_from_extra_body(effective)

    def lookup(self, request_hash: Union[str, ChatRequest], required: Optional[FrozenSet[str]] = None) -> Optional[Dict[str, Any]]:
        if isinstance(request_hash, ChatRequest):
            key = base_request_hash(request_hash)
            need = self.required_for(request_hash) if required is None else frozenset(required)
        else:
            key = request_hash
            need = self.required_for() if required is None else frozenset(required)
        for (telemetry, row) in self._db.execute(
                "SELECT telemetry, row FROM responses WHERE request_hash = ? AND usable = 1 ORDER BY id", (key,)):
            if need <= frozenset(json.loads(telemetry)):
                return json.loads(row)
        return None

    def _truncated_row(self, request_hash: str) -> Optional[Dict[str, Any]]:
        found = self._db.execute("SELECT row FROM responses WHERE request_hash = ? AND usable = 0 ORDER BY id",
                                 (request_hash,)).fetchone()
        return json.loads(found[0]) if found else None

    def insert(self, row: Dict[str, Any], *, usable: bool = True, key: Optional[str] = None,
               flags: Optional[Iterable[str]] = None) -> bool:
        tflags = sorted(telemetry_flags(row.get("extra")) if flags is None else frozenset(flags))
        cache_key = row["request_hash"] if key is None else key
        cur = self._db.execute("INSERT OR IGNORE INTO responses (request_hash, telemetry, usable, row) VALUES (?,?,?,?)",
                               (cache_key, json.dumps(tflags), int(usable), canonical_json({**row, "cached": False})))
        return cur.rowcount == 1

    async def complete(self, request: ChatRequest) -> ChatResponse:
        key = base_request_hash(request)
        required = self.required_for(request)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:  # identical concurrent requests hit the model once
            hit = self.lookup(key, required=required)
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
                    self.insert(row, usable=False, key=key)
                raise
            self.insert(response.to_dict(), usable=True, key=key)
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
