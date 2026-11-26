"""Game Checker: free deterministic legality/invariant checks + selective L1-metered escalation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from antelligence.harness.core import Action, EnvAdapter, Observation
from antelligence.harness.games.memory import EpisodeMemory
from antelligence.record.l1_gate import L1Gate


@dataclass(frozen=True)
class CrossFamilyVerdict:
    """Result from a selective cross-family checker or lookahead call."""

    approved: bool
    reason: str
    alternative: Optional[Action] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_microusd: int = 0
    format_ok: bool = True


@dataclass(frozen=True)
class CheckDecision:
    """Combined outcome of deterministic legality checks and optional selective cross-family review."""

    allowed: bool
    reason: str
    escalated: bool = False
    override_action: Optional[Action] = None
    used_cross_family: bool = False
    cost_microusd: int = 0


InvariantFn = Callable[[Observation, Action, Optional[EpisodeMemory]], Optional[str]]
TriggerFn = Callable[[Observation, Action, Optional[EpisodeMemory]], bool]
CrossFamilyFn = Callable[[Observation, Action, Optional[EpisodeMemory]], CrossFamilyVerdict]


@dataclass
class GameChecker:
    """Two-stage game action checker (no per-tick Queen).

    Stage 1 runs free deterministic legality and invariant checks every turn.
    Stage 2 fires a cross-family checker/lookahead *only* when an action is
    high-stakes/irreversible or flagged as a calibrated anomaly, and meters
    every such call through PR 3's :class:`~antelligence.record.l1_gate.L1Gate`.
    """

    invariants: Sequence[InvariantFn] = field(default_factory=tuple)
    high_stakes_fn: Optional[TriggerFn] = None
    anomaly_fn: Optional[TriggerFn] = None
    cross_family_fn: Optional[CrossFamilyFn] = None
    checker_model: str = "cross_family_checker"
    worst_case_microusd: int = 2000

    def check(
        self,
        env: EnvAdapter,
        obs: Observation,
        action: Action,
        memory: Optional[EpisodeMemory] = None,
        *,
        gate: Optional[L1Gate] = None,
    ) -> CheckDecision:
        legal = env.legal_actions(obs)
        if legal is not None and action not in legal:
            return CheckDecision(allowed=False, reason=f"illegal_action:{action!r}")

        for inv in self.invariants:
            violation = inv(obs, action, memory)
            if violation:
                return CheckDecision(allowed=False, reason=f"invariant:{violation}")

        high_stakes = bool(self.high_stakes_fn and self.high_stakes_fn(obs, action, memory))
        anomaly = bool(self.anomaly_fn and self.anomaly_fn(obs, action, memory))
        if not (high_stakes or anomaly) or self.cross_family_fn is None:
            return CheckDecision(allowed=True, reason="deterministic_ok")

        if gate is not None:
            ok = gate.model_call(
                self.checker_model,
                f"check:{action!r}|hs={high_stakes}|anom={anomaly}",
                self.worst_case_microusd,
            )
            if not ok:
                return CheckDecision(
                    allowed=False,
                    reason="l1_gate_refused",
                    escalated=True,
                )

        verdict = self.cross_family_fn(obs, action, memory)
        if gate is not None:
            gate.model_result(
                verdict.tokens_in,
                verdict.tokens_out,
                verdict.cost_microusd,
                verdict.reason,
                format_ok=verdict.format_ok,
            )
        return CheckDecision(
            allowed=verdict.approved,
            reason=verdict.reason,
            escalated=True,
            override_action=verdict.alternative,
            used_cross_family=True,
            cost_microusd=verdict.cost_microusd,
        )
