"""Reputation: a track record earned from verdicts, never from self-report.

What carries reputation is a **persona** (model + role + prompt), per **area**
(a competence domain such as ``research_qa/finance``; deliberately not called
"scope", which in memory means experimental arm) and per **channel**:

* ``label``         — the evaluator scored the persona's final answer;
* ``verification``  — the verifier checked a claim (quote/number) model-free;
* ``contradiction`` — an authority resolved a contradiction against its claim.

Only authorities may write (same rule as ``EvidenceMemory`` outcome records);
there is no API that takes an agent's confidence or self-assessment.

The stored state is weighted success/failure counts. The posterior is a Beta
whose prior is centred on **chance** accuracy (supplied at query time, since
it depends on the question), with ``prior_strength`` pseudo-observations. An
unknown persona therefore sits exactly at chance, which the aggregator maps to
zero voting weight: a fresh identity cannot buy influence.

Every update is returned by :meth:`drain_updates` for the event log
(``reputation_updated``), so a ledger can be rebuilt from logs, and
:meth:`snapshot_hash` lets a run's config hash pin the record it started from.
:class:`ReputationView` freezes a snapshot for the duration of one run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple

from antelligence.kernel import events as ev
from antelligence.kernel.canonical import content_hash, plain
from antelligence.kernel.memory import VERIFIER, WORLD, TrustError

EVALUATOR = "evaluator"
LABEL = "label"
VERIFICATION = "verification"
CONTRADICTION = "contradiction"
CHANNELS = frozenset({LABEL, VERIFICATION, CONTRADICTION})

Key = Tuple[str, str, str]  # (persona, area, channel)


@dataclass(frozen=True)
class Standing:
    """Posterior accuracy of one persona in one area and channel."""

    persona: str
    area: str
    channel: str
    successes: float
    failures: float
    accuracy: float  # posterior mean
    chance: float

    @property
    def n(self) -> float:
        return self.successes + self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {"persona": self.persona, "area": self.area, "channel": self.channel,
                "successes": round(self.successes, 9), "failures": round(self.failures, 9),
                "accuracy": round(self.accuracy, 9), "chance": self.chance}


class ReputationLedger:
    def __init__(self, *, authorities: FrozenSet[str] = frozenset({WORLD, VERIFIER, EVALUATOR}),
                 prior_strength: float = 2.0, forgetting: float = 1.0) -> None:
        if prior_strength <= 0:
            raise ValueError("prior_strength must be positive")
        if not 0 < forgetting <= 1:
            raise ValueError("forgetting must be in (0, 1]")
        self.authorities = frozenset(authorities)
        self.prior_strength = float(prior_strength)
        self.forgetting = float(forgetting)
        self._counts: Dict[Key, List[float]] = {}
        self._pending: List[dict] = []

    # ------------------------------------------------------------- writing
    def record(self, *, persona: str, area: str, channel: str, success: bool, author: str,
               tick: Optional[int] = None, ref: Optional[str] = None) -> dict:
        """Apply one authority verdict. ``ref`` names the evidence (item, record id)."""
        if author not in self.authorities:
            raise TrustError(f"{author!r} may not write reputation")
        if channel not in CHANNELS:
            raise ValueError(f"unknown reputation channel {channel!r}")
        if not persona or not area:
            raise ValueError("persona and area are required")
        if not isinstance(success, bool):
            raise ValueError("success must be a bool")
        counts = self._counts.setdefault((persona, area, channel), [0.0, 0.0])
        counts[0] *= self.forgetting
        counts[1] *= self.forgetting
        counts[0 if success else 1] += 1.0
        update = {"persona": persona, "area": area, "channel": channel, "success": success,
                  "author": author, "tick": tick, "ref": ref}
        self._pending.append(update)
        return update

    def drain_updates(self) -> List[dict]:
        pending, self._pending = self._pending, []
        return pending

    # ------------------------------------------------------------- reading
    def standing(self, persona: str, area: str, *, chance: float, channel: str = LABEL) -> Standing:
        if not 0 < chance < 1:
            raise ValueError("chance must be in (0, 1)")
        s, f = self._counts.get((persona, area, channel), (0.0, 0.0))
        alpha = self.prior_strength * chance + s
        beta = self.prior_strength * (1 - chance) + f
        return Standing(persona, area, channel, s, f, alpha / (alpha + beta), chance)

    def accuracy(self, persona: str, area: str, *, chance: float, channel: str = LABEL) -> float:
        return self.standing(persona, area, chance=chance, channel=channel).accuracy

    def reliability(self, area: str, channel: str = LABEL):
        """``(persona, chance) -> accuracy`` for :class:`~antelligence.kernel.aggregate.Aggregator`."""
        return lambda persona, chance: self.accuracy(persona, area, chance=chance, channel=channel)

    def snapshot(self) -> Dict[str, Any]:
        rows = [{"persona": p, "area": a, "channel": c, "successes": v[0], "failures": v[1]}
                for (p, a, c), v in sorted(self._counts.items())]
        return plain({"prior_strength": self.prior_strength, "forgetting": self.forgetting, "counts": rows})

    def snapshot_hash(self) -> str:
        return content_hash(self.snapshot())

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any], **kwargs: Any) -> "ReputationLedger":
        ledger = cls(prior_strength=snapshot["prior_strength"], forgetting=snapshot["forgetting"], **kwargs)
        for row in snapshot["counts"]:
            ledger._counts[(row["persona"], row["area"], row["channel"])] = [float(row["successes"]),
                                                                             float(row["failures"])]
        return ledger

    @classmethod
    def from_events(cls, events: Iterable[ev.Event], **kwargs: Any) -> "ReputationLedger":
        """Rebuild by replaying ``reputation_updated`` events in log order."""
        ledger = cls(**kwargs)
        for event in events:
            if event.type == ev.REPUTATION_UPDATED:
                d = event.data
                ledger.record(persona=d["persona"], area=d["area"], channel=d["channel"],
                              success=d["success"], author=d["author"], tick=d.get("tick"), ref=d.get("ref"))
        ledger.drain_updates()
        return ledger


class ReputationView:
    """A frozen, per-run reading of a ledger: agent id -> posterior accuracy.

    Reputation never changes inside a run (labels arrive only after an item
    closes), so the view copies the ledger at construction and its
    ``describe()`` — part of the run's config hash — names that snapshot.
    """

    def __init__(self, ledger: ReputationLedger, persona_of: Mapping[str, str], *, area: str, chance: float,
                 channel: str = LABEL) -> None:
        self._ledger = ReputationLedger.from_snapshot(ledger.snapshot(), authorities=ledger.authorities)
        self._hash = self._ledger.snapshot_hash()
        self.persona_of = dict(persona_of)
        self.area = area
        self.chance = chance
        self.channel = channel

    def persona(self, agent_id: str) -> Optional[str]:
        return self.persona_of.get(agent_id)

    def accuracy(self, agent_id: str) -> Optional[float]:
        persona = self.persona_of.get(agent_id)
        if persona is None:
            return None
        return self._ledger.accuracy(persona, self.area, chance=self.chance, channel=self.channel)

    def __call__(self, agent_id: str) -> Optional[float]:
        value = self.accuracy(agent_id)
        return None if value is None else round(value, 6)

    def describe(self) -> Dict[str, Any]:
        return {"reputation": "ledger_view", "snapshot": self._hash, "area": self.area, "chance": self.chance,
                "channel": self.channel, "personas": dict(sorted(self.persona_of.items()))}
