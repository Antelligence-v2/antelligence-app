"""cli.py — unified command-line interface for Antelligence simulation tools.

Subcommands
-----------
simulate    Run a single simulation and write metrics to JSON.
benchmark   Run multiple simulations, aggregate stats, write report to JSON.
leaderboard Fetch and display the on-chain leaderboard.

Usage
-----
    antelligence simulate --steps 100 --bots 10 --output results.json
    antelligence benchmark --runs 5 --output benchmark.json
    antelligence leaderboard --limit 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

# Ensure backend package is importable when invoked as a script.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Import at module level so tests can patch backend.cli.TumorNanobotModel
with redirect_stdout(sys.stderr):
    from backend.nanobot_simulation import TumorNanobotModel
from backend.config import SimulationConfig
from backend.runtime_factory import run_simulation


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_simulate(args: argparse.Namespace) -> None:
    """Run a single simulation."""
    cfg = SimulationConfig(num_bots=args.bots, grid_size=args.grid_size,
                           steps=args.steps, seed=args.seed)
    print(f"[simulate] bots={args.bots}, steps={args.steps}, grid={args.grid_size}×{args.grid_size}", file=sys.stderr)
    with redirect_stdout(sys.stderr):
        _, metrics = run_simulation(cfg, model_factory=TumorNanobotModel)

    result = {
        "config": {
            "num_bots": args.bots,
            "steps": args.steps,
            "grid_size": args.grid_size,
            "seed": args.seed,
        },
        "metrics": metrics,
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[simulate] results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Run multiple simulations and aggregate statistics."""
    if args.runs < 1:
        raise ValueError("runs must be at least 1")
    results = []
    steps = getattr(args, "steps", 50)
    grid_size = getattr(args, "grid_size", 30)
    bots = getattr(args, "bots", 5)
    print(f"[benchmark] runs={args.runs}, steps={steps}, bots={bots}", file=sys.stderr)

    for i in range(args.runs):
        seed = i
        cfg = SimulationConfig(num_bots=bots, grid_size=grid_size, steps=steps, seed=seed)
        with redirect_stdout(sys.stderr):
            _, metrics = run_simulation(cfg, model_factory=TumorNanobotModel)
        results.append({"run": i, "seed": seed, **metrics})
        print(f"  run {i + 1}/{args.runs}: kill_rate={metrics['kill_rate']:.4f}", file=sys.stderr)

    kill_rates = [r["kill_rate"] for r in results]
    summary = {
        "runs": args.runs,
        "mean_kill_rate": sum(kill_rates) / len(kill_rates),
        "min_kill_rate": min(kill_rates),
        "max_kill_rate": max(kill_rates),
        "results": results,
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"[benchmark] results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(summary, indent=2))


def cmd_leaderboard(args: argparse.Namespace) -> None:
    """Display the on-chain leaderboard."""
    try:
        from chain.leaderboard import build_leaderboard, fetch_onchain_events, load_local_artifacts
        from chain.config import get_base_sepolia_rpc_url

        artifacts: list = []

        if args.from_dir:
            artifacts = load_local_artifacts(args.from_dir)
        else:
            rpc_url = get_base_sepolia_rpc_url()
            if not rpc_url:
                print("[leaderboard] BASE_SEPOLIA_RPC_URL not set; cannot fetch on-chain data.")
                print("[leaderboard] No entries to display (offline mode). Use --from-dir <dir> for local artifacts.")
                return
            events = fetch_onchain_events(rpc_url)
            for evt in events:
                artifacts.append({
                    "type": "antelligence-simulation-v2",
                    "config": {},
                    "metrics": {"kill_rate": 0},
                    "verification_status": {
                        "schema_ok": True,
                        "integrity_ok": False,
                        "replay_ok": False,
                        "proof_ok": False,
                        "onchain_ok": True,
                    },
                    "proof_lifecycle": {"stage": "verified_onchain"},
                    "tx_hash": evt.get("transactionHash", ""),
                })

        if not artifacts:
            print("[leaderboard] No simulation entries found.")
            return

        result = build_leaderboard(artifacts)
        if not result.get("leaderboard"):
            print("[leaderboard] No simulation entries found.")
            return

        print("\nAntelligence Simulation Leaderboard")
        print("=" * 60)
        print(f"{'Rank':<6}{'Kill Rate':<12}{'Deliveries':<12}{'Nanobots':<10}{'Steps':<8}{'Run ID'}")
        print("-" * 60)
        for entry in result["leaderboard"][:args.limit]:
            print(
                f"{entry['rank']:<6}"
                f"{entry['kill_rate']:>8.1f}%   "
                f"{entry['deliveries']:>8}    "
                f"{entry['nanobot_count']:>6}    "
                f"{entry['steps']:>5}   "
                f"{entry['run_id'][:16]}"
            )
        print(f"\nTotal: {result['summary']['total_entries']} entries")
        print(f"Best: {result['summary']['best_kill_rate']}% | Avg: {result['summary']['avg_kill_rate']}%")
    except Exception as exc:  # noqa: BLE001
        # Graceful fallback when blockchain is unavailable.
        print(f"[leaderboard] could not reach on-chain data: {exc}")
        print("[leaderboard] No entries to display (dry-run / offline mode).")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="antelligence",
        description="Antelligence nanobot simulation CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- simulate ---
    p_sim = sub.add_parser("simulate", help="Run a single simulation")
    p_sim.add_argument("--steps", type=int, default=100, help="Number of simulation steps (default: 100)")
    p_sim.add_argument("--bots", type=int, default=10, help="Number of nanobots (default: 10)")
    p_sim.add_argument("--grid-size", dest="grid_size", type=int, default=60, help="Grid size N×N (default: 60)")
    p_sim.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    p_sim.add_argument("--output", type=str, default=None, help="Output JSON file (default: stdout)")
    p_sim.set_defaults(func=cmd_simulate)

    # --- benchmark ---
    p_bench = sub.add_parser("benchmark", help="Run multiple simulations and aggregate stats")
    p_bench.add_argument("--runs", type=int, default=3, help="Number of runs (default: 3)")
    p_bench.add_argument("--steps", type=int, default=50, help="Steps per run (default: 50)")
    p_bench.add_argument("--bots", type=int, default=5, help="Nanobots per run (default: 5)")
    p_bench.add_argument("--grid-size", dest="grid_size", type=int, default=30)
    p_bench.add_argument("--output", type=str, default=None, help="Output JSON file (default: stdout)")
    p_bench.set_defaults(func=cmd_benchmark)

    # --- leaderboard ---
    p_lb = sub.add_parser("leaderboard", help="Display the on-chain leaderboard")
    p_lb.add_argument("--limit", type=int, default=10, help="Number of entries to show (default: 10)")
    p_lb.add_argument("--from-dir", dest="from_dir", type=str, default=None, help="Load artifacts from local directory instead of on-chain")
    p_lb.set_defaults(func=cmd_leaderboard)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
