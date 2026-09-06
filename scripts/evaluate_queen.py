#!/usr/bin/env python3
"""Run a paired, offline Queen-policy evaluation on synthetic scenarios.

The fixed and Queen conditions receive the same seed and configuration.  The
Queen is heuristic-only, and every trial uses one model-owned Queen stepped
once per simulation step.  Output is always one JSON document with descriptive
percentage-point deltas; it does not claim statistical or clinical superiority.
"""

import argparse
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Iterator, Sequence

import numpy as np


_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@contextmanager
def _offline_environment() -> Iterator[None]:
    """Disable dotenv, chain reads/writes, and network credentials locally."""
    values = {
        "PYTHON_DOTENV_DISABLED": "1",
        "ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX": "0",
        "CHAIN_READ_ENABLED": "0",
        "CHAIN_WRITE_ENABLED": "0",
        "IO_SECRET_KEY": "",
        "LITELLM_API_KEY": "",
    }
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# Importing the legacy module emits startup diagnostics.  Keep those out of
# the JSON protocol even when this script is imported by a test.
with _offline_environment(), redirect_stdout(StringIO()):
    from nanobot_simulation import QueenNanobot, TumorNanobotModel


class _JsonArgumentParser(argparse.ArgumentParser):
    """Raise validation errors so main() can keep stdout JSON-only."""

    def error(self, message):
        raise ValueError(message)


SYNTHETIC_SCENARIOS = [
    {"tumor_radius": 80.0, "label": "synthetic_small_tumor"},
    {"tumor_radius": 150.0, "label": "synthetic_medium_tumor"},
    {"tumor_radius": 200.0, "label": "synthetic_large_tumor"},
]


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_float(value: float, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive number")
    return float(value)


def _average(runs: Sequence[dict], key: str) -> float:
    return round(float(np.mean([float(run[key]) for run in runs])), 2)


def run_trial(
    n_steps: int,
    n_bots: int,
    tumor_radius: float,
    seed: int,
    with_queen: bool,
    episode_length: int = 10,
):
    """Run one rule-based, offline trial and return measured metrics."""
    n_steps = _positive_int(n_steps, "steps")
    n_bots = _positive_int(n_bots, "bots")
    tumor_radius = _positive_float(tumor_radius, "radius")
    seed = _non_negative_int(seed, "seed")
    episode_length = _positive_int(episode_length, "episode_length")
    if not isinstance(with_queen, bool):
        raise ValueError("with_queen must be a boolean")

    np.random.seed(seed)
    random.seed(seed)

    start = time.perf_counter()
    queen_steps = 0
    with _offline_environment(), redirect_stdout(StringIO()):
        model = TumorNanobotModel(
            domain_size=max(400.0, tumor_radius * 3),
            voxel_size=20.0,
            n_nanobots=n_bots,
            tumor_radius=tumor_radius,
            agent_type="Rule-Based",
            with_queen=with_queen,
            use_llm_queen=False,
            pheromones_enabled=True,
            seed=seed,
        )
        # TumorNanobotModel owns the Queen.  Do not construct another one here.
        queen = model.queen if with_queen else None
        if with_queen and queen is None:
            raise RuntimeError("model did not create the requested Queen")

        total_cells = len(model.geometry.tumor_cells)
        if total_cells <= 0:
            raise ValueError("radius/configuration must produce a non-empty synthetic tumor")

        for _ in range(n_steps):
            model.step()
            if queen is not None:
                queen.step()
                queen_steps += 1

        living = len(model.geometry.get_living_cells())
        deliveries = sum(bot.deliveries_made for bot in model.nanobots)
        total_drug = sum(bot.total_drug_delivered for bot in model.nanobots)

    kills = total_cells - living
    kill_rate = kills / total_cells * 100.0
    result = {
        "seed": seed,
        "policy": "queen" if with_queen else "fixed",
        "with_queen": with_queen,
        "kills": kills,
        "total_cells": total_cells,
        "living_cells": living,
        "kill_rate": round(kill_rate, 2),
        "kill_rate_unit": "percent",
        "deliveries": deliveries,
        "total_drug": round(float(total_drug), 2),
        "queen_steps": queen_steps,
        "queen_episodes": queen.episode_counter if queen is not None else 0,
        "runtime_s": round(time.perf_counter() - start, 4),
    }
    if queen is not None:
        result["final_params"] = queen.worker_params.copy()
    return result


def run_evaluation(
    n_seeds: int,
    patients=None,
    n_steps: int = 50,
    n_bots: int = 5,
    episode_length: int = 10,
    verbose: bool = False,
    scenarios=None,
) -> dict:
    """Run paired fixed/Queen trials over synthetic scenario configurations.

    ``patients`` is retained as a Python-call compatibility name for older
    callers; emitted artifacts call these inputs synthetic scenarios.
    """
    n_seeds = _positive_int(n_seeds, "seeds")
    n_steps = _positive_int(n_steps, "steps")
    n_bots = _positive_int(n_bots, "bots")
    episode_length = _positive_int(episode_length, "episode_length")
    if scenarios is not None and patients is not None:
        raise ValueError("provide scenarios or patients, not both")
    source = scenarios if scenarios is not None else (
        SYNTHETIC_SCENARIOS if patients is None else patients
    )
    scenario_configs = list(source)
    if not scenario_configs:
        raise ValueError("at least one synthetic scenario is required")

    results = {"fixed": {}, "queen": {}}
    pairs = {}
    for scenario in scenario_configs:
        if not isinstance(scenario, dict):
            raise ValueError("each synthetic scenario must be an object")
        label = scenario.get("label")
        if not isinstance(label, str) or not label:
            raise ValueError("each synthetic scenario needs a non-empty label")
        radius = _positive_float(scenario.get("tumor_radius"), f"radius for {label}")
        results["fixed"][label] = []
        results["queen"][label] = []
        pairs[label] = []

        for seed in range(n_seeds):
            # Run each condition from the exact same deterministic inputs.
            fixed = run_trial(
                n_steps=n_steps,
                n_bots=n_bots,
                tumor_radius=radius,
                seed=seed,
                with_queen=False,
                episode_length=episode_length,
            )
            queen = run_trial(
                n_steps=n_steps,
                n_bots=n_bots,
                tumor_radius=radius,
                seed=seed,
                with_queen=True,
                episode_length=episode_length,
            )
            fixed["scenario"] = label
            queen["scenario"] = label
            delta = round(queen["kill_rate"] - fixed["kill_rate"], 2)
            results["fixed"][label].append(fixed)
            results["queen"][label].append(queen)
            pairs[label].append(
                {
                    "seed": seed,
                    "same_seed_and_config": True,
                    "fixed": fixed,
                    "queen": queen,
                    "delta_kill_rate_percentage_points": delta,
                }
            )

    summary = {}
    for policy in ("fixed", "queen"):
        all_kills = []
        for label in results[policy]:
            kills = results[policy][label]
            all_kills.extend(kills)
            summary[f"{policy}_{label}_avg"] = _average(kills, "kill_rate")
        summary[f"{policy}_overall_avg"] = _average(all_kills, "kill_rate")

    all_deltas = [
        pair["delta_kill_rate_percentage_points"]
        for scenario_pairs in pairs.values()
        for pair in scenario_pairs
    ]
    mean_delta = round(float(np.mean(all_deltas)), 2)
    summary.update(
        {
            "delta_kill_rate_percentage_points": mean_delta,
            "paired_delta_kill_rate_percentage_points": mean_delta,
            "delta_definition": (
                "queen kill rate minus fixed kill rate; percentage points, not relative percent"
            ),
            "interpretation": (
                "Descriptive paired local result only; a positive delta does not "
                "establish statistical or clinical superiority."
            ),
        }
    )

    return {
        "ok": True,
        "evaluation": "queen_policy_ablation",
        "scenario_type": "synthetic",
        "paired": True,
        "config": {
            "n_seeds": n_seeds,
            "n_scenarios": len(scenario_configs),
            "n_steps": n_steps,
            "n_bots": n_bots,
            "episode_length": episode_length,
            "agent_type": "Rule-Based",
            "queen_mode": "heuristic",
            "network": "disabled",
        },
        "scenarios": [
            {"label": scenario["label"], "tumor_radius": float(scenario["tumor_radius"])}
            for scenario in scenario_configs
        ],
        "summary": summary,
        "runs": results,
        "pairs": pairs,
    }


def main(argv=None) -> int:
    parser = _JsonArgumentParser(description="Paired synthetic Queen policy evaluation")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--scenarios", "--patients", dest="scenarios", type=int, default=3)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--bots", type=int, default=5)
    parser.add_argument("--episode-length", type=int, default=10)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
        count = _positive_int(args.scenarios, "scenarios")
        if count > len(SYNTHETIC_SCENARIOS):
            raise ValueError(f"scenarios must be between 1 and {len(SYNTHETIC_SCENARIOS)}")
        result = run_evaluation(
            n_seeds=args.seeds,
            scenarios=SYNTHETIC_SCENARIOS[:count],
            n_steps=args.steps,
            n_bots=args.bots,
            episode_length=args.episode_length,
            verbose=False,
        )
    except (TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": {"type": "input_validation", "message": str(exc)}}))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
