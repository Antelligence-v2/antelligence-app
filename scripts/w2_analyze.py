#!/usr/bin/env python3
"""Preregistered analysis for the W2 SLM-vs-frontier benchmark.

Reads ``docs/research/slm-vs-frontier-20261008/cells/*.jsonl`` (never the smoke files)
and writes ``results.csv`` (one row per model x world x domain x arm, seeds pooled),
``results-by-seed.csv`` and ``comparisons.json``. Pure stdlib + the engine's own
``antelligence/experiments/stats.py``; deterministic (bootstrap RNG seed fixed).

Denominator rule: every *requested* cell counts. A cell is a success only if the
world/verifier marked it correct. Abstained, invalid, error (transport/truncation),
and missing (requested but never written) cells are all failures in ``accuracy``.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from antelligence.experiments.stats import paired_comparison, sign_test_p, wilson_interval  # noqa: E402

OUT = ROOT / "docs/research/slm-vs-frontier-20261008"
Z_ONE_SIDED_95 = 1.6448536269514722
BOOT_REPS = 10_000
BOOT_SEED = 20261008
QA_ARMS = ("single", "independent_vote", "signal_board", "evidence_exchange", "evidence_isolated", "solo_refine")

# Preregistered comparisons: (label, model_a, arm_a, model_b, arm_b). Treatment is (a), baseline is (b).
SMALL = "qwen38-27b-q3k"
STRONG = "claude-sonnet-5.5"
PRIMARY = [
    ("a1 small swarm(signal_board) vs small single", SMALL, "signal_board", SMALL, "single"),
    ("a2 small swarm(evidence_exchange) vs small single", SMALL, "evidence_exchange", SMALL, "single"),
    ("b1 small swarm(signal_board) vs frontier-strong single", SMALL, "signal_board", STRONG, "single"),
    ("b2 small swarm(evidence_exchange) vs frontier-strong single", SMALL, "evidence_exchange", STRONG, "single"),
]
SECONDARY_ARMS = [
    ("communication beyond more calls: signal_board vs independent_vote", "signal_board", "independent_vote"),
    ("communication beyond more calls: signal_board vs solo_refine", "signal_board", "solo_refine"),
    ("sharing beyond sharding: evidence_exchange vs evidence_isolated", "evidence_exchange", "evidence_isolated"),
    ("voting vs single", "independent_vote", "single"),
]


def load_cells() -> List[dict]:
    rows = []
    for path in sorted((OUT / "cells").glob("*.jsonl")):
        if path.name.startswith("smoke-"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dedupe(rows: List[dict]) -> Tuple[Dict[tuple, dict], int]:
    """First write wins; duplicates (only possible after a crash-resume) are counted, not used."""
    cells: Dict[tuple, dict] = {}
    duplicates = 0
    for row in rows:
        key = (row["model_key"], row["world"], row["domain"], row["arm"], row["seed"], row["task_id"])
        if key in cells:
            duplicates += 1
            continue
        cells[key] = row
    return cells, duplicates


def wilson_lower_one_sided(successes: int, trials: int) -> Optional[float]:
    interval = wilson_interval(successes, trials, z=Z_ONE_SIDED_95)
    return None if interval is None else interval["low"]


def summarize(cells: Dict[tuple, dict], requested: Dict[tuple, set]) -> List[dict]:
    """requested[(model, world, domain, arm, seed)] = set(task_ids) that were planned."""
    groups: Dict[tuple, List[Optional[dict]]] = defaultdict(list)
    for (model, world, domain, arm, seed), task_ids in requested.items():
        for task_id in sorted(task_ids):
            groups[(model, world, domain, arm)].append(cells.get((model, world, domain, arm, seed, task_id)))
    out = []
    for (model, world, domain, arm), group in sorted(groups.items()):
        present = [c for c in group if c is not None]
        n = len(group)
        correct = sum(bool(c["correct"]) for c in present)
        status = defaultdict(int)
        for c in present:
            status[c["status"]] += 1
        missing = n - len(present)
        answered = sum(1 for c in present if c["status"] in ("completed", "completed_with_failures")
                       and (world != "research_qa" or c.get("answer") is not None))
        first = present[0] if present else {}
        cost = sum(float(c.get("cost_usd") or 0.0) for c in present)
        out.append({
            "model_key": model, "tier": first.get("tier"), "billing": first.get("billing"), "model": first.get("model"),
            "world": world, "domain": domain, "arm": arm,
            "seeds": len({c["seed"] for c in present}), "requested": n, "missing": missing,
            "correct": correct, "accuracy": round(correct / n, 4) if n else None,
            "wilson_lower_95_one_sided": None if not n else round(wilson_lower_one_sided(correct, n), 4),
            "answered": answered, "coverage": round(answered / n, 4) if n else None,
            "answered_accuracy": round(correct / answered, 4) if answered else None,
            "abstained": status["abstained"], "invalid": status["invalid"],
            "error_transport": status["error"], "completed_with_failures": status["completed_with_failures"],
            "failed_calls": sum(int(c.get("failed_calls") or 0) for c in present),
            "logical_calls": sum(int(c.get("calls") or 0) for c in present),
            "physical_calls": sum(int(c.get("physical_calls", c.get("calls", 0) - c.get("cached_calls", 0)) or 0)
                                  for c in present),
            "prompt_tokens": sum(int(c.get("prompt_tokens") or 0) for c in present),
            "completion_tokens": sum(int(c.get("completion_tokens") or 0) for c in present),
            "model_latency_s": round(sum(float(c.get("latency_s") or 0.0) for c in present), 1),
            "mean_cell_wall_s": round(sum(float(c.get("wall_s") or 0.0) for c in present) / len(present), 2)
            if present else None,
            "cost_usd": round(cost, 6),
            "cost_per_correct_usd": round(cost / correct, 6) if correct else None,
        })
    return out


def paired_vectors(cells, requested, model_a, arm_a, model_b, arm_b, world="research_qa", domain=None):
    """Return aligned per-(domain, seed, task) success vectors for the cells requested in BOTH arms."""
    keys_a = {(d, s, t) for (m, w, d, a, s), ts in requested.items() if m == model_a and w == world and a == arm_a
              and (domain is None or d == domain) for t in ts}
    keys_b = {(d, s, t) for (m, w, d, a, s), ts in requested.items() if m == model_b and w == world and a == arm_b
              and (domain is None or d == domain) for t in ts}
    if model_a != model_b:
        # Different models share task ids but may differ in seeds: pair on (domain, task) within common seeds.
        pass
    common = sorted(keys_a & keys_b)
    va = [1.0 if (cells.get((model_a, world, d, arm_a, s, t)) or {}).get("correct") else 0.0 for d, s, t in common]
    vb = [1.0 if (cells.get((model_b, world, d, arm_b, s, t)) or {}).get("correct") else 0.0 for d, s, t in common]
    return common, va, vb


def bootstrap_ci(common, va, vb) -> Optional[Dict[str, float]]:
    """Percentile CI for mean paired difference, resampling *tasks* (clusters across seeds)."""
    if not common:
        return None
    by_task: Dict[tuple, List[float]] = defaultdict(list)
    for (d, s, t), a, b in zip(common, va, vb):
        by_task[(d, t)].append(a - b)
    tasks = sorted(by_task)
    rng = random.Random(BOOT_SEED)
    stats = []
    for _ in range(BOOT_REPS):
        sample = [by_task[tasks[rng.randrange(len(tasks))]] for _ in tasks]
        flat = [x for group in sample for x in group]
        stats.append(sum(flat) / len(flat))
    stats.sort()
    return {"low": round(stats[int(0.025 * BOOT_REPS)], 4), "high": round(stats[int(0.975 * BOOT_REPS) - 1], 4),
            "clusters": len(tasks)}


def compare(cells, requested, label, model_a, arm_a, model_b, arm_b, domain=None) -> dict:
    common, va, vb = paired_vectors(cells, requested, model_a, arm_a, model_b, arm_b, domain=domain)
    comp = paired_comparison(vb, va, lower_is_better=False)  # baseline first, treatment second
    n = len(common)
    return {"label": label, "domain": domain or "both", "treatment": f"{model_a}:{arm_a}",
            "baseline": f"{model_b}:{arm_b}", "pairs": n,
            "treatment_accuracy": round(sum(va) / n, 4) if n else None,
            "baseline_accuracy": round(sum(vb) / n, 4) if n else None,
            "mean_difference": round(comp["mean_delta"], 4) if comp["mean_delta"] is not None else None,
            "ci95_task_bootstrap": bootstrap_ci(common, va, vb),
            "treatment_wins": comp["wins"], "baseline_wins": comp["losses"], "ties": comp["ties"],
            "sign_test_p": comp["sign_test_p"]}


def holm(results: List[dict]) -> None:
    ordered = sorted((r for r in results if r["sign_test_p"] is not None), key=lambda r: r["sign_test_p"])
    m = len(ordered)
    running = 0.0
    for i, r in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * r["sign_test_p"]))
        r["holm_p"] = round(running, 6)
    for r in results:
        r.setdefault("holm_p", None)
        lo = (r["ci95_task_bootstrap"] or {}).get("low")
        hi = (r["ci95_task_bootstrap"] or {}).get("high")
        if r["holm_p"] is not None and r["holm_p"] < 0.05 and lo is not None and lo > 0:
            r["verdict"] = "treatment better"
        elif r["holm_p"] is not None and r["holm_p"] < 0.05 and hi is not None and hi < 0:
            r["verdict"] = "treatment worse"
        else:
            r["verdict"] = "no reliable difference"


def requested_from_runlog() -> Dict[tuple, set]:
    """Planned cells, reconstructed from the run plan the harness logged (never from outcomes)."""
    fixture = json.loads((ROOT / "backend/research_fixtures/tasks.json").read_text())
    eval_ids = json.loads((OUT / "eval-task-ids.json").read_text())
    domain_of = {t["task_id"]: t["domain"] for t in fixture["tasks"]}
    requested: Dict[tuple, set] = defaultdict(set)
    log = OUT / "run-log.jsonl"
    for line in log.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event") != "start" or row.get("smoke"):
            continue
        argv = row["argv"]

        def opt(name, default=None, many=False):
            if name not in argv:
                return default
            i = argv.index(name) + 1
            if not many:
                return argv[i]
            vals = []
            while i < len(argv) and not argv[i].startswith("--"):
                vals.append(argv[i])
                i += 1
            return vals

        model, world = opt("--model"), opt("--world")
        if world == "research_qa":
            arms = opt("--arms", list(QA_ARMS), many=True)
            seeds = [int(s) for s in opt("--seeds", ["0"], many=True)]
            per = int(opt("--per-domain", "30"))
            ids = [t for t in eval_ids if domain_of[t] == "medical"][:per] + \
                  [t for t in eval_ids if domain_of[t] == "finance"][:per]
            for seed in seeds:
                for arm in arms:
                    for t in ids:
                        requested[(model, world, domain_of[t], arm, seed)].add(t)
        else:
            from antelligence.worlds.foraging import ARMS as FA
            from antelligence.worlds.task_dag import ARMS as DA
            arms = opt("--arms", list(DA if world == "task_dag" else FA), many=True)
            fixtures = [int(f) for f in opt("--fixtures", [], many=True)]
            prefix = "e15-fixture-" if world == "task_dag" else "e13-seed-"
            for arm in arms:
                for f in fixtures:
                    requested[(model, world, world, arm, f)].add(f"{prefix}{f}")
    return requested


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cells, duplicates = dedupe(load_cells())
    requested = requested_from_runlog()
    rows = summarize(cells, requested)
    write_csv(OUT / "results.csv", rows)
    by_seed = []
    for (model, world, domain, arm, seed), ts in sorted(requested.items()):
        by_seed += [dict(r, seed=seed) for r in summarize(cells, {(model, world, domain, arm, seed): ts})]
    write_csv(OUT / "results-by-seed.csv", by_seed)

    primary = [compare(cells, requested, *p) for p in PRIMARY]
    holm(primary)
    secondary = []
    models = sorted({k[0] for k in requested if k[1] == "research_qa"})
    for model in models:
        for label, a, b in SECONDARY_ARMS:
            secondary.append(compare(cells, requested, f"{model}: {label}", model, a, model, b))
    for r in secondary:
        r["holm_p"] = None
        r["verdict"] = "exploratory (uncorrected)"
    per_domain = [compare(cells, requested, f"{p[0]} [{d}]", *p[1:], domain=d)
                  for p in PRIMARY for d in ("medical", "finance")]
    other_worlds = []
    for world in ("task_dag", "foraging"):
        for model in sorted({k[0] for k in requested if k[1] == world}):
            arms = sorted({k[3] for k in requested if k[0] == model and k[1] == world})
            base = "solo_planner" if world == "task_dag" else "baseline"
            for arm in arms:
                if arm == base:
                    continue
                common, va, vb = paired_vectors(cells, requested, model, arm, model, base, world=world)
                comp = paired_comparison(vb, va, lower_is_better=False)
                other_worlds.append({"world": world, "model": model, "treatment": arm, "baseline": base,
                                     "pairs": len(common), "treatment_successes": int(sum(va)),
                                     "baseline_successes": int(sum(vb)), "sign_test_p": comp["sign_test_p"]})
    report = {"duplicates_ignored": duplicates, "requested_cells": sum(len(v) for v in requested.values()),
              "written_cells": len(cells), "primary": primary, "primary_per_domain_exploratory": per_domain,
              "secondary": secondary, "other_worlds": other_worlds,
              "method": {"wilson": "one-sided 95% lower bound, z=1.6449, via antelligence.experiments.stats",
                         "paired_test": "exact two-sided sign test on discordant (task,seed) pairs, stats.py",
                         "ci": f"task-cluster bootstrap percentile 95%, {BOOT_REPS} reps, seed {BOOT_SEED}",
                         "multiplicity": "Holm over the 4 primary comparisons only"}}
    (OUT / "comparisons.json").write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    print(json.dumps({"rows": len(rows), "requested": report["requested_cells"], "written": len(cells),
                      "duplicates": duplicates}, indent=1))


if __name__ == "__main__":
    main()
