#!/usr/bin/env python3
"""Attestation bot — re-runs random submissions for reproducibility spot-checks.

Picks k% of recent simulation submissions, re-runs them with the same config,
and verifies metrics are within tolerance. Reports discrepancies.

Usage:
    python3 scripts/attestation_bot.py results.json [--sample-pct 20] [--tolerance 5]
    python3 scripts/attestation_bot.py --from-dir ./results/ --sample-pct 10
"""

import argparse
import json
import os
import sys
import random
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chain.verify import verify_artifact_integrity, verify_metrics_tolerance
from chain.ipfs import create_simulation_artifact
from simulation_replay import replay_artifact_metrics


def spot_check_run(original_result, steps, n_bots, with_queen, episode_length):
    """Re-run a simulation and compare metrics."""
    artifact = {
        "config": {
            "seed": original_result.get("seed", 0),
            "tumor_radius": original_result.get("tumor_radius", 150),
            "nanobot_count": n_bots,
            "steps": steps,
            "with_queen": with_queen,
            "episode_length": episode_length,
            "domain_size": max(400.0, original_result.get("tumor_radius", 150) * 3),
            "voxel_size": 20.0,
        }
    }
    recomputed = replay_artifact_metrics(artifact)
    return {
        "kill_rate_pct": round(recomputed["kill_rate"], 2),
        "kills": recomputed["cells_killed"],
        "deliveries": recomputed["deliveries"],
    }


def run_spot_checks(sweep_data, sample_pct=20, tolerance_pct=5.0, verbose=True, dry_run=False):
    """Run spot checks on a sample of sweep results."""
    config = sweep_data.get("config", {})
    results = sweep_data.get("results", [])

    if not results:
        return {"ok": True, "checked": 0, "passed": 0, "message": "No results to check"}

    # Sample k%
    n_sample = max(1, int(len(results) * sample_pct / 100))
    sample = random.sample(results, min(n_sample, len(results)))

    if dry_run:
        return {
            "ok": False,
            "status": "dry_run_unverified",
            "checked": 0,
            "passed": 0,
            "failed": 0,
            "candidate_count": len(sample),
            "sample_pct": sample_pct,
            "tolerance_pct": tolerance_pct,
            "checks": [],
            "message": "Dry run selected candidates but did not execute or attest them.",
        }

    checks = []
    for original in sample:
        if verbose:
            print(f"  Spot-checking seed={original.get('seed')} patient={original.get('patient')}...", end=" ", flush=True)

        recomputed = spot_check_run(
            original,
            steps=config.get("steps", 50),
            n_bots=config.get("n_bots", 5),
            with_queen=config.get("with_queen", True),
            episode_length=config.get("episode_length", 10),
        )

        tolerance_result = verify_metrics_tolerance(
            {"kill_rate": original.get("kill_rate_pct", 0), "deliveries": original.get("deliveries", 0)},
            {"kill_rate": recomputed["kill_rate_pct"], "deliveries": recomputed["deliveries"]},
            tolerance_pct=tolerance_pct,
        )

        check = {
            "seed": original.get("seed"),
            "patient": original.get("patient"),
            "original_kill_rate": original.get("kill_rate_pct"),
            "recomputed_kill_rate": recomputed["kill_rate_pct"],
            "passed": tolerance_result["ok"],
            "details": tolerance_result["checks"],
        }
        checks.append(check)

        if verbose:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"{status} (orig={check['original_kill_rate']}% recomp={check['recomputed_kill_rate']}%)")

    passed = sum(1 for c in checks if c["passed"])
    return {
        "ok": passed == len(checks),
        "checked": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "sample_pct": sample_pct,
        "tolerance_pct": tolerance_pct,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Attestation spot-check bot")
    parser.add_argument("input", help="JSON results from batch_runner.py")
    parser.add_argument("--sample-pct", type=float, default=20)
    parser.add_argument("--tolerance", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without executing simulations")
    args = parser.parse_args()

    if args.dry_run:
        if not args.json:
            print("Attestation Bot: DRY RUN mode enabled. No simulations will be executed.")
            print("=" * 50)
        # For dry run, we still need to load the JSON data to show what would be checked
        text = Path(args.input).read_text()
        start = text.find("{")
        data = json.loads(text[start:])
        result = run_spot_checks(data, args.sample_pct, args.tolerance, verbose=not args.json, dry_run=True)
    else:
        text = Path(args.input).read_text()
        start = text.find("{")
        data = json.loads(text[start:])

        if not args.json:
            print(f"Attestation Bot: spot-checking {args.sample_pct}% of runs (tolerance: {args.tolerance}%)")
            print("=" * 50)

        result = run_spot_checks(data, args.sample_pct, args.tolerance, verbose=not args.json, dry_run=False)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nResults: {result['passed']}/{result['checked']} passed")
        if result["failed"] > 0:
            print(f"ALERT: {result['failed']} checks failed!")
            for c in result["checks"]:
                if not c["passed"]:
                    print(f"  FAIL: seed={c['seed']} patient={c['patient']} "
                          f"orig={c['original_kill_rate']}% vs recomp={c['recomputed_kill_rate']}%")


if __name__ == "__main__":
    main()
