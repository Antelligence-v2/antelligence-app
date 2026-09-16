#!/usr/bin/env python3
"""Parameter sensitivity sweep over pheromone params.

Runs an N×M grid over trail_decay × recruitment_diffusion, scores each run
by kill_rate * efficiency (efficiency = deliveries / steps), and writes a
ranked JSON to feeds/parameter-sensitivity.json.

CLI: --bots N --steps N --grid-points K --output PATH --seed S --dry-run

In --dry-run (or ANTELLIGENCE_TEST=1):
    Skips actual simulation; returns deterministic mock metrics based on param
    values so tests can run fast without spinning up the full model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import List, Dict, Any

# Make backend importable
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "backend"))


def _is_dry_run_env() -> bool:
    return os.environ.get("ANTELLIGENCE_TEST", "").strip() in {"1", "true", "yes"}


def _mock_metrics(trail_decay: float, recruitment_diffusion: float, steps: int) -> Dict[str, Any]:
    """Deterministic mock metrics for dry-run mode."""
    kill_rate = 20.0 + trail_decay * 50.0 + recruitment_diffusion * 1e6
    kill_rate = max(0.0, min(100.0, kill_rate))
    deliveries = int(kill_rate / 5)
    efficiency = deliveries / steps if steps > 0 else 0.0
    score = kill_rate * efficiency
    return {
        "kill_rate": round(kill_rate, 4),
        "deliveries": deliveries,
        "efficiency": round(efficiency, 6),
        "score": round(score, 6),
        "steps": steps,
    }


def _real_metrics(
    trail_decay: float,
    recruitment_diffusion: float,
    n_bots: int,
    steps: int,
    seed: int,
) -> Dict[str, Any]:
    """Run actual simulation and return metrics."""
    import time
    import numpy as np
    import random as _random

    np.random.seed(seed)
    _random.seed(seed)

    from nanobot_simulation import TumorNanobotModel

    pheromone_params = {
        "trail_decay": trail_decay,
        "recruitment_diffusion": recruitment_diffusion,
    }

    domain = 450.0
    model = TumorNanobotModel(
        domain_size=domain,
        voxel_size=20.0,
        n_nanobots=n_bots,
        tumor_radius=150,
        agent_type="heuristic",
        with_queen=False,
        use_llm_queen=False,
        pheromone_params=pheromone_params,
        seed=seed,
    )

    total_cells = len(model.geometry.tumor_cells)

    for _ in range(steps):
        model.step()

    living = len(model.geometry.get_living_cells())
    kills = total_cells - living
    kill_rate = (kills / total_cells * 100.0) if total_cells > 0 else 0.0
    deliveries = sum(bot.deliveries_made for bot in model.nanobots)
    efficiency = deliveries / steps if steps > 0 else 0.0
    score = kill_rate * efficiency

    return {
        "kill_rate": round(kill_rate, 4),
        "deliveries": deliveries,
        "efficiency": round(efficiency, 6),
        "score": round(score, 6),
        "steps": steps,
    }


def build_grid(grid_points: int) -> tuple[List[float], List[float]]:
    """Build linearly-spaced grid for trail_decay and recruitment_diffusion."""
    import numpy as np
    # trail_decay range: 0.03 to 0.15 (centered on default 0.0693)
    trail_decays = list(np.linspace(0.03, 0.15, grid_points))
    # recruitment_diffusion range: 1e-7 to 1e-5 (log-spaced around default 2e-6)
    recruitment_diffusions = list(np.logspace(-7, -5, grid_points))
    return trail_decays, recruitment_diffusions


def run_sweep(
    n_bots: int,
    steps: int,
    grid_points: int,
    seed: int,
    dry_run: bool,
) -> Dict[str, Any]:
    """Run the full parameter grid sweep and return ranked results."""
    if grid_points <= 0:
        raise ValueError("grid_points must be positive")
    trail_decays, recruitment_diffusions = build_grid(grid_points)

    results = []
    for td, rd in product(trail_decays, recruitment_diffusions):
        if dry_run:
            m = _mock_metrics(td, rd, steps)
        else:
            m = _real_metrics(td, rd, n_bots, steps, seed)

        results.append({
            "trail_decay": round(td, 8),
            "recruitment_diffusion": rd,
            "kill_rate": m["kill_rate"],
            "deliveries": m["deliveries"],
            "efficiency": m["efficiency"],
            "score": m["score"],
            "steps": m["steps"],
        })

    # Sort by score descending and assign rank
    results.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    top = results[0]
    top_params = {
        "trail_decay": top["trail_decay"],
        "recruitment_diffusion": top["recruitment_diffusion"],
        "score": top["score"],
        "kill_rate": top["kill_rate"],
        "efficiency": top["efficiency"],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grid_points": grid_points,
        "bots": n_bots,
        "steps": steps,
        "seed": seed,
        "results": results,
        "top_params": top_params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parameter sensitivity sweep over pheromone params")
    parser.add_argument("--bots", type=int, default=5, help="Number of nanobots")
    parser.add_argument("--steps", type=int, default=50, help="Simulation steps per run")
    parser.add_argument("--grid-points", type=int, default=3, help="Grid resolution per axis (total = K*K)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual simulation, use mock metrics")
    args = parser.parse_args()

    if args.grid_points <= 0:
        parser.error("--grid-points must be positive")

    is_dry = args.dry_run or _is_dry_run_env()

    output_path = Path(args.output) if args.output else _ROOT / "feeds" / "parameter-sensitivity.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = run_sweep(
        n_bots=args.bots,
        steps=args.steps,
        grid_points=args.grid_points,
        seed=args.seed,
        dry_run=is_dry,
    )

    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(data['results'])} results to {output_path}")
    print(f"Top params: trail_decay={data['top_params']['trail_decay']:.4f}, "
          f"recruitment_diffusion={data['top_params']['recruitment_diffusion']:.2e}, "
          f"score={data['top_params']['score']:.4f}")


if __name__ == "__main__":
    main()
