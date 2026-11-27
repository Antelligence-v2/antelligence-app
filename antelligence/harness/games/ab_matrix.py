"""A/B variant matrix runner: holds scenario + seed fixed while swapping (model_stack, harness_variant)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np

from antelligence.harness.core import EnvAdapter
from antelligence.harness.games.checker import GameChecker
from antelligence.harness.games.runner import GameEpisodeResult, PolicyFn, run_episode
from antelligence.harness.scorecard import Outcome, compare, paired_bootstrap


@dataclass(frozen=True)
class ABVariant:
    """One swappable (model_stack, harness_variant) configuration."""

    name: str
    model_stack: str
    harness_variant: str
    policy: PolicyFn
    use_memory: bool = True
    checker: Optional[GameChecker] = None


def _four_axes_summary(results: Sequence[GameEpisodeResult]) -> Dict[str, Any]:
    all_lat = [x for r in results for x in r.decision_latencies_s] or [0.0]
    n = len(results)
    mean_score = sum(r.score for r in results) / n
    mean_base = sum(r.baseline_score for r in results) / n
    total_viol = sum(r.violations for r in results)
    return {
        "n": n,
        "fidelity_tier": results[0].fidelity_tier,
        "latency": {
            "decision_p50_s": round(float(np.percentile(all_lat, 50)), 6),
            "decision_p95_s": round(float(np.percentile(all_lat, 95)), 6),
            "mean_wall_time_s": round(sum(r.latency_s for r in results) / n, 6),
        },
        "accuracy": {
            "mean_score": round(mean_score, 4),
            "completion_rate": round(sum(1 for r in results if r.done) / n, 4),
            "baseline_S_score": round(mean_base, 4),
            "lift_over_S": round(mean_score - mean_base, 4),
        },
        "safety": {
            "total_violations": total_viol,
            "violation_free_rate": round(sum(1 for r in results if r.violations == 0) / n, 4),
        },
        "cost": {
            "total_cost_usd": round(sum(r.cost_usd for r in results), 6),
            "mean_cost_usd": round(sum(r.cost_usd for r in results) / n, 6),
            "total_l1_calls": sum(r.l1_calls for r in results),
            "checker_fires": sum(r.checker_fires for r in results),
        },
    }


def _to_outcome(v: ABVariant, r: GameEpisodeResult) -> Outcome:
    return Outcome(
        task=f"seed-{r.seed}",
        kind="interactive_game",
        variant=v.name,
        answer=r.state_hash,
        score=r.score,
        format_ok=True,
        seconds=round(r.latency_s, 6),
        cost_usd=round(r.cost_usd, 6),
        calls=r.l1_calls,
        metadata={
            "model_stack": v.model_stack,
            "harness_variant": v.harness_variant,
            "violations": r.violations,
            "fidelity_tier": r.fidelity_tier,
            "baseline_score": r.baseline_score,
        },
    )


def run_ab_matrix(
    env_factory: Callable[[], EnvAdapter],
    variants: Sequence[ABVariant],
    seeds: Sequence[int],
    *,
    scenario_config: Optional[Mapping[str, Any]] = None,
    max_steps: int = 50,
    baseline_name: Optional[str] = None,
    l0_dir: Optional[Path] = None,
    bootstrap_reps: int = 2000,
) -> Dict[str, Any]:
    """Run all variants over identical (scenario, seeds) and return 4-axis + paired bootstrap report."""
    if not variants or not seeds:
        raise ValueError("variants and seeds must be non-empty")

    raw_results: Dict[str, List[GameEpisodeResult]] = {}
    outcomes: Dict[str, List[Outcome]] = {}
    for v in variants:
        v_res: List[GameEpisodeResult] = []
        v_out: List[Outcome] = []
        for s in seeds:
            l0_path = (Path(l0_dir) / f"{v.name}_seed_{s}.jsonl") if l0_dir is not None else None
            res = run_episode(
                env_factory(),
                v.policy,
                seed=s,
                config=scenario_config,
                max_steps=max_steps,
                use_memory=v.use_memory,
                checker=v.checker,
                l0_path=l0_path,
                run_id=f"{v.name}-s{s}",
            )
            v_res.append(res)
            v_out.append(_to_outcome(v, res))
        raw_results[v.name] = v_res
        outcomes[v.name] = v_out

    base_key = baseline_name or variants[0].name
    base_res = raw_results[base_key]
    base_out = outcomes[base_key]

    paired: Dict[str, Any] = {}
    for v in variants:
        if v.name == base_key:
            continue
        comp = compare(outcomes[v.name], base_out, reps=bootstrap_reps)
        v_diff, v_lo, v_hi = paired_bootstrap(
            [a.violations - b.violations for a, b in zip(raw_results[v.name], base_res)],
            reps=bootstrap_reps,
        )
        c_diff, c_lo, c_hi = paired_bootstrap(
            [a.cost_usd - b.cost_usd for a, b in zip(raw_results[v.name], base_res)],
            reps=bootstrap_reps,
        )
        comp["violations_delta"] = round(v_diff, 4)
        comp["violations_ci95"] = [round(v_lo, 4), round(v_hi, 4)]
        comp["cost_delta_usd"] = round(c_diff, 6)
        comp["cost_ci95"] = [round(c_lo, 6), round(c_hi, 6)]
        paired[v.name] = comp

    return {
        "baseline": base_key,
        "seeds": list(seeds),
        "variants": {v.name: _four_axes_summary(raw_results[v.name]) for v in variants},
        "paired_vs_baseline": paired,
    }
