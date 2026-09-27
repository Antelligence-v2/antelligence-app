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
        store.save_run(record, bundle, scheduler.log, experiment_id=experiment_id)
    if outbox is not None:
        outbox.enqueue(bundle)
    return {**record, "bundle": bundle}


def experiment_request(world_name: str, arms: Sequence[str], cases: Sequence[int], *,
                       params: Optional[Dict[str, Any]] = None, baseline: Optional[str] = None) -> Dict[str, Any]:
    ws = world(world_name)
    arms = list(dict.fromkeys(arms))
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
                   outbox: Optional[ProvenanceOutbox] = None) -> Dict[str, Any]:
    request = experiment_request(request["world"], request["arms"], request["cases"],
                                 params=request.get("params"), baseline=request.get("baseline"))
    experiment_id = content_hash(request)[:16]
    if store is not None:
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
        "request": request,
        "primary_metric": metric,
        "lower_is_better": ws.lower_is_better,
        "arms": arms_summary,
        "comparisons_vs_baseline": comparisons,
        "runs": {arm: [{k: r[k] for k in ("run_id", "spec", "trace_hash", "bundle_hash", "ticks")}
                       | {metric: r["metrics"].get(metric), "verdict": r["verdict"]["verdict"]}
                       for r in records] for arm, records in runs.items()},
        "caveats": list(CAVEATS),
    }
    if store is not None:
        store.save_experiment(experiment_id, request, report)
    return report
