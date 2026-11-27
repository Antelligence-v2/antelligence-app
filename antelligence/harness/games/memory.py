"""Structured-first EpisodeMemory separating verified state from unverified LLM notes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

SCALAR_FACT_TYPES = (bool, int, float, str)


def extract_scalar_facts(obs: Any) -> Dict[str, Any]:
    """Extract verified non-None scalar key-value pairs from a Mapping observation."""
    if not isinstance(obs, Mapping):
        return {}
    return {
        str(key): value
        for key, value in obs.items()
        if isinstance(value, SCALAR_FACT_TYPES)
    }


@dataclass
class EpisodeMemory:
    """Grounded episodic memory for stateful EnvAdapter rollouts.

    Verified observations, actions, counters, and extracted facts are stored
    separately from ``unverified_notes`` (LLM scratchpad), preventing blind loops
    without letting unverified text masquerade as ground truth.
    """

    verified_history: List[Dict[str, Any]] = field(default_factory=list)
    counters: Dict[str, int] = field(
        default_factory=lambda: {"steps": 0, "violations": 0, "deliveries": 0}
    )
    facts: Dict[str, Any] = field(default_factory=dict)
    unverified_notes: List[Dict[str, Any]] = field(default_factory=list)
    total_reward: float = 0.0

    def update_facts(self, facts: Mapping[str, Any]) -> None:
        """Merge verified non-None facts into ``self.facts``."""
        for key, value in facts.items():
            if value is not None:
                self.facts[str(key)] = value

    def record_step(
        self,
        step_idx: int,
        obs: Any,
        action: Any,
        *,
        reward: float,
        done: bool,
        state_hash: str,
        info: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Record one verified environment transition and update structured counters."""
        self.counters["steps"] += 1
        self.total_reward += float(reward)
        info_map = dict(info or {})
        if info_map.get("violation"):
            self.counters["violations"] += int(info_map.get("violation_count", 1))
        if info_map.get("delivered"):
            self.counters["deliveries"] += 1
        self.update_facts(extract_scalar_facts(obs))
        if isinstance(info_map.get("verified_facts"), Mapping):
            self.update_facts(info_map["verified_facts"])
        self.verified_history.append(
            {
                "step": step_idx,
                "action": action,
                "reward": float(reward),
                "done": bool(done),
                "state_hash": state_hash,
                "obs": obs,
            }
        )

    def add_unverified_note(
        self,
        note: str,
        *,
        step_idx: Optional[int] = None,
        source: str = "llm",
    ) -> None:
        """Append an explicitly tagged unverified scratchpad note."""
        self.unverified_notes.append(
            {
                "tag": "unverified_note",
                "step": step_idx,
                "source": source,
                "text": str(note),
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable view with verified state separated from unverified notes."""
        return {
            "verified": {
                "counters": dict(self.counters),
                "facts": dict(self.facts),
                "total_reward": round(self.total_reward, 6),
                "history_len": len(self.verified_history),
                "last_step": self.verified_history[-1] if self.verified_history else None,
            },
            "unverified_notes": list(self.unverified_notes),
        }
