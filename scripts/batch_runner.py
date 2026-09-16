#!/usr/bin/env python3
"""Batch runner for automated experiment sweeps.

Reads a YAML config defining seed × parameter grid, runs all combinations,
collects metrics, and optionally attests results on-chain via IPFS.

Usage:
    python3 scripts/batch_runner.py config.yaml [--json] [--attest]
    python3 scripts/batch_runner.py --example > sweep.yaml

Example YAML:
    name: pheromone-sweep-001
    seeds: [0, 1, 2, 3, 4]
    steps: 50
    n_bots: 5
    with_queen: true
    episode_length: 10
    patients:
      - {tumor_radius: 80, label: small}
      - {tumor_radius: 150, label: medium}
      - {tumor_radius: 200, label: large}
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from nanobot_simulation import TumorNanobotModel, QueenNanobot
from biofvm import create_trail_pheromone, create_alarm_pheromone, create_recruitment_pheromone
from chain.ipfs import create_simulation_artifact, pin_simulation


EXAMPLE_CONFIG = """\
name: example-sweep
description: Example parameter sweep across seeds and tumor sizes
seeds: [0, 1, 2]
steps: 50
n_bots: 5
with_queen: true
episode_length: 10
patients:
  - {tumor_radius: 80, label: small}
  - {tumor_radius: 150, label: medium}
  - {tumor_radius: 200, label: large}
"""


def load_config(path):
    """Load sweep config from YAML or JSON."""
    text = Path(path).read_text()
    # Try YAML first, fall back to JSON
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass
    # Simple YAML-like parser for basic configs (no full YAML dependency)
    return _parse_simple_yaml(text)


def _parse_simple_yaml(text):
    """Minimal YAML parser for sweep configs (no pyyaml dependency)."""
    config = {}
    current_list_key = None
    current_list = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            # List item
            item = stripped[2:].strip()
            if item.startswith("{") and item.endswith("}"):
                # Inline dict
                pairs = item[1:-1].split(",")
                d = {}
                for pair in pairs:
                    k, v = pair.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        v = int(v)
                    except ValueError:
                        try:
                            v = float(v)
                        except ValueError:
                            pass
                    d[k] = v
                current_list.append(d)
            else:
                try:
                    current_list.append(int(item))
                except ValueError:
                    current_list.append(item)
            continue

        if current_list_key and current_list:
            config[current_list_key] = current_list
            current_list = []
            current_list_key = None

        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if not value:
                current_list_key = key
                current_list = []
                continue

            # Parse value
            if value.startswith("[") and value.endswith("]"):
                # Inline list
                items = value[1:-1].split(",")
                parsed = []
                for item in items:
                    item = item.strip()
                    try:
                        parsed.append(int(item))
                    except ValueError:
                        try:
                            parsed.append(float(item))
                        except ValueError:
                            parsed.append(item)
                config[key] = parsed
            elif value.lower() in ("true", "false"):
                config[key] = value.lower() == "true"
            else:
                try:
                    config[key] = int(value)
                except ValueError:
                    try:
                        config[key] = float(value)
                    except ValueError:
                        config[key] = value

    if current_list_key and current_list:
        config[current_list_key] = current_list

    return config


def run_single(seed, steps, n_bots, tumor_radius, with_queen, episode_length):
    """Run a single simulation trial and return metrics."""
    np.random.seed(seed)
    import random
    random.seed(seed)

    domain = max(400.0, tumor_radius * 3)
    model = TumorNanobotModel(
        domain_size=domain,
        voxel_size=20.0,
        n_nanobots=n_bots,
        tumor_radius=tumor_radius,
        agent_type="heuristic",
        with_queen=with_queen,
        use_llm_queen=False,
    )

    create_trail_pheromone(model.microenv)
    create_alarm_pheromone(model.microenv)
    create_recruitment_pheromone(model.microenv)

    queen = None
    if with_queen:
        queen = QueenNanobot(model=model, use_llm=False, episode_length=episode_length)

    total_cells = len(model.geometry.tumor_cells)
    start = time.time()

    for _ in range(steps):
        model.step()
        if queen:
            queen.step()

    runtime = time.time() - start
    living = len(model.geometry.get_living_cells())
    kills = total_cells - living
    kill_rate = (kills / total_cells * 100) if total_cells > 0 else 0
    deliveries = sum(bot.deliveries_made for bot in model.nanobots)
    total_drug = sum(bot.total_drug_delivered for bot in model.nanobots)

    # Toxicity proxy: drug deposited outside tumor / total drug
    # (simplified — real toxicity would track healthy tissue exposure)
    toxicity_proxy = 0.0  # Placeholder

    return {
        "kill_rate_pct": round(kill_rate, 2),
        "kills": kills,
        "total_cells": total_cells,
        "living_cells": living,
        "deliveries": deliveries,
        "total_drug_ug": round(total_drug, 2),
        "toxicity_proxy": toxicity_proxy,
        "runtime_s": round(runtime, 2),
        "queen_episodes": queen.episode_counter if queen else 0,
    }


def run_sweep(config, verbose=True):
    """Run full parameter sweep from config."""
    name = config.get("name", "unnamed-sweep")
    seeds = config.get("seeds", [0, 1, 2])
    steps = config.get("steps", 50)
    n_bots = config.get("n_bots", 5)
    with_queen = config.get("with_queen", True)
    episode_length = config.get("episode_length", 10)
    patients = config.get("patients", [{"tumor_radius": 150, "label": "default"}])

    all_results = []
    total_runs = len(seeds) * len(patients)
    completed = 0

    for patient in patients:
        label = patient.get("label", f"r{patient['tumor_radius']}")
        radius = patient["tumor_radius"]

        for seed in seeds:
            completed += 1
            if verbose:
                print(f"  [{completed}/{total_runs}] {label} seed={seed}...", end=" ", flush=True)

            metrics = run_single(seed, steps, n_bots, radius, with_queen, episode_length)
            metrics["seed"] = seed
            metrics["patient"] = label
            metrics["tumor_radius"] = radius

            all_results.append(metrics)
            if verbose:
                print(f"kill={metrics['kill_rate_pct']}% del={metrics['deliveries']} {metrics['runtime_s']}s")

    # Aggregate
    kill_rates = [r["kill_rate_pct"] for r in all_results]
    summary = {
        "name": name,
        "total_runs": len(all_results),
        "avg_kill_rate": round(np.mean(kill_rates), 2),
        "std_kill_rate": round(np.std(kill_rates), 2),
        "best_kill_rate": max(kill_rates),
        "worst_kill_rate": min(kill_rates),
        "avg_deliveries": round(np.mean([r["deliveries"] for r in all_results]), 1),
        "avg_runtime_s": round(np.mean([r["runtime_s"] for r in all_results]), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "ok": True,
        "config": config,
        "summary": summary,
        "results": all_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch experiment runner")
    parser.add_argument("config", nargs="?", help="YAML/JSON config file")
    parser.add_argument("--example", action="store_true", help="Print example config")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--attest", action="store_true", help="Pin results to IPFS")
    args = parser.parse_args()

    if args.example:
        print(EXAMPLE_CONFIG)
        return

    if not args.config:
        parser.error("Provide a config file or --example")

    config = load_config(args.config)

    if not args.json:
        print(f"Batch Runner: {config.get('name', 'unnamed')}")
        print(f"Seeds: {len(config.get('seeds', []))}, Patients: {len(config.get('patients', []))}")
        print("=" * 50)

    result = run_sweep(config, verbose=not args.json)

    if args.attest:
        artifact = create_simulation_artifact(config, result["summary"])
        ipfs = pin_simulation(config, result["summary"], backend="dry-run")
        result["attestation"] = ipfs

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"\n{'='*50}")
        print(f"SWEEP: {s['name']}")
        print(f"Runs: {s['total_runs']}")
        print(f"Kill rate: {s['avg_kill_rate']}% ± {s['std_kill_rate']}%")
        print(f"Best: {s['best_kill_rate']}% | Worst: {s['worst_kill_rate']}%")
        print(f"Avg deliveries: {s['avg_deliveries']}")
        print(f"Avg runtime: {s['avg_runtime_s']}s")


if __name__ == "__main__":
    main()
