#!/usr/bin/env python3
"""Analyze E13 results: sign test on sweep_moves, 5% threshold, verdict check.

Usage: python3 analyze_e13.py
Reads out/results_*.json and prints verdict summary.
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"


def load_results(arm):
    path = OUT / f"results_{arm}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data


def sign_test_paired(x, y):
    """Exact binomial sign test. Returns (n, n_plus, n_minus, p_value, direction).

    x: baseline sweep_moves per seed
    y: hive_memory sweep_moves per seed
    """
    pairs = []
    for bx in x:
        for by in y:
            if bx["seed"] == by["seed"]:
                pairs.append((bx["sweep_moves"], by["sweep_moves"], bx["seed"]))
                break

    n_plus = sum(1 for b, h, _ in pairs if h < b)  # hive better (fewer sweeps)
    n_minus = sum(1 for b, h, _ in pairs if h > b)  # hive worse
    n_ties = sum(1 for b, h, _ in pairs if h == b)
    n = len(pairs)

    if n == 0:
        return 0, 0, 0, None, "no data"

    # One-sided sign test: H0: P(hive < baseline) <= 0.5
    # p-value = P(X >= n_plus) where X ~ Binomial(n, 0.5), excluding ties
    n_nontied = n_plus + n_minus
    if n_nontied == 0:
        return n, n_plus, n_minus, 0.5, "all ties"

    # Sum tail from n_plus to n_nontied
    p_value = 0.0
    for k in range(n_plus, n_nontied + 1):
        # binomial coefficient: C(n_nontied, k)
        p_value += math.comb(n_nontied, k) * (0.5 ** n_nontied)

    if n_plus > n_minus:
        direction = "hive_memory reduces sweep_moves"
    elif n_minus > n_plus:
        direction = "hive_memory INCREASES sweep_moves (reversal)"
    else:
        direction = "no difference (all ties)"

    return n, n_plus, n_minus, p_value, direction


def aggregate_reduction(x, y):
    """Total sweep moves: baseline vs hive. Returns (total_b, total_h, pct_change)."""
    total_b = sum(r["sweep_moves"] for r in x)
    total_h = sum(r["sweep_moves"] for r in y)
    if total_b == 0:
        return total_b, total_h, None
    pct = (total_h - total_b) / total_b * 100
    return total_b, total_h, pct


def main():
    print("=" * 60)
    print("E13 Chain-Prioritized Foraging — Results Analysis")
    print("=" * 60)

    for arm in ["baseline", "hive_memory", "hive_memory_comm"]:
        data = load_results(arm)
        if data is None:
            print(f"\n❌ {arm}: NO RESULTS FILE")
            continue
        runs = data["runs"]
        successes = sum(r["success"] for r in runs)
        total_sweep = sum(r["sweep_moves"] for r in runs)
        total_steps = sum(r["steps_to_success"] for r in runs if r["success"])
        mean_steps = total_steps / max(1, successes)
        deliveries = sum(r["deliveries"] for r in runs)
        cost = data["totals"]["estimated_cost_usd"]
        tokens = data["totals"]["total_tokens"]
        memory_hits = sum(r.get("memory_hits", 0) for r in runs)
        mrh = sum(r.get("memory_relevant_hits", 0) for r in runs)

        print(f"\n{'─' * 55}")
        print(f"  ARM: {arm}")
        print(f"{'─' * 55}")
        print(f"  Runs: {len(runs)}")
        print(f"  Successes: {successes}/{len(runs)}")
        print(f"  Deliveries: {deliveries}")
        print(f"  Mean steps (successful): {mean_steps:.1f}")
        print(f"  Total sweep_moves: {total_sweep}")
        print(f"  Memory hits: {memory_hits}")
        print(f"  Memory relevant hits: {mrh}")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Tokens: {tokens}")

        if arm == "baseline":
            baseline_data = data
            baseline_runs = runs
        elif arm == "hive_memory":
            hive_data = data
            hive_runs = runs
        elif arm == "hive_memory_comm":
            comm_data = data
            comm_runs = runs

    # Sign test: baseline vs hive_memory
    print("\n" + "=" * 60)
    print("SIGN TEST: baseline vs hive_memory (sweep_moves per seed)")
    print("=" * 60)

    if "baseline_data" in dir() and "hive_data" in dir():
        n, n_plus, n_minus, p_val, direction = sign_test_paired(
            baseline_runs, hive_runs
        )
        total_b, total_h, pct = aggregate_reduction(baseline_runs, hive_runs)

        print(f"\n  Seeds compared: {n}")
        print(f"  Hive better (fewer sweeps): {n_plus}")
        print(f"  Hive worse (more sweeps): {n_minus}")
        print(f"  Ties: {n - n_plus - n_minus}")
        print(f"  Sign test p-value (one-sided): {p_val:.4f}")
        print(f"  Direction: {direction}")
        print(f"\n  Aggregate sweep moves:")
        print(f"    Baseline:  {total_b}")
        print(f"    Hive:      {total_h}")
        if pct is not None:
            print(f"    Change:    {pct:+.1f}%")

        # Verdict check against pre-registered bar
        print(f"\n{'─' * 55}")
        print("  PRE-REGISTERED BAR CHECK")
        print(f"{'─' * 55}")
        print(f"  Reduction ≥ 5%?  {'YES' if pct is not None and pct <= -5 else 'NO'} ({pct:+.1f}%)")
        print(f"  p < 0.05?        {'YES' if p_val is not None and p_val < 0.05 else 'NO'} (p={p_val:.4f})")

        if pct is not None and pct <= -5 and p_val is not None and p_val < 0.05:
            verdict = "GENALITY SUPPORTED — headline holds across families"
        elif p_val is not None and p_val >= 0.05:
            verdict = "GENALITY REFUTED — headline narrowed to single task family"
        elif pct is not None and pct > -5:
            verdict = "GENALITY REFUTED (effect < 5%) — headline narrowed"
        else:
            verdict = "PARTIAL — report effect size, do not upgrade to claim"

        print(f"\n  VERDICT: {verdict}")
        print(f"{'─' * 55}")
    else:
        print("  ❌ Missing baseline or hive_memory results")

    # Sign test: baseline vs hive_memory_comm (secondary)
    print("\n" + "=" * 60)
    print("SIGN TEST (secondary): baseline vs hive_memory_comm (sweep_moves per seed)")
    print("=" * 60)

    if "baseline_data" in dir() and "comm_data" in dir():
        n2, n_plus2, n_minus2, p_val2, direction2 = sign_test_paired(
            baseline_runs, comm_runs
        )
        total_b2, total_c2, pct2 = aggregate_reduction(baseline_runs, comm_runs)

        print(f"\n  Seeds compared: {n2}")
        print(f"  Comm better (fewer sweeps): {n_plus2}")
        print(f"  Comm worse (more sweeps): {n_minus2}")
        print(f"  Ties: {n2 - n_plus2 - n_minus2}")
        print(f"  Sign test p-value (one-sided): {p_val2:.4f}")
        print(f"  Direction: {direction2}")
        print(f"\n  Aggregate sweep moves:")
        print(f"    Baseline:  {total_b2}")
        print(f"    Comm:      {total_c2}")
        if pct2 is not None:
            print(f"    Change:    {pct2:+.1f}%")
    else:
        print("  ❌ Missing baseline or hive_memory_comm results")

    print("\n" + "=" * 60)
    print("END ANALYSIS")
    print("=" * 60)


if __name__ == "__main__":
    main()
