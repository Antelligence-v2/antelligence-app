"""Evidence memory: what the swarm knows, where it came from, and whether it
may still be trusted.

Rules enforced here (from the DeSci paper, section 3.2):

1. Agents may act only on **admitted** records.
2. **Outcome** records may only be written by an authority (world/verifier).
3. Replacing a source (bumping a subject's revision) **invalidates** every record
   about the older revision and **cascades** to all dependents.
4. A **contradiction** takes both records out of use and invalidates their
   dependents until an authority resolves it.
5. Records never cross scopes (experimental arms).

A claim can require confirmations: it is admitted once ``min_confirmations``
distinct authors have proposed identical content about the same subject
revision. Every status change is recorded and can be drained for the event log.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

from antelligence.kernel.canonical import canonical_json, content_hash, plain

CLAIM = "claim"
PROCEDURE = "procedure"
OUTCOME = "outcome"
KINDS = frozenset({CLAIM, PROCEDURE, OUTCOME})

CANDIDATE = "candidate"
ADMITTED = "admitted"
REJECTED = "rejected"
INVALIDATED = "invalidated"
CONTRADICTED = "contradicted"

WORLD = "world"
VERIFIER = "verifier"

_SCHEMA_VERSION = 1
MAX_BODY_BYTES = 65_536  # same bounds as research_hive_memory
MAX_DEPENDENCIES = 128
_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL, author TEXT NOT NULL,
    subject TEXT NOT NULL, subject_rev INTEGER NOT NULL, body TEXT NOT NULL,
    depends_on TEXT NOT NULL, content_key TEXT NOT NULL, status TEXT NOT NULL,
    created_tick INTEGER NOT NULL, updated_tick INTEGER NOT NULL, reason TEXT
);
CREATE INDEX IF NOT EXISTS records_scope_subject ON records(scope, subject, status);
CREATE INDEX IF NOT EXISTS records_content ON records(scope, content_key);
CREATE TABLE IF NOT EXISTS edges (child TEXT NOT NULL, parent TEXT NOT NULL, PRIMARY KEY (child, parent));
CREATE INDEX IF NOT EXISTS edges_parent ON edges(parent);
CREATE TABLE IF NOT EXISTS subjects (
    scope TEXT NOT NULL, subject TEXT NOT NULL, rev INTEGER NOT NULL, changed_tick INTEGER NOT NULL DEFAULT -1,
    PRIMARY KEY (scope, subject)
);
CREATE TABLE IF NOT EXISTS contradictions (
    id TEXT PRIMARY KEY, scope TEXT NOT NULL, a TEXT NOT NULL, b TEXT NOT NULL,
    author TEXT NOT NULL, tick INTEGER NOT NULL, resolved_by TEXT, winner TEXT
);
"""


class EvidenceError(RuntimeError):
    """Base class for evidence-memory refusals."""


class TrustError(EvidenceError):
    """The author is not allowed to write this kind of record."""


class StaleError(EvidenceError):
    """The record describes an older revision of its subject."""


class IntegrityError(EvidenceError):
    """A stored record no longer matches its content-derived id (tampering)."""


class DependencyError(EvidenceError):
    """A dependency is missing, crosses scope, or is not admitted."""


class StatusError(EvidenceError):
    """The requested transition is not allowed from the current status."""


@dataclass(frozen=True)
class Record:
    id: str
    scope: str
    kind: str
    author: str
    subject: str
    subject_rev: int
    body: Mapping[str, Any]
    depends_on: Tuple[str, ...]
    content_key: str
    status: str
    created_tick: int
    updated_tick: int
    reason: Optional[str] = None

    @property
    def usable(self) -> bool:
        return self.status == ADMITTED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scope": self.scope,
            "kind": self.kind,
            "author": self.author,
            "subject": self.subject,
            "subject_rev": self.subject_rev,
            "body": plain(dict(self.body)),
            "depends_on": list(self.depends_on),
            "status": self.status,
            "created_tick": self.created_tick,
            "updated_tick": self.updated_tick,
            "reason": self.reason,
        }


def _row_to_record(row: sqlite3.Row) -> Record:
    return Record(
        id=row["id"],
        scope=row["scope"],
        kind=row["kind"],
        author=row["author"],
        subject=row["subject"],
        subject_rev=row["subject_rev"],
        body=json.loads(row["body"]),
        depends_on=tuple(json.loads(row["depends_on"])),
        content_key=row["content_key"],
        status=row["status"],
        created_tick=row["created_tick"],
        updated_tick=row["updated_tick"],
        reason=row["reason"],
    )


class EvidenceMemory:
    def __init__(
        self,
        path: str = ":memory:",
        *,
        authorities: FrozenSet[str] = frozenset({WORLD, VERIFIER}),
        min_confirmations: int = 1,
    ) -> None:
        if min_confirmations < 1:
            raise ValueError("min_confirmations must be at least 1")
        self.authorities = frozenset(authorities)
        self.min_confirmations = min_confirmations
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, _SCHEMA_VERSION):
            raise EvidenceError(f"unsupported memory schema version {version}")
        self._db.executescript(_SCHEMA)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(subjects)")}
        if "changed_tick" not in columns:  # stores created before changed_tick existed
            self._db.execute("ALTER TABLE subjects ADD COLUMN changed_tick INTEGER NOT NULL DEFAULT -1")
        self._db.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
        self._pending: List[dict] = []
        self.verify_integrity()

    def verify_integrity(self) -> int:
        """Recompute every record id from its stored content; raise on any mismatch."""
        count = 0
        for row in self._db.execute("SELECT * FROM records"):
            record = _row_to_record(row)
            content = {"scope": record.scope, "kind": record.kind, "subject": record.subject,
                       "subject_rev": record.subject_rev, "body": record.body, "depends_on": list(record.depends_on)}
            if content_hash({**content, "author": record.author}) != record.id or content_hash(content) != record.content_key:
                raise IntegrityError(f"record {record.id[:12]} does not match its content")
            count += 1
        return count

    def close(self) -> None:
        self._db.close()

    # --------------------------------------------------------------- subjects
    def subject_rev(self, scope: str, subject: str) -> int:
        row = self._db.execute("SELECT rev FROM subjects WHERE scope=? AND subject=?", (scope, subject)).fetchone()
        return row["rev"] if row else 0

    def subject_changed_at(self, scope: str, subject: str) -> Optional[int]:
        """Tick of the subject's most recent source replacement, if any."""
        row = self._db.execute("SELECT changed_tick FROM subjects WHERE scope=? AND subject=?",
                               (scope, subject)).fetchone()
        return None if row is None or row["changed_tick"] < 0 else row["changed_tick"]

    def replace_source(self, scope: str, subject: str, tick: int, new_rev: Optional[int] = None,
                       reason: str = "source_replaced") -> List[str]:
        """Advance ``subject`` to a new revision; invalidate everything older."""
        current = self.subject_rev(scope, subject)
        new_rev = current + 1 if new_rev is None else new_rev
        if new_rev <= current:
            raise StaleError(f"{subject}: revision {new_rev} is not newer than {current}")
        with self._tx():
            self._db.execute(
                "INSERT INTO subjects(scope, subject, rev, changed_tick) VALUES (?,?,?,?) "
                "ON CONFLICT(scope, subject) DO UPDATE SET rev=excluded.rev, changed_tick=excluded.changed_tick",
                (scope, subject, new_rev, tick),
            )
            rows = self._db.execute(
                "SELECT id FROM records WHERE scope=? AND subject=? AND subject_rev<? AND status IN (?,?,?)",
                (scope, subject, new_rev, CANDIDATE, ADMITTED, CONTRADICTED),
            ).fetchall()
            return self._invalidate_many([r["id"] for r in rows], tick, reason)

    # ---------------------------------------------------------------- writing
    def propose(
        self,
        *,
        scope: str,
        kind: str,
        author: str,
        subject: str,
        body: Mapping[str, Any],
        tick: int,
        depends_on: Sequence[str] = (),
        subject_rev: Optional[int] = None,
        observed_at: Optional[int] = None,
    ) -> Record:
        """Add a record. ``observed_at`` is the tick the author observed the subject;
        an observation made at or before the subject's last source change is stale
        (agents observe at the start of a tick, before any action in that tick)."""
        if kind not in KINDS:
            raise ValueError(f"unknown record kind {kind!r}")
        if not scope or not author or not subject:
            raise ValueError("scope, author and subject are required")
        if kind == OUTCOME and author not in self.authorities:
            raise TrustError(f"{author!r} may not write outcome records")
        current = self.subject_rev(scope, subject)
        rev = current if subject_rev is None else subject_rev
        if rev < current:
            raise StaleError(f"{subject}: proposed revision {rev} is older than current {current}")
        if rev > current:
            raise StaleError(f"{subject}: proposed revision {rev} is ahead of current {current}")
        changed_at = self.subject_changed_at(scope, subject)
        if observed_at is not None and changed_at is not None and observed_at <= changed_at:
            raise StaleError(f"{subject}: observed at tick {observed_at}, before its source changed at tick {changed_at}")
        deps = tuple(sorted(set(depends_on)))
        if len(deps) > MAX_DEPENDENCIES:
            raise ValueError(f"at most {MAX_DEPENDENCIES} dependencies")
        for dep in deps:
            parent = self.get(dep)
            if parent is None:
                raise DependencyError(f"unknown dependency {dep}")
            if parent.scope != scope:
                raise DependencyError(f"dependency {dep} belongs to another scope")
            if parent.status != ADMITTED:
                raise DependencyError(f"dependency {dep} is {parent.status}")
        detached = plain(dict(body))
        if len(canonical_json(detached).encode()) > MAX_BODY_BYTES:
            raise ValueError(f"record body exceeds {MAX_BODY_BYTES} bytes")
        content = {"scope": scope, "kind": kind, "subject": subject, "subject_rev": rev, "body": detached, "depends_on": list(deps)}
        content_key = content_hash(content)
        record_id = content_hash({**content, "author": author})
        existing = self.get(record_id)
        if existing is not None:
            return existing
        with self._tx():
            self._db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record_id, scope, kind, author, subject, rev, canonical_json(detached), canonical_json(list(deps)),
                 content_key, CANDIDATE, tick, tick, None),
            )
            self._db.executemany("INSERT INTO edges(child, parent) VALUES (?,?)", [(record_id, d) for d in deps])
            self._note(record_id, subject, None, CANDIDATE, f"proposed_by:{author}", tick)
            if author in self.authorities or self._confirmations(scope, content_key) >= self.min_confirmations:
                self._admit_group(scope, content_key, tick, "authority" if author in self.authorities else "confirmed")
        return self.get(record_id)  # type: ignore[return-value]

    def admit(self, record_id: str, tick: int, reason: str = "manual") -> Record:
        record = self._require(record_id)
        if record.status != CANDIDATE:
            raise StatusError(f"cannot admit a {record.status} record")
        if record.subject_rev != self.subject_rev(record.scope, record.subject):
            raise StaleError(f"{record.subject}: record revision is no longer current")
        for dep in record.depends_on:
            if self._require(dep).status != ADMITTED:
                raise DependencyError(f"dependency {dep} is not admitted")
        with self._tx():
            self._set(record, ADMITTED, tick, reason)
        return self._require(record_id)

    def reject(self, record_id: str, tick: int, reason: str) -> Record:
        record = self._require(record_id)
        if record.status != CANDIDATE:
            raise StatusError(f"cannot reject a {record.status} record")
        with self._tx():
            self._set(record, REJECTED, tick, reason)
        return self._require(record_id)

    def invalidate(self, record_id: str, tick: int, reason: str) -> List[str]:
        self._require(record_id)
        with self._tx():
            return self._invalidate_many([record_id], tick, reason)

    def contradict(self, a: str, b: str, *, author: str, tick: int) -> str:
        """Both records leave service; their dependents are invalidated."""
        ra, rb = self._require(a), self._require(b)
        if ra.scope != rb.scope:
            raise DependencyError("cannot contradict across scopes")
        if a == b:
            raise ValueError("a record cannot contradict itself")
        contradiction_id = content_hash({"a": min(a, b), "b": max(a, b), "author": author})
        with self._tx():
            self._db.execute(
                "INSERT OR IGNORE INTO contradictions(id, scope, a, b, author, tick) VALUES (?,?,?,?,?,?)",
                (contradiction_id, ra.scope, a, b, author, tick),
            )
            for record in (ra, rb):
                if record.status in (CANDIDATE, ADMITTED):
                    self._set(record, CONTRADICTED, tick, f"contradiction:{contradiction_id[:12]}")
                self._invalidate_many(self._dependents(record.id), tick, "dependency_contradicted")
        return contradiction_id

    def resolve(self, contradiction_id: str, *, winner: str, author: str, tick: int) -> Record:
        if author not in self.authorities:
            raise TrustError(f"{author!r} may not resolve contradictions")
        row = self._db.execute("SELECT * FROM contradictions WHERE id=?", (contradiction_id,)).fetchone()
        if row is None or row["resolved_by"] is not None:
            raise StatusError("unknown or already resolved contradiction")
        if winner not in (row["a"], row["b"]):
            raise ValueError("winner must be one side of the contradiction")
        loser = row["b"] if winner == row["a"] else row["a"]
        with self._tx():
            self._db.execute("UPDATE contradictions SET resolved_by=?, winner=? WHERE id=?", (author, winner, contradiction_id))
            self._invalidate_many([loser], tick, "lost_contradiction")
            record = self._require(winner)
            current = record.subject_rev == self.subject_rev(record.scope, record.subject)
            deps_ok = all(self._require(d).status == ADMITTED for d in record.depends_on)
            still_disputed = self._db.execute(
                "SELECT 1 FROM contradictions WHERE resolved_by IS NULL AND id<>? AND (a=? OR b=?) LIMIT 1",
                (contradiction_id, winner, winner),
            ).fetchone() is not None
            if record.status == CONTRADICTED and not still_disputed:
                if current and deps_ok:
                    self._set(record, ADMITTED, tick, "won_contradiction")
                else:
                    self._set(record, INVALIDATED, tick, "won_contradiction_but_stale")
        return self._require(winner)

    # ---------------------------------------------------------------- reading
    def get(self, record_id: str) -> Optional[Record]:
        row = self._db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        return _row_to_record(row) if row else None

    def is_usable(self, record_id: str) -> bool:
        record = self.get(record_id)
        return record is not None and record.usable

    def recall(
        self,
        scope: str,
        *,
        subjects: Optional[Iterable[str]] = None,
        kinds: Optional[Iterable[str]] = None,
        limit: int = 50,
    ) -> List[Record]:
        """Admitted records only; one per distinct content; oldest first."""
        sql = "SELECT * FROM records WHERE scope=? AND status=?"
        args: List[Any] = [scope, ADMITTED]
        if subjects is not None:
            subject_list = sorted(set(subjects))
            if not subject_list:
                return []
            sql += f" AND subject IN ({','.join('?' * len(subject_list))})"
            args += subject_list
        if kinds is not None:
            kind_list = sorted(set(kinds))
            sql += f" AND kind IN ({','.join('?' * len(kind_list))})"
            args += kind_list
        sql += " ORDER BY created_tick, id"
        seen, out = set(), []
        for row in self._db.execute(sql, args):
            if row["content_key"] in seen:
                continue
            seen.add(row["content_key"])
            out.append(_row_to_record(row))
            if len(out) >= limit:
                break
        return out

    def count(self, scope: str, status: Optional[str] = None) -> int:
        if status is None:
            return self._db.execute("SELECT COUNT(*) FROM records WHERE scope=?", (scope,)).fetchone()[0]
        return self._db.execute("SELECT COUNT(*) FROM records WHERE scope=? AND status=?", (scope, status)).fetchone()[0]

    def note_refusal(self, subject: str, reason: str, tick: int) -> None:
        """Record a proposal that never became a record (for the event log)."""
        self._note(None, subject, None, REJECTED, reason, tick)

    def drain_transitions(self) -> List[dict]:
        pending, self._pending = self._pending, []
        return pending

    # ------------------------------------------------------------- internals
    def _tx(self):
        db = self._db

        class _Tx:
            def __enter__(self_inner):
                self_inner.outer = db.in_transaction
                if not self_inner.outer:
                    db.execute("BEGIN")

            def __exit__(self_inner, exc_type, exc, tb):
                if self_inner.outer:
                    return False
                db.execute("ROLLBACK" if exc_type else "COMMIT")
                return False

        return _Tx()

    def _require(self, record_id: str) -> Record:
        record = self.get(record_id)
        if record is None:
            raise DependencyError(f"unknown record {record_id}")
        return record

    def _confirmations(self, scope: str, content_key: str) -> int:
        return self._db.execute(
            "SELECT COUNT(DISTINCT author) FROM records WHERE scope=? AND content_key=? AND status IN (?,?)",
            (scope, content_key, CANDIDATE, ADMITTED),
        ).fetchone()[0]

    def _admit_group(self, scope: str, content_key: str, tick: int, reason: str) -> None:
        rows = self._db.execute(
            "SELECT * FROM records WHERE scope=? AND content_key=? AND status=?", (scope, content_key, CANDIDATE)
        ).fetchall()
        for row in rows:
            self._set(_row_to_record(row), ADMITTED, tick, reason)

    def _dependents(self, record_id: str) -> List[str]:
        return [r["child"] for r in self._db.execute("SELECT child FROM edges WHERE parent=? ORDER BY child", (record_id,))]

    def _invalidate_many(self, roots: Sequence[str], tick: int, reason: str) -> List[str]:
        """Breadth-first cascade; returns every record newly invalidated."""
        changed: List[str] = []
        queue = [(rid, reason) for rid in roots]
        visited = set()
        while queue:
            rid, why = queue.pop(0)
            if rid in visited:
                continue
            visited.add(rid)
            record = self._require(rid)
            if record.status in (CANDIDATE, ADMITTED, CONTRADICTED):
                self._set(record, INVALIDATED, tick, why)
                changed.append(rid)
            queue.extend((child, "dependency_invalidated") for child in self._dependents(rid))
        return changed

    def _set(self, record: Record, status: str, tick: int, reason: str) -> None:
        self._db.execute(
            "UPDATE records SET status=?, updated_tick=?, reason=? WHERE id=?", (status, tick, reason, record.id)
        )
        self._note(record.id, record.subject, record.status, status, reason, tick)

    def _note(self, record_id: Optional[str], subject: str, old: Optional[str], new: str, reason: str, tick: int) -> None:
        self._pending.append({"record_id": record_id, "subject": subject, "from": old, "to": new, "reason": reason, "tick": tick})


class ScopedRecall:
    """Scheduler memory reader: admitted records relevant to one agent.

    ``select`` maps (agent_id, observation) to the subjects the agent may
    recall; ``None`` means every subject in scope (use only in small worlds).
    """

    def __init__(
        self,
        memory: EvidenceMemory,
        select: Optional[Callable[[str, Mapping[str, Any]], Iterable[str]]] = None,
        *,
        kinds: Optional[Iterable[str]] = None,
        limit: int = 32,
    ) -> None:
        self.memory = memory
        self.select = select
        self.kinds = None if kinds is None else frozenset(kinds)
        self.limit = limit

    def recall_for(self, agent_id: str, scope: str, tick: int, observation: Mapping[str, Any]) -> Tuple[Record, ...]:
        subjects = None if self.select is None else list(self.select(agent_id, observation))
        return tuple(self.memory.recall(scope, subjects=subjects, kinds=self.kinds, limit=self.limit))


SubjectOf = Callable[[Any], Optional[str]]


class EvidenceRecorder:
    """Turns admitted signals into claims and world outcomes into facts.

    * A deposited signal whose kind is in ``claim_kinds`` becomes a claim by
      its sender about ``claim_kinds[kind](signal)``. Its ``cites`` that name
      memory records become dependencies.
    * An accepted outcome may carry ``effects["subjects_changed"]`` (subjects
      whose source is replaced) and ``effects["facts"]`` (authority-written
      outcome records, each ``{"subject": ..., "body": {...}}``).
    """

    def __init__(self, memory: EvidenceMemory, claim_kinds: Mapping[str, SubjectOf]) -> None:
        self.memory = memory
        self.claim_kinds = dict(claim_kinds)

    def on_signal(self, signal: Any, tick: int) -> List[dict]:
        subject_of = self.claim_kinds.get(signal.kind)
        if subject_of is not None:
            subject = subject_of(signal)
            if subject:
                deps = [c for c in signal.cites if self.memory.get(c) is not None]
                body = {"kind": signal.kind, "payload": signal.payload,
                        "pos": list(signal.pos) if signal.pos else None, "topic": signal.topic}
                try:
                    self.memory.propose(scope=signal.scope, kind=CLAIM, author=signal.sender, subject=subject,
                                        body=body, depends_on=deps, tick=tick, observed_at=signal.emitted_at)
                except EvidenceError as exc:
                    self.memory.note_refusal(subject, f"{type(exc).__name__}: {exc}", tick)
        return self.memory.drain_transitions()

    def on_outcome(self, scope: str, agent_id: str, intent: Any, outcome: Any, tick: int) -> List[dict]:
        if outcome.accepted:
            for subject in outcome.effects.get("subjects_changed", ()) or ():
                self.memory.replace_source(scope, str(subject), tick)
            for fact in outcome.effects.get("facts", ()) or ():
                self.memory.propose(scope=scope, kind=OUTCOME, author=WORLD, subject=str(fact["subject"]),
                                    body=fact.get("body", {}), tick=tick)
        return self.memory.drain_transitions()
