"""Append-only, hash-chained event log: the single source of run provenance.

Every observation digest, intent, signal, admission decision and outcome is an
event. ``trace_hash`` chains them, so two runs have the same hash only if they
produced the same events in the same order. Wall-clock time is deliberately
excluded from hashed content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, List, Mapping, Optional

from antelligence.kernel.canonical import canonical_bytes, canonical_json, plain

GENESIS = "0" * 64

RUN_STARTED = "run_started"
OBSERVED = "observed"
DECIDED = "decided"
POLICY_FAILED = "policy_failed"
OUTCOME = "outcome"
SIGNAL_DEPOSITED = "signal_deposited"
SIGNAL_REJECTED = "signal_rejected"
SIGNAL_EXPIRED = "signal_expired"
INTENT_BLOCKED = "intent_blocked"
MEMORY_CHANGED = "memory_changed"
TICK_ENDED = "tick_ended"
RUN_FINISHED = "run_finished"


class EventLogError(ValueError):
    """A log failed integrity verification."""


@dataclass(frozen=True)
class Event:
    seq: int
    tick: int
    type: str
    agent_id: Optional[str]
    data: Mapping[str, Any]
    prev_hash: str
    hash: str

    def body(self) -> dict:
        return {"seq": self.seq, "tick": self.tick, "type": self.type, "agent_id": self.agent_id, "data": self.data}

    def to_dict(self) -> dict:
        return {**self.body(), "prev_hash": self.prev_hash, "hash": self.hash}


def _link(prev_hash: str, body: Mapping[str, Any]) -> str:
    return hashlib.sha256(prev_hash.encode("ascii") + canonical_bytes(body)).hexdigest()


class EventLog:
    def __init__(self, sink: Optional[Callable[[Event], Any]] = None) -> None:
        self._events: List[Event] = []
        self._sink = sink

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    @property
    def trace_hash(self) -> str:
        return self._events[-1].hash if self._events else GENESIS

    def append(self, type: str, tick: int, data: Mapping[str, Any], agent_id: Optional[str] = None) -> Event:
        prev = self.trace_hash
        body = {"seq": len(self._events), "tick": tick, "type": type, "agent_id": agent_id, "data": plain(dict(data))}
        event = Event(prev_hash=prev, hash=_link(prev, body), **body)
        self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        return event

    def of_type(self, type: str) -> List[Event]:
        return [e for e in self._events if e.type == type]

    def write_jsonl(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for event in self._events:
                handle.write(canonical_json(event.to_dict()) + "\n")

    @classmethod
    def read_jsonl(cls, path: Path) -> "EventLog":
        """Load and verify a log; any edited, dropped or reordered line fails."""
        log = cls()
        prev = GENESIS
        with Path(path).open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle):
                raw = json.loads(line)
                body = {k: raw[k] for k in ("seq", "tick", "type", "agent_id", "data")}
                if raw["seq"] != line_no or raw["prev_hash"] != prev or _link(prev, body) != raw["hash"]:
                    raise EventLogError(f"integrity check failed at line {line_no}")
                event = Event(prev_hash=prev, hash=raw["hash"], **body)
                log._events.append(event)
                prev = event.hash
        return log
