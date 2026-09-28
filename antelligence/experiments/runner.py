"""Run single engine runs and paired multi-arm experiments.

Every run produces: a result, an evaluator-owned verdict, a hash-chained event
log and a provenance bundle. Experiments run each arm on the same cases
(seeds) and compare each arm to the baseline pairwise on the world's primary
metric with an exact sign test. Reports carry their caveats with them.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from antelligence.experiments.registry import RunSpec, world
from antelligence.experiments.stats import paired_comparison, wilson_interval
from antelligence.experiments.store import EngineStore
from antelligence.experiments.version import engine_fingerprint
from antelligence.kernel.canonical import content_hash
from antelligence.kernel.verifier import classify_episode
from antelligence.provenance.bundle import build_bundle
from antelligence.provenance.outbox import ProvenanceOutbox

CAVEATS = (
    "Agents are rule policies unless stated otherwise; these are not LLM results.",
    "Worlds are synthetic research models; tumor results are not clinical evidence.",
    "Sign-test p-values are per comparison and not corrected for multiple comparisons.",
    "Bundles are replayable provenance (trust_tier=local_replay, proof_ok=false), not cryptographic proofs.",
)


SIGNIFICANCE = 0.05


def recommend(comparisons: Dict[str, Dict[str, Any]], arms_summary: Dict[str, Dict[str, Any]], *,
              baseline: str, metric_label: str, lower_is_better: bool) -> Dict[str, Any]:
    """Pick the strategy that works, or say that none did.

    An arm counts as *better* only if it beats the baseline on more seeds than it
    loses, the paired sign test gives p < 0.05, and it had no unsafe acts or
    policy failures. Among better arms, the one with the largest average
    improvement wins (ties: smaller p).
    """
    verdicts: Dict[str, Dict[str, Any]] = {}
    better: List[str] = []
    for arm, comp in comparisons.items():
        summary = arms_summary[arm]
        p = comp["sign_test_p"]
        significant = p is not None and p < SIGNIFICANCE
        if summary["unsafe_applied"] or summary["policy_failures"]:
            verdict = "excluded"
            reason = "had unsafe acts or failed runs"
        elif significant and comp["wins"] > comp["losses"]:
            verdict = "better"
            reason = f"better on {comp['wins']} of {comp['pairs']} seeds (p = {p:.2g})"
            better.append(arm)
        elif significant and comp["losses"] > comp["wins"]:
            verdict = "worse"
            reason = f"worse on {comp['losses']} of {comp['pairs']} seeds (p = {p:.2g})"
        else:
            verdict = "no_clear_difference"
            reason = ("identical on every seed" if comp["ties"] == comp["pairs"] else
                      f"{comp['wins']} better / {comp['losses']} worse / {comp['ties']} tied, not significant")
        verdicts[arm] = {"verdict": verdict, "reason": reason, "pct_change": comp["pct_change"],
                         "mean_delta": comp["mean_delta"], "p": p}

    def gain(arm: str) -> float:
        delta = comparisons[arm]["mean_delta"] or 0.0
        return -delta if lower_is_better else delta

    pairs = max((c["pairs"] for c in comparisons.values()), default=0)
    min_p = 2 * 0.5 ** pairs if pairs else None  # smallest two-sided sign-test p at this many seeds
    underpowered = min_p is not None and min_p >= SIGNIFICANCE

    if better:
        best = max(better, key=lambda arm: (gain(arm), -(comparisons[arm]["sign_test_p"] or 1.0), arm))
        comp = comparisons[best]
        change = comp["pct_change"]
        change_text = f"{change:+.0f}% {metric_label}" if change is not None else f"change in {metric_label}"
        summary = (f"{best} works best: {change_text} vs {baseline}, better on {comp['wins']} of "
                   f"{comp['pairs']} seeds (p = {comp['sign_test_p']:.2g}), 0 unsafe acts.")
    elif underpowered:
        best = None
        summary = (f"Too few seeds to decide: with {pairs} seeds the smallest possible p is {min_p:.2g}, "
                   f"so no difference can reach p < {SIGNIFICANCE}. Use at least 6 seeds.")
    else:
        best = None
        summary = f"No strategy beat {baseline} significantly on {metric_label} across {pairs} seeds."
    return {"best_arm": best, "baseline": baseline, "summary": summary, "significance": SIGNIFICANCE,
            "seeds": pairs, "underpowered": underpowered, "verdicts": verdicts}


def run_id_for(spec: RunSpec) -> str:
    return f"{spec.world}-{spec.arm}-{spec.case}-{spec.key[:10]}"


def execute_run(spec: RunSpec, *, store: Optional[EngineStore] = None, outbox: Optional[ProvenanceOutbox] = None,
                experiment_id: Optional[str] = None) -> Dict[str, Any]:
    ws = world(spec.world)
    run_id = run_id_for(spec)
    scheduler = ws.build(spec, run_id)
    result = scheduler.run()
    goal = bool(result.metrics.get(ws.success_metric))
    verdict = classify_episode(scheduler.log, goal_reached=goal).to_dict()
    bundle = build_bundle(result, spec.to_dict(), world_description=scheduler.world.describe(),
                          extra={"verdict": verdict})
    record = {
        "run_id": run_id,
        "spec": spec.to_dict(),
        "metrics": result.metrics,
        "ticks": result.ticks,
        "stopped_reason": result.stopped_reason,
        "trace_hash": result.trace_hash,
        "config_hash": result.config_hash,
        "event_count": result.event_count,
        "verdict": verdict,
        "bundle_hash": bundle["bundle_hash"],
    }
    if store is not None:
        frames = {"scene": scheduler.scene, "frames": scheduler.frames} if scheduler.frames else None
        store.save_run(record, bundle, scheduler.log, experiment_id=experiment_id, frames=frames)
    if outbox is not None:
        outbox.enqueue(bundle)
    return {**record, "bundle": bundle}


def experiment_request(world_name: str, arms: Optional[Sequence[str]], cases: Sequence[int], *,
                       params: Optional[Dict[str, Any]] = None, baseline: Optional[str] = None) -> Dict[str, Any]:
    ws = world(world_name)
    arms = list(dict.fromkeys(arms or ws.arms))  # no arms given: compare every strategy
    cases = list(dict.fromkeys(cases))
    if not arms or not cases:
        raise ValueError("at least one arm and one case are required")
    unknown = [a for a in arms if a not in ws.arms]
    if unknown:
        raise ValueError(f"unknown arms for {world_name}: {unknown}")
    baseline = baseline or (ws.baseline if ws.baseline in arms else arms[0])
    if baseline not in arms:
        raise ValueError("baseline must be one of the arms")
    if any(isinstance(c, bool) or not isinstance(c, int) or c < 0 for c in cases):
        raise ValueError("cases must be nonnegative integers (seeds)")
    return {"world": world_name, "arms": arms, "cases": cases, "baseline": baseline,
            "params": ws.resolve_params(params or {})}


def run_experiment(request: Dict[str, Any], *, store: Optional[EngineStore] = None,
                   outbox: Optional[ProvenanceOutbox] = None, force: bool = False) -> Dict[str, Any]:
    """Run (or return the cached report for) an experiment.

    The cache key includes the engine fingerprint, so a report is reused only if
    no engine, world or physics source changed since it was computed. ``force``
    re-runs and overwrites regardless.
    """
    request = experiment_request(request["world"], request.get("arms"), request["cases"],
                                 params=request.get("params"), baseline=request.get("baseline"))
    fingerprint = engine_fingerprint()
    experiment_id = content_hash({"request": request, "engine": fingerprint})[:16]
    if store is not None and not force:
        cached = store.get_experiment(experiment_id)
        if cached is not None:
            return cached
    ws = world(request["world"])
    runs: Dict[str, List[Dict[str, Any]]] = {}
    for arm in request["arms"]:
        runs[arm] = []
        for case in request["cases"]:
            record = execute_run(RunSpec(request["world"], arm, case, request["params"]), store=store,
                                 outbox=outbox, experiment_id=experiment_id)
            record.pop("bundle")
            runs[arm].append(record)

    metric = ws.primary_metric
    arms_summary = {}
    for arm, records in runs.items():
        values = [r["metrics"].get(metric) for r in records]
        present = [v for v in values if v is not None]
        successes = sum(bool(r["metrics"].get(ws.success_metric)) for r in records)
        arms_summary[arm] = {
            "cases": len(records),
            metric: {"total": sum(present), "mean": sum(present) / len(present) if present else None,
                     "missing": len(values) - len(present)},
            "successes": successes,
            "success_wilson_95": wilson_interval(successes, len(records)),
            "verdicts": dict(Counter(r["verdict"]["verdict"] for r in records)),
            "unsafe_applied": sum(r["verdict"]["unsafe_applied"] for r in records),
            "blocked_attempts": sum(r["verdict"]["blocked_attempts"] for r in records),
            "concurrent_blocks": sum(r["verdict"]["concurrent_blocks"] for r in records),
            "policy_failures": sum(r["verdict"]["policy_failures"] for r in records),
        }
    base = [r["metrics"].get(metric) for r in runs[request["baseline"]]]
    comparisons = {
        arm: paired_comparison(base, [r["metrics"].get(metric) for r in records], lower_is_better=ws.lower_is_better)
        for arm, records in runs.items() if arm != request["baseline"]
    }
    report = {
        "experiment_id": experiment_id,
        "engine_fingerprint": fingerprint,
        "request": request,
        "primary_metric": metric,
        "lower_is_better": ws.lower_is_better,
        "arms": arms_summary,
        "comparisons_vs_baseline": comparisons,
        "runs": {arm: [{k: r[k] for k in ("run_id", "spec", "trace_hash", "bundle_hash", "ticks")}
                       | {metric: r["metrics"].get(metric), "verdict": r["verdict"]["verdict"]}
                       for r in records] for arm, records in runs.items()},
        "recommendation": recommend(comparisons, arms_summary, baseline=request["baseline"],
                                    metric_label=ws.metric_label or metric, lower_is_better=ws.lower_is_better),
        "caveats": list(CAVEATS),
    }
    if store is not None:
        store.save_experiment(experiment_id, request, report)
    return report
