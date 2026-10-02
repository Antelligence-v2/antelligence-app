"""Signal admission: what may enter a field (the paper's bounded transport).

The scheduler already guarantees identity (sender/scope are stamped) and
de-duplicates identical signals. :class:`AdmissionPolicy` adds the rules that
make shared signals safe to act on:

* **kind / schema** — only declared kinds; optional per-kind payload validator.
* **ttl bound** — no signal may outlive ``max_ttl``.
* **causality** — every ``parent_id`` must be a previously admitted signal in
  the same scope, emitted strictly earlier.
* **citations** — every ``cite`` must resolve to a usable evidence record.
* **budgets** — per-sender per-tick, per-topic per-tick, and per-run totals.

Rejections are returned as short reason codes and logged by the scheduler.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from antelligence.kernel.signal import Signal

PayloadCheck = Callable[[Mapping[str, Any]], Optional[str]]


class AdmissionPolicy:
    def __init__(
        self,
        *,
        kinds: Optional[Mapping[str, Optional[PayloadCheck]]] = None,
        max_ttl: Optional[int] = None,
        require_known_parents: bool = True,
        cite_resolver: Optional[Callable[[str], bool]] = None,
        max_per_sender_per_tick: Optional[int] = None,
        max_per_topic_per_tick: Optional[int] = None,
        max_total: Optional[int] = None,
    ) -> None:
        self.kinds = None if kinds is None else dict(kinds)
        self.max_ttl = max_ttl
        self.require_known_parents = require_known_parents
        self.cite_resolver = cite_resolver
        self.max_per_sender_per_tick = max_per_sender_per_tick
        self.max_per_topic_per_tick = max_per_topic_per_tick
        self.max_total = max_total
        self._admitted: Dict[str, Tuple[str, int]] = {}  # id -> (scope, emitted_at)
        self._tick = -1
        self._per_sender: Counter = Counter()
        self._per_topic: Counter = Counter()
        self._total: Counter = Counter()

    def check(self, signal: Signal, tick: int) -> Optional[str]:
        if tick != self._tick:
            self._tick = tick
            self._per_sender.clear()
            self._per_topic.clear()

        if self.kinds is not None:
            if signal.kind not in self.kinds:
                return "kind_not_allowed"
            validator = self.kinds[signal.kind]
            if validator is not None:
                problem = validator(signal.payload)
                if problem:
                    return f"bad_payload:{problem}"[:80]
        if self.max_ttl is not None and signal.ttl > self.max_ttl:
            return "ttl_too_long"
        if self.require_known_parents:
            for parent in signal.parent_ids:
                known = self._admitted.get(parent)
                if known is None:
                    return "unknown_parent"
                scope, emitted_at = known
                if scope != signal.scope:
                    return "parent_out_of_scope"
                if emitted_at >= signal.emitted_at:
                    return "parent_not_earlier"
        if signal.cites:
            if self.cite_resolver is None:
                return "citations_unverifiable"
            for cite in signal.cites:
                if not self.cite_resolver(cite):
                    return "citation_not_usable"
        sender_key = (signal.scope, signal.sender)
        if self.max_per_sender_per_tick is not None and self._per_sender[sender_key] >= self.max_per_sender_per_tick:
            return "sender_budget_exceeded"
        topic_key = (signal.scope, signal.topic)
        if (
            signal.topic is not None
            and self.max_per_topic_per_tick is not None
            and self._per_topic[topic_key] >= self.max_per_topic_per_tick
        ):
            return "topic_budget_exceeded"
        if self.max_total is not None and self._total[signal.scope] >= self.max_total:
            return "run_budget_exceeded"

        self._per_sender[sender_key] += 1
        if signal.topic is not None:
            self._per_topic[topic_key] += 1
        self._total[signal.scope] += 1
        self._admitted[signal.id] = (signal.scope, signal.emitted_at)
        return None

    def describe(self) -> dict:
        return {
            "kinds": None if self.kinds is None else sorted(self.kinds),
            "max_ttl": self.max_ttl,
            "require_known_parents": self.require_known_parents,
            "citations": self.cite_resolver is not None,
            "max_per_sender_per_tick": self.max_per_sender_per_tick,
            "max_per_topic_per_tick": self.max_per_topic_per_tick,
            "max_total": self.max_total,
        }
