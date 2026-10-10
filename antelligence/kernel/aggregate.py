"""Calibrated aggregation: weigh votes by earned reliability, discount copies.

Replaces strict-majority and AND-style rules. Pure and model-free: votes in,
decision out. For each non-abstaining vote i on answer a:

* reliability weight  ``w_i = clip(log((K-1) p_i / (1 - p_i)), 0, max_weight)``
  where ``p_i`` is the voter's reputation (posterior accuracy at chance 1/K,
  see :meth:`ReputationLedger.reliability`) and K the number of options. These are the Nitzan–Paroush optimal weights for independent
  voters; a voter at chance (e.g. an unknown persona) gets weight 0, and an
  unreliable one is ignored rather than inverted;
* verification multiplier ``m_i``: verified 1, unverified ``unverified_weight``,
  failed 0 (a claim whose quote is not in the source has no voice);
* correlation discount ``d_i = 1 / sum_{j in voters} max(rho_ij, 0)`` with
  rho_ii = 1: k exact copies count as one agent, independent agents count fully,
  and ``sum d_i`` is the effective number of independent voters
  (see :mod:`antelligence.kernel.independence`).

``score(a) = sum_{i votes a} d_i m_i w_i`` and ``P(a) = softmax(score / T)`` over
every option (closed questions: all choices; open questions: the proposed
answers plus one "other" bucket). Under the symmetric-error model, a single
verified voter's posterior then equals its reputation exactly.

Modes: ``forced`` returns the argmax (ties broken by the number of effective
supporters, then the strongest single supporter, then canonical order);
``abstain`` also abstains when P(top) < ``tau`` or the top answer's effective
independent support ``sum d_i m_i`` is below ``min_support``.

Ablations switch off one mechanism each: ``use_reputation`` (all w_i = 1),
``use_correlation`` (all d_i = 1), ``use_verification`` (all m_i = 1). With all
three off, forced mode is plurality vote.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

VERIFIED = "verified"
UNVERIFIED = "unverified"
FAILED = "failed"
VERIFICATIONS = (VERIFIED, UNVERIFIED, FAILED)
FORCED = "forced"
ABSTAIN = "abstain"
OTHER = "__other__"

Correlation = Callable[[str, str], Optional[float]]  # (seat_a, seat_b) -> rho or None
Reliability = Callable[[str, float], Optional[float]]  # (persona, chance) -> posterior accuracy, or None if unknown


@dataclass(frozen=True)
class Vote:
    seat: str
    persona: str
    answer: Optional[Any]  # None = abstained
    verification: str = UNVERIFIED

    def __post_init__(self) -> None:
        if not self.seat or not self.persona:
            raise ValueError("seat and persona are required")
        if self.verification not in VERIFICATIONS:
            raise ValueError(f"unknown verification {self.verification!r}")


@dataclass(frozen=True)
class AggregateDecision:
    answer: Optional[str]
    abstained: bool
    reason: str
    posterior: Dict[str, float]
    support_n_eff: float
    voters_n_eff: float
    contributions: Tuple[Dict[str, Any], ...] = field(default=())

    def to_dict(self) -> Dict[str, Any]:
        return {"answer": self.answer, "abstained": self.abstained, "reason": self.reason,
                "posterior": {k: round(v, 9) for k, v in sorted(self.posterior.items())},
                "support_n_eff": round(self.support_n_eff, 9), "voters_n_eff": round(self.voters_n_eff, 9),
                "contributions": [dict(c) for c in self.contributions]}


def canonical_answer(answer: Any, sig_figs: int = 6) -> str:
    """Group equal answers: numbers by value (rounded to ``sig_figs``), text case-insensitively."""
    text = str(answer).strip()
    cleaned = text.replace(",", "").replace("$", "").rstrip("%").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return " ".join(text.lower().split())
    if not value.is_finite():
        return " ".join(text.lower().split())
    if value == 0:
        return "0"
    rounded = round(value, sig_figs - 1 - value.adjusted())
    return format(rounded.normalize(), "f")


class Aggregator:
    def __init__(
        self,
        *,
        reliability: Optional[Reliability] = None,
        correlation: Optional[Correlation] = None,
        rho_prior: float = 0.0,
        unverified_weight: float = 0.5,
        max_weight: float = 4.0,
        temperature: float = 1.0,
        mode: str = FORCED,
        tau: float = 0.6,
        min_support: float = 1.0,
        sig_figs: int = 6,
        use_reputation: bool = True,
        use_correlation: bool = True,
        use_verification: bool = True,
    ) -> None:
        if mode not in (FORCED, ABSTAIN):
            raise ValueError(f"unknown mode {mode!r}")
        if temperature <= 0 or max_weight <= 0 or not 0 <= unverified_weight <= 1:
            raise ValueError("temperature and max_weight must be positive; unverified_weight in [0, 1]")
        self.reliability = reliability
        self.correlation = correlation
        self.rho_prior = rho_prior
        self.unverified_weight = unverified_weight
        self.max_weight = max_weight
        self.temperature = temperature
        self.mode = mode
        self.tau = tau
        self.min_support = min_support
        self.sig_figs = sig_figs
        self.use_reputation = use_reputation
        self.use_correlation = use_correlation
        self.use_verification = use_verification

    def describe(self) -> Dict[str, Any]:
        return {"aggregator": "calibrated_logodds", "mode": self.mode, "rho_prior": self.rho_prior,
                "unverified_weight": self.unverified_weight, "max_weight": self.max_weight,
                "temperature": self.temperature, "tau": self.tau, "min_support": self.min_support,
                "sig_figs": self.sig_figs, "use_reputation": self.use_reputation,
                "use_correlation": self.use_correlation, "use_verification": self.use_verification}

    # ----------------------------------------------------------------- parts
    def weight(self, persona: str, k: int) -> float:
        if not self.use_reputation:
            return 1.0
        p = self.reliability(persona, 1.0 / k) if self.reliability is not None else None
        if p is None:
            return 0.0  # unknown persona: no earned record, no voice
        p = min(max(p, 1e-9), 1 - 1e-9)
        return min(self.max_weight, max(0.0, math.log((k - 1) * p / (1 - p))))

    def multiplier(self, verification: str) -> float:
        if not self.use_verification:
            return 1.0
        return {VERIFIED: 1.0, UNVERIFIED: self.unverified_weight, FAILED: 0.0}[verification]

    def rho(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        value = self.correlation(a, b) if self.correlation is not None else None
        return self.rho_prior if value is None else value

    def discounts(self, seats: Sequence[str]) -> Dict[str, float]:
        if not self.use_correlation:
            return {s: 1.0 for s in seats}
        return {s: 1.0 / sum(max(self.rho(s, t), 0.0) for t in seats) for s in seats}

    # -------------------------------------------------------------- decision
    def decide(self, votes: Sequence[Vote], *, choices: Optional[Sequence[str]] = None) -> AggregateDecision:
        seats = [v.seat for v in votes]
        if len(set(seats)) != len(seats):
            raise ValueError("one vote per seat")
        if choices is not None:
            options = [canonical_answer(c, self.sig_figs) for c in choices]
            if len(set(options)) != len(options) or len(options) < 2:
                raise ValueError("choices must be at least two distinct options")
        voting = [v for v in votes if v.answer is not None and self.multiplier(v.verification) > 0]
        canon = {v.seat: canonical_answer(v.answer, self.sig_figs) for v in voting}
        if choices is None:
            options = sorted(set(canon.values())) + [OTHER]
        else:
            unknown = sorted(set(canon.values()) - set(options))
            if unknown:
                raise ValueError(f"answers outside choices: {unknown}")
        k = len(options)
        discount = self.discounts([v.seat for v in voting])
        score = {o: 0.0 for o in options}
        support = {o: 0.0 for o in options}
        strongest = {o: 0.0 for o in options}
        voters = {o: 0 for o in options}
        contributions: List[Dict[str, Any]] = []
        for vote in sorted(votes, key=lambda v: v.seat):
            m = self.multiplier(vote.verification)
            if vote.answer is None or m == 0:
                contributions.append({"seat": vote.seat, "persona": vote.persona, "answer": None,
                                      "verification": vote.verification,
                                      "excluded": "abstained" if vote.answer is None else "failed_verification"})
                continue
            option = canon[vote.seat]
            w, d = self.weight(vote.persona, k), discount[vote.seat]
            score[option] += d * m * w
            support[option] += d * m
            strongest[option] = max(strongest[option], d * m * w)
            voters[option] += 1
            contributions.append({"seat": vote.seat, "persona": vote.persona, "answer": option,
                                  "verification": vote.verification, "weight": round(w, 9),
                                  "discount": round(d, 9), "multiplier": m, "contribution": round(d * m * w, 9)})
        posterior = _softmax({o: s / self.temperature for o, s in score.items()})
        voters_n_eff = sum(discount.values())
        if not voting:
            return AggregateDecision(None, True, "no_votes", posterior, 0.0, 0.0, tuple(contributions))
        ranked = sorted((o for o in options if o != OTHER and voters[o] > 0),
                        key=lambda o: (-score[o], -support[o], -strongest[o], o))
        top = ranked[0]
        tied = len(ranked) > 1 and (score[ranked[1]], support[ranked[1]], strongest[ranked[1]]) == \
            (score[top], support[top], strongest[top])
        reason = "argmax_tiebreak_canonical" if tied else "argmax"
        if self.mode == ABSTAIN:
            if tied:
                return AggregateDecision(None, True, "tie", posterior, support[top], voters_n_eff,
                                         tuple(contributions))
            if posterior[top] < self.tau:
                return AggregateDecision(None, True, "low_confidence", posterior, support[top], voters_n_eff,
                                         tuple(contributions))
            if support[top] < self.min_support:
                return AggregateDecision(None, True, "low_independent_support", posterior, support[top],
                                         voters_n_eff, tuple(contributions))
        return AggregateDecision(top, False, reason, posterior, support[top], voters_n_eff, tuple(contributions))


def _softmax(scores: Mapping[str, float]) -> Dict[str, float]:
    top = max(scores.values())
    exp = {o: math.exp(s - top) for o, s in scores.items()}
    total = sum(exp.values())
    return {o: e / total for o, e in exp.items()}
