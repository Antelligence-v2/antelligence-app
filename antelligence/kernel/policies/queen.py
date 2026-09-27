"""The Queen as a signal emitter, not an omniscient planner.

The legacy Queen computed directions from every hypoxic cell in the tumor —
global ground truth no agent should have. Here the Queen is an ordinary agent:
it sees only what workers reported (``report_kind`` signals in its sensing
range, plus admitted memory claims), clusters those reports, and emits
``recruit`` signals toward the densest reported regions. Workers are free to
follow or ignore them. Whether this beats no Queen is now a clean A/B.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import NOOP, Intent, LocalView


class QueenEmitter:
    def __init__(
        self,
        *,
        report_kind: str = "found",
        recruit_kind: str = "recruit",
        cell_size: float = 50.0,
        top_k: int = 1,
        min_reports: int = 2,
        ttl: int = 10,
        every: int = 10,
        use_memory: bool = True,
    ) -> None:
        if cell_size <= 0 or top_k < 1 or min_reports < 1 or every < 1:
            raise ValueError("invalid queen configuration")
        self.report_kind = report_kind
        self.recruit_kind = recruit_kind
        self.cell_size = cell_size
        self.top_k = top_k
        self.min_reports = min_reports
        self.ttl = ttl
        self.every = every
        self.use_memory = use_memory

    def describe(self) -> Dict[str, Any]:
        return {"policy": "queen_emitter", "report_kind": self.report_kind, "recruit_kind": self.recruit_kind,
                "cell_size": self.cell_size, "top_k": self.top_k, "min_reports": self.min_reports,
                "ttl": self.ttl, "every": self.every, "use_memory": self.use_memory}

    def decide(self, view: LocalView) -> Intent:
        if view.tick % self.every:
            return Intent(NOOP)
        reports: List[Tuple[Tuple[float, ...], str, str]] = []  # (pos, reporter, evidence id or "")
        for signal in view.signals:
            if signal.kind == self.report_kind and signal.pos is not None:
                reports.append((signal.pos, signal.sender, ""))
        if self.use_memory:
            for record in view.memory:
                body = record.body
                if body.get("kind") == self.report_kind and body.get("pos"):
                    reports.append((tuple(float(c) for c in body["pos"]), record.author, record.id))
        buckets: Dict[Tuple[int, ...], List[Tuple[Tuple[float, ...], str, str]]] = defaultdict(list)
        for report in reports:
            key = tuple(math.floor(c / self.cell_size) for c in report[0])
            buckets[key].append(report)
        ranked = sorted(
            ((len({r[1] for r in items}), key, items) for key, items in buckets.items()),
            key=lambda row: (-row[0], row[1]),
        )
        emits = []
        for reporters, _, items in ranked[: self.top_k]:
            if reporters < self.min_reports:
                break
            dims = len(items[0][0])
            centroid = tuple(round(sum(r[0][d] for r in items) / len(items), 3) for d in range(dims))
            cites = tuple(sorted({r[2] for r in items if r[2]}))[:16]
            emits.append(SignalDraft(kind=self.recruit_kind, pos=centroid, ttl=self.ttl,
                                     payload={"reports": len(items), "reporters": reporters}, cites=cites))
        if not emits:
            return Intent(NOOP)
        return Intent(NOOP, emit=tuple(emits), rationale=f"recruit to {len(emits)} reported region(s)")
