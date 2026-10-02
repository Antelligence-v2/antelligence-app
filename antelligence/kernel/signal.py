"""The Signal envelope: one type for pheromones and LLM messages alike.

Agents never construct a :class:`Signal` directly. A policy returns
:class:`SignalDraft` objects; the scheduler stamps sender, scope, revision and
emission tick, so an agent cannot forge another agent's identity or address a
different experimental arm.

Visibility is deferred: a signal emitted at tick ``t`` is live for ticks
``t + 1 .. t + ttl`` inclusive. No agent can see a same-tick signal, which
makes decision order irrelevant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from antelligence.kernel.canonical import canonical_bytes, content_hash, plain

KIND_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_PAYLOAD_BYTES = 4096
MAX_REFERENCES = 16
MAX_TTL = 10_000


class SignalError(ValueError):
    """A signal or draft violates the envelope contract."""


def _refs(values: Sequence[str], label: str) -> Tuple[str, ...]:
    refs = tuple(values)
    if len(refs) > MAX_REFERENCES:
        raise SignalError(f"{label}: at most {MAX_REFERENCES} references")
    for ref in refs:
        if not isinstance(ref, str) or not ref:
            raise SignalError(f"{label}: references must be non-empty strings")
    if len(set(refs)) != len(refs):
        raise SignalError(f"{label}: duplicate references")
    return refs


def _where(pos: Optional[Sequence[float]], topic: Optional[str]) -> Tuple[Optional[Tuple[float, ...]], Optional[str]]:
    if (pos is None) == (topic is None):
        raise SignalError("exactly one of pos or topic is required")
    if pos is not None:
        coords = tuple(float(c) for c in pos)
        if not 1 <= len(coords) <= 3:
            raise SignalError("pos must have 1 to 3 coordinates")
        return coords, None
    if not isinstance(topic, str) or not topic:
        raise SignalError("topic must be a non-empty string")
    return None, topic


def _payload(payload: Optional[Mapping[str, Any]]) -> dict:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise SignalError("payload must be an object")
    try:
        detached = plain(dict(payload))
        size = len(canonical_bytes(detached))
    except ValueError as exc:
        raise SignalError(f"payload is not canonical JSON: {exc}") from exc
    if size > MAX_PAYLOAD_BYTES:
        raise SignalError(f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
    return detached


def _ttl(ttl: int) -> int:
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 1 <= ttl <= MAX_TTL:
        raise SignalError(f"ttl must be an integer in 1..{MAX_TTL}")
    return ttl


def _kind(kind: str) -> str:
    if not isinstance(kind, str) or not KIND_RE.match(kind):
        raise SignalError(f"invalid kind {kind!r}")
    return kind


@dataclass(frozen=True)
class SignalDraft:
    """What a policy asks to emit; identity fields are stamped later."""

    kind: str
    pos: Optional[Tuple[float, ...]] = None
    topic: Optional[str] = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    cites: Tuple[str, ...] = ()
    parent_ids: Tuple[str, ...] = ()
    ttl: int = 1

    def __post_init__(self) -> None:
        _kind(self.kind)
        pos, topic = _where(self.pos, self.topic)
        object.__setattr__(self, "pos", pos)
        object.__setattr__(self, "topic", topic)
        object.__setattr__(self, "payload", _payload(self.payload))
        object.__setattr__(self, "cites", _refs(self.cites, "cites"))
        object.__setattr__(self, "parent_ids", _refs(self.parent_ids, "parent_ids"))
        _ttl(self.ttl)


@dataclass(frozen=True, eq=False)
class Signal:
    """An emitted, stamped, content-addressed signal."""

    sender: str
    scope: str
    kind: str
    emitted_at: int
    revision: int
    ttl: int
    pos: Optional[Tuple[float, ...]] = None
    topic: Optional[str] = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    cites: Tuple[str, ...] = ()
    parent_ids: Tuple[str, ...] = ()
    id: str = field(init=False)

    def __post_init__(self) -> None:
        for label in ("sender", "scope"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value:
                raise SignalError(f"{label} must be a non-empty string")
        for label in ("emitted_at", "revision"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SignalError(f"{label} must be a nonnegative integer")
        _kind(self.kind)
        _ttl(self.ttl)
        pos, topic = _where(self.pos, self.topic)
        object.__setattr__(self, "pos", pos)
        object.__setattr__(self, "topic", topic)
        object.__setattr__(self, "payload", _payload(self.payload))
        object.__setattr__(self, "cites", _refs(self.cites, "cites"))
        object.__setattr__(self, "parent_ids", _refs(self.parent_ids, "parent_ids"))
        object.__setattr__(self, "id", content_hash(self._body()))

    @classmethod
    def stamp(cls, draft: SignalDraft, *, sender: str, scope: str, tick: int, revision: int) -> "Signal":
        return cls(
            sender=sender,
            scope=scope,
            kind=draft.kind,
            emitted_at=tick,
            revision=revision,
            ttl=draft.ttl,
            pos=draft.pos,
            topic=draft.topic,
            payload=draft.payload,
            cites=draft.cites,
            parent_ids=draft.parent_ids,
        )

    @property
    def expires_at(self) -> int:
        return self.emitted_at + self.ttl

    def is_live(self, tick: int) -> bool:
        """Live strictly after emission and up to and including ``expires_at``."""
        return self.emitted_at < tick <= self.expires_at

    def _body(self) -> dict:
        return {
            "sender": self.sender,
            "scope": self.scope,
            "kind": self.kind,
            "emitted_at": self.emitted_at,
            "revision": self.revision,
            "ttl": self.ttl,
            "pos": list(self.pos) if self.pos is not None else None,
            "topic": self.topic,
            "payload": self.payload,
            "cites": list(self.cites),
            "parent_ids": list(self.parent_ids),
        }

    def to_dict(self) -> dict:
        return {"id": self.id, **plain(self._body())}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Signal":
        signal = cls(
            sender=data["sender"],
            scope=data["scope"],
            kind=data["kind"],
            emitted_at=data["emitted_at"],
            revision=data["revision"],
            ttl=data["ttl"],
            pos=tuple(data["pos"]) if data.get("pos") is not None else None,
            topic=data.get("topic"),
            payload=data.get("payload") or {},
            cites=tuple(data.get("cites") or ()),
            parent_ids=tuple(data.get("parent_ids") or ()),
        )
        if "id" in data and data["id"] != signal.id:
            raise SignalError("signal id does not match its content")
        return signal

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Signal) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
