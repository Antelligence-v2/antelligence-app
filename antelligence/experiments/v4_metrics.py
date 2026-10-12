"""v4 pilot metrics: gap recovered, seconds per decision, calibration, paired bootstrap, go/no-go.

Pure functions over plain numbers and cell dicts; no I/O, no model calls. Goal section 7 is
implemented literally: Go, No-go or unclear, with no extra thresholds.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DS_ARM = "DS-all"
FRAMEWORK_ARMS = ("F-Laya", "F-Jev")
GO_MARGIN = 0.10  # Go: framework mean G >= DS-all mean G - 0.10 and a lower median s/decision
NO_GO_G = 0.10  # No-go: both framework arms below this mean G
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261011
# Pre-registered: a variant run's G is undefined when S' - S is below this gap (G explodes on a tiny gap).
MIN_GAP = {"foraging_sb": 2.0, "graph_coloring": 0.05}


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear-interpolated percentile (q in 0..100), the numpy default."""
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q / 100.0
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def gap_recovered(score: float, s_score: float, s_prime_score: float, min_gap: float = 0.0) -> Optional[float]:
    """G = (score - S) / (S' - S). None when S' beats S by no more than ``min_gap`` (no headroom to recover)."""
    gap = s_prime_score - s_score
    return None if gap <= 0 or gap < min_gap else (score - s_score) / gap


def seconds_per_decision(latencies: Sequence[float]) -> Dict[str, Any]:
    """Median and p90 of wall-clock seconds per model call, network included."""
    return {"n": len(latencies), "median": percentile(latencies, 50), "p90": percentile(latencies, 90)}


# --- calibration (Phase 0) -------------------------------------------------


def brier(probs: Sequence[float], labels: Sequence[bool]) -> Optional[float]:
    if not probs:
        return None
    return sum((p - float(y)) ** 2 for p, y in zip(probs, labels)) / len(probs)


def ece(probs: Sequence[float], labels: Sequence[bool], bins: int = 10) -> Optional[float]:
    """Expected calibration error with equal-width bins; p == 1.0 falls in the top bin."""
    if not probs:
        return None
    grouped: Dict[int, List[Tuple[float, bool]]] = defaultdict(list)
    for p, y in zip(probs, labels):
        grouped[min(int(p * bins), bins - 1)].append((p, y))
    total = len(probs)
    return sum(len(g) / total * abs(sum(p for p, _ in g) / len(g) - sum(float(y) for _, y in g) / len(g))
               for g in grouped.values())


def calibration_summary(cells: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Accuracy, Brier, ECE and latency over Phase 0 cells.

    Each cell has ``prob`` (probability given to the event), ``label`` (did it happen) and
    ``correct``. Noul: prob = P(yes), label = truth. Choice: prob = probability of the chosen
    option, label = whether it was right. Cells with an ``error`` are counted, not scored.
    """
    scored = [c for c in cells if not c.get("error") and c.get("prob") is not None]
    probs = [float(c["prob"]) for c in scored]
    labels = [bool(c["label"]) for c in scored]
    return {"n": len(cells), "scored": len(scored), "errors": len(cells) - len(scored),
            "accuracy": mean(float(bool(c["correct"])) for c in scored),
            "brier": brier(probs, labels), "ece": ece(probs, labels),
            "latency_s": seconds_per_decision([float(c["latency_s"]) for c in scored
                                               if c.get("latency_s") is not None])}


# --- paired bootstrap --------------------------------------------------------


def paired_bootstrap(x: Mapping[Tuple, float], y: Mapping[Tuple, float], *, resamples: int = BOOTSTRAP_RESAMPLES,
                     seed: int = BOOTSTRAP_SEED, level: float = 0.95) -> Dict[str, Any]:
    """Mean of x - y over shared keys with a percentile CI, resampling whole seeds.

    Keys are tuples whose element 1 is the seed, e.g. (world, seed, condition). All pairs from a
    resampled seed are kept together. The RNG is seeded, so the interval is reproducible.
    """
    keys = sorted(set(x) & set(y))
    if not keys:
        return {"pairs": 0, "seeds": 0, "mean_diff": None, "low": None, "high": None, "resamples": resamples}
    by_seed: Dict[Any, List[float]] = defaultdict(list)
    for k in keys:
        by_seed[k[1]].append(x[k] - y[k])
    clusters = [by_seed[s] for s in sorted(by_seed)]
    rng = random.Random(seed)
    means: List[float] = []
    for _ in range(resamples):
        picked = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        flat = [d for cluster in picked for d in cluster]
        means.append(sum(flat) / len(flat))
    means.sort()
    alpha = (1 - level) / 2
    return {"pairs": len(keys), "seeds": len(clusters), "mean_diff": sum(sum(c) for c in clusters) / len(keys),
            "low": percentile(means, 100 * alpha), "high": percentile(means, 100 * (1 - alpha)),
            "resamples": resamples, "level": level, "rng_seed": seed}


# --- go / no-go (goal section 7, literal) ------------------------------------


def go_no_go(mean_g: Mapping[str, Optional[float]], median_spd: Mapping[str, Optional[float]]) -> Dict[str, Any]:
    """Go: a framework arm's mean G >= DS-all mean G - 0.10 AND its median s/decision is lower.
    No-go: both framework arms have mean G < 0.10. Otherwise unclear.

    No-go takes precedence (pre-registered): if both framework arms recover < 0.10 of the gap, a
    "Go" against an equally weak DS-all is meaningless, so the verdict is "no-go" and
    ``go_also_holds`` records that the Go condition held too.
    """
    ds_g, ds_t = mean_g.get(DS_ARM), median_spd.get(DS_ARM)
    per_arm: Dict[str, Dict[str, Any]] = {}
    for arm in FRAMEWORK_ARMS:
        g, t = mean_g.get(arm), median_spd.get(arm)
        g_ok = None if g is None or ds_g is None else g >= ds_g - GO_MARGIN
        t_ok = None if t is None or ds_t is None else t < ds_t
        per_arm[arm] = {"mean_g": g, "median_s_per_decision": t, "g_within_margin": g_ok, "faster": t_ok,
                        "go": bool(g_ok and t_ok), "below_no_go_line": None if g is None else g < NO_GO_G}
    go_arms = [a for a, r in per_arm.items() if r["go"]]
    no_go = all(r["below_no_go_line"] for r in per_arm.values())
    verdict = "no-go" if no_go else "go" if go_arms else "unclear"
    return {"verdict": verdict, "go_arms": go_arms, "go_also_holds": bool(go_arms and no_go),
            "ds_all": {"mean_g": ds_g, "median_s_per_decision": ds_t}, "arms": per_arm,
            "rule": {"go_margin": GO_MARGIN, "no_go_g": NO_GO_G}}


# --- aggregation over cells --------------------------------------------------


def attach_g(cells: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Copy cells with ``g`` recomputed from the S and S' scores of the same world, seed and condition."""
    refs: Dict[Tuple, Dict[str, float]] = defaultdict(dict)
    for c in cells:
        if c["arm"] in ("S", "S-prime") and c.get("score") is not None and not c.get("error"):
            refs[(c["world"], c["seed"], c["condition"])][c["arm"]] = c["score"]
    out = []
    for c in cells:
        row = dict(c)
        r = refs.get((c["world"], c["seed"], c["condition"]), {})
        variant_run = c["condition"] != "base" and c["arm"] not in ("S", "S-prime")
        row["g"] = (gap_recovered(c["score"], r["S"], r["S-prime"], MIN_GAP.get(c["world"], 0.0))
                    if variant_run and c.get("score") is not None and "S" in r and "S-prime" in r else None)
        out.append(row)
    return out


def _arm_summary(cells: Sequence[Mapping[str, Any]], s_base: Mapping[Tuple, float]) -> Dict[str, Any]:
    ok = [c for c in cells if not c.get("error")]
    latencies = [float(x) for c in ok for x in c.get("latencies_s", [])]
    base = [c for c in ok if c["condition"] == "base"]
    shares = [c["score"] / s_base[(c["world"], c["seed"])] for c in base
              if s_base.get((c["world"], c["seed"])) and c.get("score") is not None]
    base_mean, s_mean = mean(c["score"] for c in base), mean(s_base[(c["world"], c["seed"])] for c in base
                                                             if (c["world"], c["seed"]) in s_base)
    by_cond = {cond: mean(c["score"] for c in ok if c["condition"] == cond) for cond in ("base", "v1", "v2")}

    def weighted(key: str, weight: str) -> Optional[float]:
        pairs = [(c[key], c[weight]) for c in ok if c.get(key) is not None and c.get(weight)]
        total = sum(w for _, w in pairs)
        return sum(v * w for v, w in pairs) / total if total else None

    reports = sum(c.get("reports", 0) for c in ok)
    return {
        "cells": len(cells), "errors": len(cells) - len(ok),
        "score_by_condition": by_cond,
        "mean_g": mean(c["g"] for c in ok if c.get("g") is not None),
        "mean_g_by_condition": {cond: mean(c["g"] for c in ok if c["condition"] == cond and c.get("g") is not None)
                                for cond in ("v1", "v2")},
        "base_share_of_S": (base_mean / s_mean) if base_mean is not None and s_mean else None,
        "base_share_of_S_per_cell_mean": mean(shares),
        "s_per_decision": seconds_per_decision(latencies),
        "ticks_mean": mean(c.get("ticks") for c in ok), "wall_s_mean": mean(c.get("wall_s") for c in ok),
        "calls": sum(c.get("calls", 0) for c in ok), "input_tokens": sum(c.get("input_tokens", 0) for c in ok),
        "output_tokens": sum(c.get("output_tokens", 0) for c in ok),
        "cost_usd": sum(c.get("cost_usd", 0.0) for c in ok),
        "compliance": weighted("compliance", "answers"),
        "report_precision": (sum(c.get("reports_true", 0) for c in ok) / reports) if reports else None,
        "reports": reports, "escalation_rate": weighted("escalation_rate", "model_decisions"),
        "policy_failures": sum(c.get("policy_failures", 0) for c in ok),
    }


def aggregate(cells: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Everything results.json needs from the cell rows: per-arm summaries, comparisons and go/no-go."""
    rows = attach_g(cells)
    s_base = {(c["world"], c["seed"]): c["score"] for c in rows
              if c["arm"] == "S" and c["condition"] == "base" and c.get("score") is not None and not c.get("error")}
    arms = sorted({c["arm"] for c in rows})
    worlds = sorted({c["world"] for c in rows})
    per_arm = {a: _arm_summary([c for c in rows if c["arm"] == a], s_base) for a in arms}
    per_world = {w: {a: _arm_summary([c for c in rows if c["arm"] == a and c["world"] == w], s_base) for a in arms
                     if any(c["arm"] == a and c["world"] == w for c in rows)} for w in worlds}

    def g_by_key(arm: str) -> Dict[Tuple, float]:
        return {(c["world"], c["seed"], c["condition"]): c["g"] for c in rows
                if c["arm"] == arm and c.get("g") is not None and not c.get("error")}

    comparisons = {f"{arm}_vs_{DS_ARM}": paired_bootstrap(g_by_key(arm), g_by_key(DS_ARM))
                   for arm in FRAMEWORK_ARMS if arm in per_arm and DS_ARM in per_arm}
    # Pre-registered: go/no-go compares mean G on the (world, seed, condition) keys every compared arm has
    # (DS-all foraging has fewer seeds), so the arms are paired by seed.
    compared = [a for a in (DS_ARM, *FRAMEWORK_ARMS) if a in per_arm]
    shared = set.intersection(*(set(g_by_key(a)) for a in compared)) if compared else set()
    paired_g = {a: mean(g_by_key(a)[k] for k in sorted(shared)) for a in compared}
    verdict = go_no_go(paired_g, {a: per_arm[a]["s_per_decision"]["median"] for a in per_arm})
    verdict["paired_keys"] = len(shared)
    return {"arms": per_arm, "by_world": per_world, "comparisons_mean_g_diff": comparisons, "go_no_go": verdict,
            "cells": len(rows), "note": "pilot estimates; 15 runs per arm per world detect only large effects"}
