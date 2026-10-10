"""Independence of agents' errors: how many agents a colony is really worth.

A colony of k agents whose errors coincide is one agent counted k times; votes
and AND-gates over it copy the same mistakes. This module measures that from
evaluator-owned evidence only:

* an **error matrix** (agent x item -> 1 error, 0 correct; missing allowed),
  built from run event logs by a ``judge`` that reads world outcomes and
  verifier/evaluator verdicts — never what an agent says about itself;
* pairwise **phi** correlation of error indicators, the **double-fault** rate
  P(both wrong), and the **effective number of independent agents**
  ``n_eff = k^2 / sum_ab rho_ab`` (rho_aa = 1). For k equally correlated agents
  this is ``k / (1 + (k-1) rho)``: the variance-based effective sample size;
* a **rate-adjusted** variant. Phi between two binary variables is capped below
  1 when their rates differ (``phi_max``), so a weak agent next to a strong one
  looks independent even if it fails on every item the strong one fails on.
  ``rho / phi_max`` removes that artefact; ``n_eff_rate_adjusted`` is the
  conservative figure;
* a seeded bootstrap interval over items, and ``herding``: how much
  independence a protocol's communication destroyed (round 0 vs final round).

Pure: the kernel never imports a world; the judge is passed in.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from antelligence.kernel import events as ev

Errors = Mapping[str, Mapping[str, int]]  # agent -> item -> 1 (error) / 0 (correct)
Judge = Callable[[str, ev.Event], Optional[Tuple[str, str, int]]]  # (run_id, event) -> (agent, item, error)

MIN_OVERLAP = 20


def default_judge(run_id: str, event: ev.Event) -> Optional[Tuple[str, str, int]]:
    """Model-free judge for worlds without per-agent gold answers.

    An applied outcome is correct; a rejected outcome, a gate block or a policy
    failure is an error. ``noop`` outcomes are not judged (the agent did not act)
    unless the policy failed, which is always an error.
    """
    if event.agent_id is None:
        return None
    item = f"{run_id}:{event.tick}"
    if event.type == ev.POLICY_FAILED:
        return event.agent_id, item, 1
    if event.type == ev.OUTCOME and event.data.get("action") != "noop":
        return event.agent_id, item, 0 if event.data.get("accepted") else 1
    return None


def errors_from_runs(runs: Iterable[Tuple[str, Iterable[ev.Event]]], judge: Judge = default_judge,
                     *, seat_of: Optional[Callable[[str, str], str]] = None) -> Dict[str, Dict[str, int]]:
    """Build an error matrix from ``(run_id, events)`` pairs.

    ``seat_of(run_id, agent_id)`` maps a run-local agent id to a stable seat
    label so one agent's record spans many runs. If an (agent, item) is judged
    more than once, any error wins.
    """
    out: Dict[str, Dict[str, int]] = {}
    for run_id, events in runs:
        for event in events:
            verdict = judge(run_id, event)
            if verdict is None:
                continue
            agent, item, error = verdict
            if error not in (0, 1):
                raise ValueError(f"judge must return error 0 or 1, got {error!r}")
            seat = seat_of(run_id, agent) if seat_of is not None else agent
            row = out.setdefault(seat, {})
            row[item] = max(row.get(item, 0), int(error))
    return out


def phi(x: Sequence[int], y: Sequence[int]) -> Optional[float]:
    """Pearson correlation of two 0/1 vectors; None when either is constant."""
    n = len(x)
    if n == 0 or n != len(y):
        return None
    mx, my = sum(x) / n, sum(y) / n
    vx, vy = mx * (1 - mx), my * (1 - my)
    if vx <= 0 or vy <= 0:
        return None
    cov = sum(a * b for a, b in zip(x, y)) / n - mx * my
    return max(-1.0, min(1.0, cov / math.sqrt(vx * vy)))


def phi_max(p1: float, p2: float) -> Optional[float]:
    """Largest positive phi attainable by two binary variables with rates p1, p2."""
    lo, hi = sorted((p1, p2))
    if lo <= 0 or hi >= 1:
        return None
    return math.sqrt(lo * (1 - hi) / (hi * (1 - lo)))


def n_eff(rho: Mapping[Tuple[str, str], Optional[float]], agents: Sequence[str], *, prior: float = 0.0) -> float:
    """``k^2 / sum_ab rho_ab`` with rho_aa = 1; undefined pairs use ``prior``."""
    k = len(agents)
    if k == 0:
        return 0.0
    total = 0.0
    for a in agents:
        for b in agents:
            if a == b:
                total += 1.0
            else:
                value = rho.get((a, b))
                total += prior if value is None else value
    return math.inf if total <= 0 else k * k / total


@dataclass(frozen=True)
class IndependenceReport:
    agents: Tuple[str, ...]
    items: int
    n: Dict[str, int]
    error_rate: Dict[str, float]
    rho: Dict[str, Dict[str, Optional[float]]]
    rho_adjusted: Dict[str, Dict[str, Optional[float]]]
    overlap: Dict[str, Dict[str, int]]
    double_fault: Dict[str, Dict[str, Optional[float]]]
    n_eff: float
    n_eff_rate_adjusted: float
    n_eff_ci: Optional[Tuple[float, float]]
    n_eff_rate_adjusted_ci: Optional[Tuple[float, float]]
    flags: Tuple[str, ...] = field(default=())

    def to_dict(self) -> Dict[str, Any]:
        def num(value: Optional[float]) -> Any:
            return None if value is None else ("inf" if math.isinf(value) else round(value, 6))

        return {
            "agents": list(self.agents),
            "items": self.items,
            "n": dict(self.n),
            "error_rate": {a: num(v) for a, v in self.error_rate.items()},
            "rho": {a: {b: num(v) for b, v in row.items()} for a, row in self.rho.items()},
            "rho_adjusted": {a: {b: num(v) for b, v in row.items()} for a, row in self.rho_adjusted.items()},
            "overlap": {a: dict(row) for a, row in self.overlap.items()},
            "double_fault": {a: {b: num(v) for b, v in row.items()} for a, row in self.double_fault.items()},
            "n_eff": num(self.n_eff),
            "n_eff_rate_adjusted": num(self.n_eff_rate_adjusted),
            "n_eff_ci": None if self.n_eff_ci is None else [num(v) for v in self.n_eff_ci],
            "n_eff_rate_adjusted_ci": (None if self.n_eff_rate_adjusted_ci is None
                                       else [num(v) for v in self.n_eff_rate_adjusted_ci]),
            "flags": list(self.flags),
        }


def _pairwise(errors: Errors, agents: Sequence[str], items: Sequence[str], min_overlap: int):
    rate = {a: (sum(errors[a][i] for i in items if i in errors[a]) /
                max(1, sum(1 for i in items if i in errors[a]))) for a in agents}
    rho: Dict[Tuple[str, str], Optional[float]] = {}
    adj: Dict[Tuple[str, str], Optional[float]] = {}
    overlap: Dict[Tuple[str, str], int] = {}
    dfault: Dict[Tuple[str, str], Optional[float]] = {}
    flags: List[str] = []
    for ai, a in enumerate(agents):
        for b in agents[ai + 1:]:
            shared = [i for i in items if i in errors[a] and i in errors[b]]
            x = [errors[a][i] for i in shared]
            y = [errors[b][i] for i in shared]
            overlap[(a, b)] = overlap[(b, a)] = len(shared)
            df = (sum(1 for u, v in zip(x, y) if u and v) / len(shared)) if shared else None
            dfault[(a, b)] = dfault[(b, a)] = df
            r = phi(x, y) if len(shared) >= min_overlap else None
            if len(shared) < min_overlap:
                flags.append(f"low_overlap:{a}|{b}")
            elif r is None:
                flags.append(f"constant_errors:{a}|{b}")
            ra = None
            if r is not None:
                if r > 0 and shared:
                    cap = phi_max(sum(x) / len(x), sum(y) / len(y))
                    ra = min(1.0, r / cap) if cap else r
                else:
                    ra = r
            rho[(a, b)] = rho[(b, a)] = r
            adj[(a, b)] = adj[(b, a)] = ra
    return rate, rho, adj, overlap, dfault, flags


def _matrix(pairs: Mapping[Tuple[str, str], Any], agents: Sequence[str],
            diag: Callable[[str], Any]) -> Dict[str, Dict[str, Any]]:
    return {a: {b: (diag(a) if a == b else pairs.get((a, b))) for b in agents} for a in agents}


def independence(errors: Errors, *, agents: Optional[Sequence[str]] = None, min_overlap: int = MIN_OVERLAP,
                 prior: float = 0.0, bootstrap: int = 1000, seed: int = 0) -> IndependenceReport:
    """Measure error independence. ``prior`` stands in for undefined pairs (flagged)."""
    agents = tuple(sorted(errors) if agents is None else agents)
    for a in agents:
        if a not in errors:
            raise KeyError(f"no errors recorded for agent {a!r}")
    items = sorted({i for a in agents for i in errors[a]})
    rate, rho, adj, overlap, dfault, flags = _pairwise(errors, agents, items, min_overlap)
    if any(v is None for v in rho.values()) and agents:
        flags.append(f"undefined_pairs_use_prior:{prior}")

    ci = ci_adj = None
    if bootstrap and len(agents) > 1 and items:
        rng = random.Random(seed)
        raw_samples, adj_samples = [], []
        for _ in range(bootstrap):
            draw = [items[rng.randrange(len(items))] for _ in items]
            # Resampled items get unique keys so duplicates count as separate observations.
            resampled = {a: {f"{k}#{i}": errors[a][i] for k, i in enumerate(draw) if i in errors[a]} for a in agents}
            keys = [f"{k}#{i}" for k, i in enumerate(draw)]
            _, r_b, a_b, _, _, _ = _pairwise(resampled, agents, keys, min_overlap)
            raw_samples.append(n_eff(r_b, agents, prior=prior))
            adj_samples.append(n_eff(a_b, agents, prior=prior))
        ci, ci_adj = _percentile(raw_samples), _percentile(adj_samples)

    return IndependenceReport(
        agents=agents,
        items=len(items),
        n={a: len(errors[a]) for a in agents},
        error_rate=rate,
        rho=_matrix(rho, agents, lambda a: 1.0),
        rho_adjusted=_matrix(adj, agents, lambda a: 1.0),
        overlap=_matrix(overlap, agents, lambda a: len(errors[a])),
        double_fault=_matrix(dfault, agents, lambda a: rate[a]),
        n_eff=n_eff(rho, agents, prior=prior),
        n_eff_rate_adjusted=n_eff(adj, agents, prior=prior),
        n_eff_ci=ci,
        n_eff_rate_adjusted_ci=ci_adj,
        flags=tuple(flags),
    )


def _percentile(samples: List[float], lo: float = 0.025, hi: float = 0.975) -> Tuple[float, float]:
    ordered = sorted(samples)
    n = len(ordered)
    return ordered[min(n - 1, int(lo * n))], ordered[min(n - 1, int(hi * n))]


def herding(round0: Errors, final: Errors, **kwargs: Any) -> Dict[str, Any]:
    """Independence lost to communication: n_eff on first-round vs final answers."""
    before = independence(round0, **kwargs)
    after = independence(final, **kwargs)
    return {
        "n_eff_round0": before.n_eff,
        "n_eff_final": after.n_eff,
        "delta": after.n_eff - before.n_eff,
        "n_eff_rate_adjusted_round0": before.n_eff_rate_adjusted,
        "n_eff_rate_adjusted_final": after.n_eff_rate_adjusted,
        "delta_rate_adjusted": after.n_eff_rate_adjusted - before.n_eff_rate_adjusted,
    }
