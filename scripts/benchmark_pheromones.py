#!/usr/bin/env python3
"""Run a paired, offline pheromone ablation on synthetic tumor scenarios.

Both conditions use the same seed and simulation configuration.  The output is
always one JSON document; the reported kill-rate delta is in percentage points,
not relative percent, and is descriptive only.
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
from typing import Iterator

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
    from nanobot_simulation import TumorNanobotModel


class _JsonArgumentParser(argparse.ArgumentParser):
    """Raise validation errors so main() can keep stdout JSON-only."""

    def error(self, message):
        raise ValueError(message)


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


def _field_snapshot(model: TumorNanobotModel) -> dict:
    """Return communication-field state without mutating the model."""
    canonical = ("trail_pheromone", "alarm_pheromone", "recruitment_pheromone")
    aliases = ("trail", "alarm", "recruitment")
    fields = {name: model.microenv.get_substrate(name) for name in canonical}
    alias_fields = {name: model.microenv.get_substrate(name) for name in aliases}
    return {
        "fields_present": {name: fields[name] is not None for name in canonical},
        "aliases_preserved": bool(model.pheromones_enabled and all(
            fields[canonical_name] is alias_fields[alias_name]
            for canonical_name, alias_name in zip(canonical, aliases)
        )),
        "concentration_mass": {
            name: float(np.sum(field.concentration)) if field is not None else 0.0
            for name, field in fields.items()
        },
    }


def run_simulation(
    n_steps: int,
    n_bots: int,
    tumor_radius: float,
    seed: int,
    with_pheromones: bool,
):
    """Run one offline rule-based condition and return measured metrics."""
    n_steps = _positive_int(n_steps, "steps")
    n_bots = _positive_int(n_bots, "bots")
    tumor_radius = _positive_float(tumor_radius, "radius")
    seed = _non_negative_int(seed, "seed")
    if not isinstance(with_pheromones, bool):
        raise ValueError("with_pheromones must be a boolean")

    np.random.seed(seed)
    random.seed(seed)

    start = time.perf_counter()
    with _offline_environment(), redirect_stdout(StringIO()):
        model = TumorNanobotModel(
            domain_size=400.0,
            voxel_size=20.0,
            n_nanobots=n_bots,
            tumor_radius=tumor_radius,
            agent_type="Rule-Based",
            with_queen=False,
            use_llm_queen=False,
            pheromones_enabled=with_pheromones,
            seed=seed,
        )
        total_cells = len(model.geometry.tumor_cells)
        if total_cells <= 0:
            raise ValueError("radius/configuration must produce a non-empty synthetic tumor")
        for _ in range(n_steps):
            model.step()
        living = len(model.geometry.get_living_cells())
        snapshot = _field_snapshot(model)

    kills = total_cells - living
    kill_rate = kills / total_cells * 100.0
    total_deliveries = sum(bot.deliveries_made for bot in model.nanobots)
    total_drug = sum(bot.total_drug_delivered for bot in model.nanobots)

    return {
        "seed": seed,
        "condition": "on" if with_pheromones else "off",
        "pheromones_enabled": with_pheromones,
        "kills": kills,
        "total_cells": total_cells,
        "living_cells": living,
        "kill_rate": round(kill_rate, 2),
        "kill_rate_unit": "percent",
        "deliveries": total_deliveries,
        "total_drug": round(float(total_drug), 2),
        "pheromone_fields": snapshot["fields_present"],
        "pheromone_aliases_preserved": snapshot["aliases_preserved"],
        "pheromone_concentration_mass": {
            name: round(value, 6)
            for name, value in snapshot["concentration_mass"].items()
        },
        "runtime_s": round(time.perf_counter() - start, 4),
    }


def _average(runs: list[dict], key: str) -> float:
    return round(float(np.mean([float(run[key]) for run in runs])), 2)


def run_benchmark(
    n_steps: int = 50,
    n_seeds: int = 3,
    n_bots: int = 5,
    tumor_radius: float = 100.0,
) -> dict:
    """Run paired ON/OFF trials over synthetic scenarios."""
    n_steps = _positive_int(n_steps, "steps")
    n_seeds = _positive_int(n_seeds, "seeds")
    n_bots = _positive_int(n_bots, "bots")
    tumor_radius = _positive_float(tumor_radius, "radius")

    results = {"without_pheromones": [], "with_pheromones": []}
    pairs = []
    for seed in range(n_seeds):
        off = run_simulation(n_steps, n_bots, tumor_radius, seed, False)
        on = run_simulation(n_steps, n_bots, tumor_radius, seed, True)
        delta = round(on["kill_rate"] - off["kill_rate"], 2)
        results["without_pheromones"].append(off)
        results["with_pheromones"].append(on)
        pairs.append(
            {
                "seed": seed,
                "same_seed_and_config": True,
                "without_pheromones": off,
                "with_pheromones": on,
                "delta_kill_rate_percentage_points": delta,
            }
        )

    summary = {
        "without_pheromones": {
            "avg_kill_rate": _average(results["without_pheromones"], "kill_rate"),
            "avg_deliveries": _average(results["without_pheromones"], "deliveries"),
            "avg_total_drug": _average(results["without_pheromones"], "total_drug"),
            "runs": len(results["without_pheromones"]),
        },
        "with_pheromones": {
            "avg_kill_rate": _average(results["with_pheromones"], "kill_rate"),
            "avg_deliveries": _average(results["with_pheromones"], "deliveries"),
            "avg_total_drug": _average(results["with_pheromones"], "total_drug"),
            "runs": len(results["with_pheromones"]),
        },
    }
    deltas = [pair["delta_kill_rate_percentage_points"] for pair in pairs]
    mean_delta = round(float(np.mean(deltas)), 2)
    summary.update(
        {
            "delta_kill_rate_percentage_points": mean_delta,
            "paired_delta_kill_rate_percentage_points": mean_delta,
            "delta_definition": (
                "with_pheromones kill rate minus without_pheromones kill rate; "
                "percentage points, not relative percent"
            ),
            "interpretation": (
                "Descriptive paired local result only; a positive delta does not "
                "establish statistical or clinical superiority."
            ),
        }
    )

    return {
        "ok": True,
        "benchmark": "pheromone_ablation",
        "scenario_type": "synthetic",
        "paired": True,
        "config": {
            "n_seeds": n_seeds,
            "n_steps": n_steps,
            "n_bots": n_bots,
            "tumor_radius": tumor_radius,
            "agent_type": "Rule-Based",
            "network": "disabled",
        },
        "summary": summary,
        "runs": results,
        "pairs": pairs,
    }


def main(argv=None) -> int:
    parser = _JsonArgumentParser(description="Paired synthetic pheromone ablation")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--bots", type=int, default=5)
    parser.add_argument("--radius", type=float, default=100.0)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
        result = run_benchmark(
            n_steps=args.steps,
            n_seeds=args.seeds,
            n_bots=args.bots,
            tumor_radius=args.radius,
        )
    except (TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": {"type": "input_validation", "message": str(exc)}}))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
