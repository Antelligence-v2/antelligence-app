"""Core contracts between the kernel, worlds and policies.

Locality is enforced by construction: a :class:`Policy` receives only a
:class:`LocalView` and has no reference to the world, the field or other agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, List, Mapping, Optional, Protocol, Tuple, Union, runtime_checkable

from antelligence.kernel.canonical import plain
from antelligence.kernel.field import SenseQuery
from antelligence.kernel.signal import Signal, SignalDraft

NOOP = "noop"


@dataclass(frozen=True)
class Observation:
    """What a world reveals to one agent: private data plus a sense query."""

    data: Mapping[str, Any]
    sense: SenseQuery = field(default_factory=SenseQuery)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", plain(dict(self.data)))


@dataclass(frozen=True)
class LocalView:
    """Everything a policy may use to decide. Nothing else is reachable."""

    agent_id: str
    tick: int
    revision: int
    seed: int
    observation: Mapping[str, Any]
    signals: Tuple[Signal, ...] = ()
    memory: Tuple[Any, ...] = ()


@dataclass(frozen=True)
class Intent:
    """A policy's decision: one action plus optional signals to emit."""

    action: str = NOOP
    params: Mapping[str, Any] = field(default_factory=dict)
    emit: Tuple[SignalDraft, ...] = ()
    rationale: Optional[str] = None
    cites: Tuple[str, ...] = ()  # evidence record ids this action relies on
    meta: Mapping[str, Any] = field(default_factory=dict)  # decision provenance (model, request hash, tokens)

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action:
            raise ValueError("action must be a non-empty string")
        object.__setattr__(self, "params", plain(dict(self.params)))
        emit = tuple(self.emit)
        if not all(isinstance(d, SignalDraft) for d in emit):
            raise ValueError("emit must contain SignalDraft objects")
        object.__setattr__(self, "emit", emit)
        cites = tuple(self.cites)
        if not all(isinstance(c, str) and c for c in cites):
            raise ValueError("cites must be non-empty strings")
        object.__setattr__(self, "cites", cites)
        object.__setattr__(self, "meta", plain(dict(self.meta)))

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "params": self.params,
            "emit": len(self.emit),
            "rationale": self.rationale,
            "cites": list(self.cites),
            "meta": self.meta,
        }


@dataclass(frozen=True)
class Outcome:
    """The world's (model-free) judgement of an applied intent."""

    accepted: bool
    reason: Optional[str] = None
    effects: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", plain(dict(self.effects)))

    def to_dict(self) -> dict:
        return {"accepted": self.accepted, "reason": self.reason, "effects": self.effects}


@runtime_checkable
class World(Protocol):
    """A task environment. Owns state, visibility, action semantics and score."""

    @property
    def revision(self) -> int:
        """Monotone counter; bump when state that signals may describe changes."""
        ...

    def agents(self) -> List[str]: ...

    def observe(self, agent_id: str, tick: int) -> Observation: ...

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome: ...

    def step_environment(self, tick: int) -> None: ...

    def metrics(self) -> Dict[str, Any]: ...

    def done(self, tick: int) -> bool: ...

    def describe(self) -> Dict[str, Any]:
        """Canonical configuration; part of the run's config hash."""
        ...


DecideResult = Union[Intent, Awaitable[Intent]]


@runtime_checkable
class Policy(Protocol):
    """An agent brain. May be sync or return an awaitable (for LLM calls)."""

    def decide(self, view: LocalView) -> DecideResult: ...

    def describe(self) -> Dict[str, Any]: ...
