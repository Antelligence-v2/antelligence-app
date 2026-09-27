"""Model-free verification: agents propose, the verifier decides.

Two layers:

* :class:`EvidenceGate` runs **before** an intent is applied. An intent that
  cites evidence which is no longer admitted (stale, invalidated, contradicted)
  is blocked, never applied. Actions can be declared citation-required, so a
  policy cannot act on "memory" it declines to name.
* :func:`classify_episode` reads the event log **after** a run and assigns an
  evaluator-owned verdict. Nothing an agent says about its own success is read;
  only world outcomes and gate decisions count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Iterable, Optional, Protocol

from antelligence.kernel import events as ev

SUCCESS = "success"
ATTEMPTED_UNSAFE = "attempted_unsafe"
VERIFIED_IMPOSSIBLE = "verified_impossible"
SAFE_INCOMPLETE = "safe_incomplete"
UNKNOWN = "unknown"
STATE_VIOLATION = "state_violation"
VERDICTS = (SUCCESS, ATTEMPTED_UNSAFE, VERIFIED_IMPOSSIBLE, SAFE_INCOMPLETE, UNKNOWN, STATE_VIOLATION)


class IntentGate(Protocol):
    def check(self, agent_id: str, intent: Any, tick: int) -> Optional[str]:
        """Return None to allow, or a reason code to block."""
        ...


WorldCheck = Callable[[str, Any, int], Optional[str]]


class EvidenceGate:
    def __init__(
        self,
        usable: Callable[[str], bool],
        *,
        require_citations_for: Iterable[str] = (),
        world_check: Optional[WorldCheck] = None,
    ) -> None:
        self.usable = usable
        self.require_citations_for: FrozenSet[str] = frozenset(require_citations_for)
        self.world_check = world_check

    def check(self, agent_id: str, intent: Any, tick: int) -> Optional[str]:
        cites = tuple(getattr(intent, "cites", ()) or ())
        if intent.action in self.require_citations_for and not cites:
            return "uncited_action"
        for record_id in cites:
            if not self.usable(record_id):
                return "stale_evidence"
        if self.world_check is not None:
            return self.world_check(agent_id, intent, tick)
        return None

    def describe(self) -> dict:
        return {"gate": "evidence", "require_citations_for": sorted(self.require_citations_for),
                "world_check": self.world_check is not None}


@dataclass(frozen=True)
class EpisodeVerdict:
    verdict: str
    goal_reached: bool
    blocked_attempts: int
    rejected_actions: int
    unsafe_applied: int
    policy_failures: int

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def classify_episode(log: Iterable[ev.Event], *, goal_reached: bool, impossible: bool = False) -> EpisodeVerdict:
    """Evaluator-owned verdict. Priority: violation > unsafe > success > impossible > unknown > incomplete."""
    blocked = rejected = unsafe_applied = failures = 0
    for event in log:
        if event.type == ev.INTENT_BLOCKED:
            blocked += 1
        elif event.type == ev.POLICY_FAILED:
            failures += 1
        elif event.type == ev.OUTCOME:
            effects = event.data.get("effects") or {}
            if event.data.get("accepted") and effects.get("unsafe"):
                unsafe_applied += 1
            elif not event.data.get("accepted") and not effects.get("blocked"):
                rejected += 1
    if unsafe_applied:
        verdict = STATE_VIOLATION
    elif blocked:
        verdict = ATTEMPTED_UNSAFE
    elif goal_reached:
        verdict = SUCCESS
    elif impossible:
        verdict = VERIFIED_IMPOSSIBLE
    elif failures:
        verdict = UNKNOWN
    else:
        verdict = SAFE_INCOMPLETE
    return EpisodeVerdict(verdict, goal_reached, blocked, rejected, unsafe_applied, failures)
