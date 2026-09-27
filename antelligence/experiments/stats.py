"""Small, dependency-free statistics for paired swarm experiments."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence


def sign_test_p(wins: int, losses: int) -> Optional[float]:
    """Exact two-sided sign test on discordant pairs (ties excluded)."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> Optional[Dict[str, float]]:
    if trials <= 0:
        return None
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return {"low": max(0.0, center - half), "high": min(1.0, center + half)}


def paired_comparison(
    baseline: Sequence[Optional[float]],
    treatment: Sequence[Optional[float]],
    *,
    lower_is_better: bool,
) -> Dict[str, Any]:
    """Compare two arms on the same cases. Missing values drop the pair."""
    if len(baseline) != len(treatment):
        raise ValueError("paired sequences must have equal length")
    pairs = [(b, t) for b, t in zip(baseline, treatment) if b is not None and t is not None]
    wins = losses = ties = 0
    for b, t in pairs:
        better = t < b if lower_is_better else t > b
        worse = t > b if lower_is_better else t < b
        wins += better
        losses += worse
        ties += not better and not worse
    total_b = sum(b for b, _ in pairs)
    total_t = sum(t for _, t in pairs)
    return {
        "pairs": len(pairs),
        "dropped_pairs": len(baseline) - len(pairs),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "baseline_total": total_b,
        "treatment_total": total_t,
        "mean_delta": (total_t - total_b) / len(pairs) if pairs else None,
        "pct_change": 100.0 * (total_t - total_b) / total_b if pairs and total_b else None,
        "sign_test_p": sign_test_p(wins, losses),
        "lower_is_better": lower_is_better,
    }
