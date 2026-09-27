"""Versioned, evaluator-gated scratch memory for research-hive candidates."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

STORE_VERSION = "research-hive-memory-v1"
_MAX_JSON_BYTES = 65_536
_MAX_DEPENDENCIES = 128
_MAX_EVIDENCE_REFS = 8
_MAX_GRAPH_MUTATIONS = 256
_MAX_STRING = 4_096
_KINDS = {"observation", "evidence_claim", "conditional_procedure", "failure_note"}
_STATUSES = {"candidate", "retained", "admitted", "superseded", "invalidated", "contradicted"}
_ACTIVE_STATUSES = {"admitted"}


class HiveMemoryError(ValueError):
    """Invalid, oversized, conflicting, or unauthorized memory operation."""


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    except (TypeError, ValueError) as exc:
        raise HiveMemoryError("record must be JSON-compatible") from exc


def _normalize_refs(value: Any, field: str) -> list[str]:
    if type(value) is not list or len(value) > _MAX_DEPENDENCIES:
        raise HiveMemoryError(f"{field} must contain at most 128 items")
    if any(type(item) is not str or not item or len(item) > _MAX_STRING for item in value):
        raise HiveMemoryError(f"{field} references must be bounded strings")
    return sorted(set(value))


def _validate_record(record: Any) -> dict[str, Any]:
    if type(record) is not dict:
        raise HiveMemoryError("record must be an object")
    required = {"kind", "content", "source_id", "source_revision", "applicability", "protocol", "revision", "dependencies"}
    if not required.issubset(record):
        raise HiveMemoryError("record provenance and scope fields are required")
    if record["kind"] not in _KINDS:
        raise HiveMemoryError("unsupported record kind")
    for field in ("source_id", "source_revision", "applicability", "protocol"):
        if type(record[field]) is not str or not record[field] or len(record[field]) > _MAX_STRING:
            raise HiveMemoryError(f"{field} must be a bounded nonempty string")
    if type(record["revision"]) is not int or record["revision"] < 0:
        raise HiveMemoryError("revision must be a nonnegative integer")
    value = dict(record)
    value["dependencies"] = _normalize_refs(value["dependencies"], "dependencies")
    if "evidence_refs" in value:
        value["evidence_refs"] = _normalize_refs(value["evidence_refs"], "evidence references")
        if len(value["evidence_refs"]) > _MAX_EVIDENCE_REFS:
            raise HiveMemoryError("evidence references must contain at most 8 items")
    if "status" in value and value["status"] not in _STATUSES:
        raise HiveMemoryError("unsupported record status")
    if "evaluator_id" in value and (type(value["evaluator_id"]) is not str or len(value["evaluator_id"]) > _MAX_STRING):
        raise HiveMemoryError("evaluator_id must be a bounded string")
    if "evaluator_revision" in value and (type(value["evaluator_revision"]) is not str or len(value["evaluator_revision"]) > _MAX_STRING):
        raise HiveMemoryError("evaluator_revision must be a bounded string")
    if "experimental_arm" in value and (type(value["experimental_arm"]) is not str or not value["experimental_arm"] or len(value["experimental_arm"]) > _MAX_STRING):
        raise HiveMemoryError("experimental_arm must be a bounded nonempty string")
    if len(_json_bytes(value)) > _MAX_JSON_BYTES:
        raise HiveMemoryError("record JSON exceeds 65536 bytes")
    return value


def _identity(record: dict[str, Any]) -> dict[str, Any]:
    value = {key: record[key] for key in ("kind", "source_id", "source_revision", "applicability", "protocol", "revision")}
    value["experimental_arm"] = record.get("experimental_arm", "default")
    return value


def _source_lineage_identity(record: dict[str, Any]) -> dict[str, Any]:
    value = {key: record[key] for key in ("kind", "source_id", "applicability", "protocol", "revision")}
    value["experimental_arm"] = record.get("experimental_arm", "default")
    return value


def _record_id(record: dict[str, Any]) -> str:
    return hashlib.sha256(_json_bytes({"identity": _identity(record), "record": record})).hexdigest()


def _immutable_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in {
        "status", "evaluator_id", "evaluator_revision", "supersession_cause",
        "invalidation_cause", "contradiction_cause",
    }}


class HiveMemoryStore:
    """A small, versioned scratch store with atomic candidate/admission operations."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._new_path = not self.path.exists() or self.path.stat().st_size == 0
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            if self._new_path:
                db.execute("CREATE TABLE hive_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("""CREATE TABLE hive_records (
                    record_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL, record_json TEXT NOT NULL,
                    kind TEXT NOT NULL, status TEXT NOT NULL, source_id TEXT NOT NULL,
                    protocol TEXT NOT NULL, revision INTEGER NOT NULL
                )""")
                db.execute("INSERT INTO hive_metadata(key, value) VALUES ('version', ?)", (STORE_VERSION,))
            self._validate_connection(db)

    def _validate_connection(self, db: sqlite3.Connection) -> None:
        """Validate this opened connection's metadata, schema, and stored rows."""
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != {"hive_metadata", "hive_records"}:
            raise HiveMemoryError("corrupt hive memory schema")
        metadata_columns = {row[1] for row in db.execute("PRAGMA table_info(hive_metadata)")}
        if metadata_columns != {"key", "value"}:
            raise HiveMemoryError("corrupt hive_metadata schema")
        row = db.execute("SELECT value FROM hive_metadata WHERE key='version'").fetchone()
        if row is None:
            raise HiveMemoryError("missing hive memory store version")
        if row[0] != STORE_VERSION:
            raise HiveMemoryError("unsupported hive memory store version")
        columns = {row[1] for row in db.execute("PRAGMA table_info(hive_records)")}
        required = {"record_id", "identity_json", "record_json", "kind", "status", "source_id", "protocol", "revision"}
        if columns != required:
            raise HiveMemoryError("corrupt hive_records schema")
        self._verify_db(db)

    def _verify_db(self, db: sqlite3.Connection) -> None:
        for row in db.execute("SELECT record_id, identity_json, record_json, kind, status, source_id, protocol, revision FROM hive_records"):
            try:
                value = json.loads(row["record_json"])
                identity = json.loads(row["identity_json"])
                if _record_id(_immutable_record(value)) != row["record_id"]:
                    raise ValueError
                if identity != _identity(value) or row["kind"] != value["kind"] or row["status"] != value.get("status"):
                    raise ValueError
                _validate_record(value)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                raise HiveMemoryError("corrupt hive memory record")

    @staticmethod
    def _status_for(value: dict[str, Any]) -> str:
        return "retained" if value["kind"] in {"evidence_claim", "failure_note"} else "candidate"

    def _insert_db(self, db: sqlite3.Connection, value: dict[str, Any]) -> str:
        value = dict(value)
        value["status"] = self._status_for(value)
        value.pop("evaluator_id", None)
        value.pop("evaluator_revision", None)
        record_id = _record_id(_immutable_record(value))
        encoded = _json_bytes(value).decode()
        identity_json = _json_bytes(_identity(value)).decode()
        existing = db.execute("SELECT record_json FROM hive_records WHERE record_id=?", (record_id,)).fetchone()
        if existing is not None:
            return record_id
        db.execute("INSERT INTO hive_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (record_id, identity_json, encoded, value["kind"], value["status"],
                    value["source_id"], value["protocol"], value["revision"]))
        return record_id

    @staticmethod
    def _validate_existing_refs(rows: dict[str, dict[str, Any]], value: dict[str, Any]) -> None:
        arm = value.get("experimental_arm", "default")
        for reference in HiveMemoryStore._refs(value):
            parent = rows.get(reference)
            if parent is not None and parent.get("experimental_arm", "default") != arm:
                raise HiveMemoryError("references cannot cross experimental arms")

    def insert_candidate(self, record: dict[str, Any]) -> str:
        value = _validate_record(record)
        replacement = False
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_connection(db)
            rows = self._rows(db)
            self._validate_existing_refs(rows, value)
            normalized_id = _record_id(_immutable_record(value))
            exact = db.execute("SELECT record_id FROM hive_records WHERE record_id=?", (normalized_id,)).fetchone()
            if exact is not None:
                return normalized_id
            replacement = any(_source_lineage_identity(item) == _source_lineage_identity(value) for item in rows.values())
            if not replacement:
                return self._insert_db(db, value)
        return self.replace_source(value)

    def _rows(self, db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        return {row["record_id"]: json.loads(row["record_json"]) for row in db.execute("SELECT record_id, record_json FROM hive_records")}

    @staticmethod
    def _refs(value: dict[str, Any]) -> set[str]:
        return set(value.get("dependencies", [])) | set(value.get("evidence_refs", []))

    def _descendants(self, rows: dict[str, dict[str, Any]], roots: set[str]) -> set[str]:
        found: set[str] = set()
        frontier = set(roots)
        arms = {rows[root].get("experimental_arm", "default") for root in roots if root in rows}
        while frontier:
            current = frontier.pop()
            for record_id, value in rows.items():
                if (record_id not in found
                        and value.get("experimental_arm", "default") in arms
                        and self._refs(value) & {current}):
                    found.add(record_id)
                    frontier.add(record_id)
        return found

    def _check_cycle(self, rows: dict[str, dict[str, Any]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(record_id: str) -> None:
            if record_id in visiting:
                raise HiveMemoryError("dependency graph cycle")
            if record_id in visited:
                return
            visiting.add(record_id)
            for parent in self._refs(rows[record_id]):
                if parent in rows:
                    visit(parent)
            visiting.remove(record_id)
            visited.add(record_id)

        for record_id in rows:
            visit(record_id)

    def _validate_reachable(self, rows: dict[str, dict[str, Any]], root: str) -> set[str]:
        reachable: set[str] = set()
        visiting: set[str] = set()
        arm = rows[root].get("experimental_arm", "default")

        def visit(record_id: str) -> None:
            if record_id in visiting:
                raise HiveMemoryError("dependency graph cycle")
            if record_id in reachable:
                return
            value = rows.get(record_id)
            if value is None:
                raise HiveMemoryError("admission requires every dependency parent to exist")
            if value.get("status") in {"superseded", "invalidated", "contradicted"}:
                raise HiveMemoryError("admission blocked by invalidated dependency or contradiction")
            if value.get("experimental_arm", "default") != arm:
                raise HiveMemoryError("admission requires same experimental arm")
            visiting.add(record_id)
            for parent in self._refs(value):
                visit(parent)
            visiting.remove(record_id)
            reachable.add(record_id)

        visit(root)
        return reachable

    def replace_source(self, record: dict[str, Any], *, inject_failure: str | None = None) -> str:
        value = _validate_record(record)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_connection(db)
            rows = self._rows(db)
            self._validate_existing_refs(rows, value)
            old_ids = {record_id for record_id, item in rows.items() if _source_lineage_identity(item) == _source_lineage_identity(value)}
            successor = self._insert_db(db, value)
            if successor in old_ids:
                return successor
            rows[successor] = dict(value, status=self._status_for(value))
            # Treat the old source as replaced while checking the proposed graph.
            proposed = {rid: dict(item) for rid, item in rows.items()}
            for rid, item in proposed.items():
                if rid == successor:
                    continue
                refs = self._refs(item)
                if old_ids & refs:
                    item["dependencies"] = [successor if ref in old_ids else ref for ref in item.get("dependencies", [])]
                    item["evidence_refs"] = [successor if ref in old_ids else ref for ref in item.get("evidence_refs", [])]
            self._check_cycle(proposed)
            affected = self._descendants(rows, old_ids)
            mutations = len(old_ids) + len(affected)
            if mutations > _MAX_GRAPH_MUTATIONS:
                raise HiveMemoryError("graph mutation bound exceeded")
            for old_id in old_ids:
                db.execute("UPDATE hive_records SET status=?, record_json=? WHERE record_id=?",
                           ("superseded", json.dumps(dict(rows[old_id], status="superseded", supersession_cause="source replacement"), sort_keys=True, separators=(",", ":")), old_id))
            if inject_failure == "after-statuses":
                raise RuntimeError("injected source-change failure")
            for record_id in affected:
                if record_id not in old_ids and record_id != successor:
                    updated = dict(rows[record_id], status="invalidated", invalidation_cause="source replacement")
                    db.execute("UPDATE hive_records SET status=?, record_json=? WHERE record_id=?",
                               ("invalidated", json.dumps(updated, sort_keys=True, separators=(",", ":")), record_id))
            return successor

    def record_contradiction(self, record_ids: list[str], *, cause: str,
                             evaluator_id: str | None = None, evaluator_revision: str | None = None) -> None:
        ids = sorted(set(record_ids))
        if not ids or len(ids) > _MAX_DEPENDENCIES or not isinstance(cause, str) or not cause or len(cause) > _MAX_STRING:
            raise HiveMemoryError("contradiction requires bounded record IDs and cause")
        if type(evaluator_id) is not str or not evaluator_id or len(evaluator_id) > _MAX_STRING:
            raise HiveMemoryError("evaluator_id must be a bounded nonempty string")
        if type(evaluator_revision) is not str or not evaluator_revision or len(evaluator_revision) > _MAX_STRING:
            raise HiveMemoryError("evaluator_revision must be a bounded nonempty string")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_connection(db)
            rows = self._rows(db)
            if any(record_id not in rows for record_id in ids):
                raise HiveMemoryError("contradiction references missing record")
            arms = {rows[record_id].get("experimental_arm", "default") for record_id in ids}
            if len(arms) != 1:
                raise HiveMemoryError("contradiction cannot cross experimental arms")
            affected = self._descendants(rows, set(ids))
            if len(ids) + len(affected) > _MAX_GRAPH_MUTATIONS:
                raise HiveMemoryError("graph mutation bound exceeded")
            for record_id in ids:
                updated = dict(rows[record_id], status="contradicted", contradiction_cause=cause,
                               evaluator_id=evaluator_id, evaluator_revision=evaluator_revision)
                db.execute("UPDATE hive_records SET status=?, record_json=? WHERE record_id=?", ("contradicted", json.dumps(updated, sort_keys=True, separators=(",", ":")), record_id))
            for record_id in affected - set(ids):
                updated = dict(rows[record_id], status="invalidated", invalidation_cause=f"contradiction: {cause}")
                db.execute("UPDATE hive_records SET status=?, record_json=? WHERE record_id=?", ("invalidated", json.dumps(updated, sort_keys=True, separators=(",", ":")), record_id))

    def admit_conditional_procedure(self, record_id: str, *, evaluator_id: str, evaluator_revision: str) -> dict[str, Any]:
        if type(evaluator_id) is not str or not evaluator_id or len(evaluator_id) > _MAX_STRING:
            raise HiveMemoryError("evaluator_id must be a bounded nonempty string")
        if type(evaluator_revision) is not str or not evaluator_revision or len(evaluator_revision) > _MAX_STRING:
            raise HiveMemoryError("evaluator_revision must be a bounded nonempty string")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_connection(db)
            row = db.execute("SELECT record_json, kind, status FROM hive_records WHERE record_id=?", (record_id,)).fetchone()
            if row is None:
                raise HiveMemoryError("record not found")
            if row["status"] in {"invalidated", "contradicted", "superseded"}:
                raise HiveMemoryError("admission blocked by invalidated dependency or contradiction")
            if row["kind"] != "conditional_procedure" or row["status"] != "candidate":
                raise HiveMemoryError("only a candidate conditional procedure may be admitted")
            value = json.loads(row["record_json"])
            refs = sorted(set(value.get("evidence_refs", [])))
            if not refs:
                raise HiveMemoryError("admission requires evidence-backed conditional procedure")
            rows = self._rows(db)
            self._validate_reachable(rows, record_id)
            if any(rows[ref]["kind"] != "evidence_claim" or rows[ref]["status"] not in {"retained", "admitted"} for ref in refs):
                raise HiveMemoryError("admission requires evidence-backed conditional procedure")
            value.update({"status": "admitted", "evaluator_id": evaluator_id, "evaluator_revision": evaluator_revision})
            encoded = _json_bytes(value)
            db.execute("UPDATE hive_records SET record_json=?, status=? WHERE record_id=?", (encoded.decode(), "admitted", record_id))
        return value

    def get(self, record_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            self._validate_connection(db)
            row = db.execute("SELECT record_json FROM hive_records WHERE record_id=?", (record_id,)).fetchone()
        return None if row is None else json.loads(row[0])

    def list_records(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            self._validate_connection(db)
            rows = db.execute("SELECT record_json FROM hive_records ORDER BY rowid").fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_admitted(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            self._validate_connection(db)
            rows = db.execute("SELECT record_json FROM hive_records WHERE status='admitted' ORDER BY record_id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def retrieve(self, protocol: str, revision: int, applicability: str, query: str,
                 experimental_arm: str = "default", *, max_results: int = 8) -> list[dict[str, Any]]:
        if (type(protocol) is not str or not protocol or type(revision) is not int or revision < 0
                or type(applicability) is not str or not applicability or len(applicability) > _MAX_STRING
                or type(query) is not str or not query or len(query) > _MAX_STRING
                or type(experimental_arm) is not str or not experimental_arm or len(experimental_arm) > _MAX_STRING
                or len(protocol) > _MAX_STRING
                or type(max_results) is not int or max_results < 1 or max_results > 8):
            raise HiveMemoryError("invalid bounded memory query")
        with self._connect() as db:
            self._validate_connection(db)
            rows = db.execute("SELECT record_id, record_json FROM hive_records WHERE kind='conditional_procedure' AND status='admitted' ORDER BY record_id").fetchall()
            all_rows = self._rows(db)
        found = []
        needle = query.casefold()
        for row in rows:
            value = json.loads(row["record_json"])
            if (value.get("protocol") == protocol and value.get("revision") == revision
                    and value.get("applicability") == applicability
                    and value.get("experimental_arm", "default") == experimental_arm
                    and needle in json.dumps(value.get("content"), sort_keys=True, ensure_ascii=True).casefold()):
                try:
                    self._validate_reachable(all_rows, row["record_id"])
                except HiveMemoryError:
                    # Historical records stay inspectable, but a broken graph
                    # is unusable and must not poison unrelated scoped recall.
                    continue
                result = dict(value)
                result["record_id"] = row["record_id"]
                found.append(result)
        return found[:max_results]


def adapt_memory_query_bytes(store: HiveMemoryStore, raw: bytes, *, applicability: str,
                             experimental_arm: str = "default", max_results: int = 8) -> bytes:
    from backend.research_hive_contracts import deserialize_envelope, serialize_envelope
    try:
        query = deserialize_envelope(raw)
        if query["kind"] != "memory-query":
            raise HiveMemoryError("memory adapter requires memory-query")
        scope = query["scope"]
        evidence = store.retrieve(scope["protocol"], scope["revision"], applicability, query["query"], experimental_arm, max_results=max_results)
        source = {"source_id": "research-hive-memory", "revision": STORE_VERSION, "applicability": applicability, "dependencies": []}
        result = {"version": "hive-contract-v1", "kind": "memory-result", "event_id": "pending", "ordinal": query["ordinal"] + 1,
                  "scope": scope, "source": source,
                  "result": {"evidence": evidence, "external_state_recheck_required": True,
                             "message": "Memory is evidence only; recheck external state before acting."}, "found": bool(evidence)}
        from backend.research_hive_contracts import _event_id
        result["event_id"] = _event_id(result)
        return serialize_envelope("memory-result", result)
    except sqlite3.Error:
        raise
    except HiveMemoryError:
        raise
    except Exception as exc:
        raise HiveMemoryError("memory query failed closed") from exc


def consume_memory_result_bytes(raw: bytes) -> dict[str, Any]:
    from backend.research_hive_contracts import deserialize_envelope
    result = deserialize_envelope(raw)
    if result["kind"] != "memory-result" or result["result"].get("external_state_recheck_required") is not True:
        raise HiveMemoryError("invalid memory result")
    return result
