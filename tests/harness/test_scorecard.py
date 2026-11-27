"""Tests for numpy-vectorized scorecard, parity with pure-python reference, and speedup."""

from __future__ import annotations

import random
import statistics as st
import time
from typing import Sequence, Tuple

from antelligence.harness.core import Artifact, Task
from antelligence.harness.scorecard import (
    Outcome,
    OutcomeLog,
    bill,
    compare,
    fresh_in,
    paired_bootstrap,
    pareto,
    summary,
)


def _pure_python_paired_boot(diffs: Sequence[float], reps: int, seed: int = 20261029) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return st.mean(diffs), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def test_numpy_paired_bootstrap_parity_and_speedup():
    rng = random.Random(12345)
    diffs = [rng.choice([-1.0, 0.0, 0.0, 1.0, 1.0]) for _ in range(200)]
    reps = 10000

    t0 = time.perf_counter()
    py_mean, py_lo, py_hi = _pure_python_paired_boot(diffs, reps=reps, seed=20261029)
    py_elapsed = time.perf_counter() - t0

    # Warm up numpy once, then measure
    paired_bootstrap(diffs[:10], reps=10, seed=1)
    t1 = time.perf_counter()
    np_mean, np_lo, np_hi = paired_bootstrap(diffs, reps=reps, seed=20261029)
    np_elapsed = time.perf_counter() - t1

    assert abs(np_mean - py_mean) < 1e-12
    assert abs(np_lo - py_lo) < 0.015
    assert abs(np_hi - py_hi) < 0.015
    speedup = py_elapsed / max(np_elapsed, 1e-9)
    assert speedup > 50.0, f"expected >50x speedup, got {speedup:.1f}x (py={py_elapsed:.4f}s, np={np_elapsed:.4f}s)"


def test_scorecard_bill_compare_summary_pareto_and_log(tmp_path):
    tasks = [Task(id=f"t{i}", kind="ops") for i in range(1, 21)]
    base_outs = [
        bill(t, "baseline", "A", [Artifact(t.id, "frontier", "A", tokens_in=200, tokens_out=50, latency_s=1.0, cost_usd=0.01, calls=1)], score=0.5)
        for t in tasks
    ]
    ours_outs = [
        bill(t, "maker_checker", "B", [Artifact(t.id, "maker", "B", tokens_in=50, tokens_out=10, latency_s=0.2, cost_usd=0.001, calls=1)], score=1.0)
        for t in tasks
    ]
    cmp = compare(ours_outs, base_outs, reps=1000)
    assert cmp["n"] == 20
    assert cmp["score_gain"] == 0.5
    assert cmp["verdict"] == "beats it on all three"

    log = OutcomeLog(tmp_path / "outcomes.jsonl")
    for o in base_outs + ours_outs:
        log.add(o)
    loaded = log.read()
    assert len(loaded) == 40
    tbl = summary(loaded, baseline="baseline")
    assert tbl["maker_checker"]["vs_baseline"]["verdict"] == "beats it on all three"
    assert pareto(tbl) == ["maker_checker"]


def test_fresh_in_prefix_caching():
    prefix = "System instructions: follow the schema strictly. " * 2  # > 40 chars
    prompts = {
        "step1": prefix + "Question 1",
        "step2": prefix + "Question 2",
    }
    arts = [
        Artifact(task_id="t1", tool="step1", tokens_in=100, calls=1),
        Artifact(task_id="t1", tool="step2", tokens_in=100, calls=2),
    ]
    fresh = fresh_in(arts, prompts, lambda _: "m1", {"m1": 0.25})
    assert fresh[0] == 100
    assert fresh[1] < 100
