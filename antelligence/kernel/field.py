"""Signal fields: where deposited signals live until they expire.

A field is scoped: ``sense`` only returns signals from the caller's scope, so
experimental arms can never read each other's signals. Two backends ship with
the kernel:

* :class:`GridField` — spatial; "nearby" means within a Euclidean radius.
* :class:`BoardField` — topical; "nearby" means the same topic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Protocol, Tuple

from antelligence.kernel.signal import Signal


@dataclass(frozen=True)
class SenseQuery:
    """What an agent is able to perceive this tick (supplied by the world)."""

    pos: Optional[Tuple[float, ...]] = None
    radius: float = 0.0
    topic: Optional[str] = None
    kinds: Optional[FrozenSet[str]] = None
    max_results: int = 64

    def __post_init__(self) -> None:
        if self.pos is not None:
            object.__setattr__(self, "pos", tuple(float(c) for c in self.pos))
        if self.kinds is not None:
            object.__setattr__(self, "kinds", frozenset(self.kinds))
        if not math.isfinite(self.radius) or self.radius < 0:
            raise ValueError("radius must be finite and nonnegative")
        if self.max_results < 0:
            raise ValueError("max_results must be nonnegative")


class FieldFullError(RuntimeError):
    """The field reached its live-signal capacity."""


class SignalField(Protocol):
    def deposit(self, signal: Signal) -> bool: ...

    def sense(self, scope: str, tick: int, query: SenseQuery, *, exclude_sender: Optional[str] = None) -> List[Signal]: ...

    def expire(self, tick: int) -> List[Signal]: ...

    def snapshot(self, scope: str, tick: int) -> List[Signal]: ...


def _order(signals: Iterable[Signal]) -> List[Signal]:
    return sorted(signals, key=lambda s: (s.emitted_at, s.id))


class _StoreField:
    """Deduplicating, capacity-bounded, scope-partitioned storage."""

    def __init__(self, max_live: int = 100_000) -> None:
        if max_live < 1:
            raise ValueError("max_live must be positive")
        self.max_live = max_live
        self._signals: Dict[str, Signal] = {}

    def __len__(self) -> int:
        return len(self._signals)

    def deposit(self, signal: Signal) -> bool:
        """Store ``signal``; returns False for a duplicate id (replay)."""
        if signal.id in self._signals:
            return False
        if len(self._signals) >= self.max_live:
            raise FieldFullError(f"field holds {self.max_live} live signals")
        self._signals[signal.id] = signal
        return True

    def expire(self, tick: int) -> List[Signal]:
        """Drop signals whose last live tick is before ``tick + 1``."""
        gone = [s for s in self._signals.values() if s.expires_at <= tick]
        for signal in gone:
            del self._signals[signal.id]
        return _order(gone)

    def snapshot(self, scope: str, tick: int) -> List[Signal]:
        return _order(s for s in self._signals.values() if s.scope == scope and s.is_live(tick))

    def _candidates(self, scope: str, tick: int, query: SenseQuery, exclude_sender: Optional[str]) -> Iterable[Signal]:
        for signal in self._signals.values():
            if signal.scope != scope or not signal.is_live(tick):
                continue
            if exclude_sender is not None and signal.sender == exclude_sender:
                continue
            if query.kinds is not None and signal.kind not in query.kinds:
                continue
            yield signal


class GridField(_StoreField):
    """Spatial field. Signals without a position are invisible here."""

    def __init__(self, max_live: int = 100_000, decay_rate: float = 0.0) -> None:
        super().__init__(max_live)
        if not math.isfinite(decay_rate) or decay_rate < 0:
            raise ValueError("decay_rate must be finite and nonnegative")
        self.decay_rate = decay_rate

    def sense(self, scope: str, tick: int, query: SenseQuery, *, exclude_sender: Optional[str] = None) -> List[Signal]:
        if query.pos is None:
            return []
        hits = []
        for signal in self._candidates(scope, tick, query, exclude_sender):
            if signal.pos is None or len(signal.pos) != len(query.pos):
                continue
            distance = math.dist(signal.pos, query.pos)
            if distance <= query.radius:
                hits.append((distance, signal.emitted_at, signal.id, signal))
        hits.sort(key=lambda h: h[:3])
        return [h[3] for h in hits[: query.max_results]]

    def intensity_at(self, scope: str, tick: int, pos: Tuple[float, ...], kind: str, radius: float) -> float:
        """Pheromone-style scalar: amount x linear distance falloff x age decay."""
        total = 0.0
        query = SenseQuery(pos=pos, radius=radius, kinds=frozenset({kind}), max_results=1 << 30)
        for signal in self.sense(scope, tick, query):
            amount = signal.payload.get("amount", 1.0)
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                continue
            falloff = 1.0 if radius == 0 else 1.0 - math.dist(signal.pos, tuple(pos)) / radius
            age = tick - signal.emitted_at - 1
            total += float(amount) * falloff * math.exp(-self.decay_rate * age)
        return total


class BoardField(_StoreField):
    """Topical field. Signals without a topic are invisible here."""

    def sense(self, scope: str, tick: int, query: SenseQuery, *, exclude_sender: Optional[str] = None) -> List[Signal]:
        if query.topic is None:
            return []
        hits = [s for s in self._candidates(scope, tick, query, exclude_sender) if s.topic == query.topic]
        return _order(hits)[: query.max_results]
