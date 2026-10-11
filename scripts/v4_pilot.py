#!/usr/bin/env python3
"""v4 pilot CLI: validity | plan | run | report-data. Every subcommand takes --dry-run.

--dry-run uses fake policies, a fake backend and a fake ledger: no network, no keys read. Live mode needs
``antelligence.experiments.v4_wiring.make_hooks(...)`` (written by the integrator) and reads keys only in
``nous_key`` and ``env_value`` below. Evaluation seeds (1..5) refuse to run unless PREREGISTRATION.md and the
harness files are committed and clean.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.experiments import v4_budget as budget  # noqa: E402
from antelligence.experiments import v4_metrics as metrics  # noqa: E402
from antelligence.experiments import v4_pilot as pilot  # noqa: E402

DEFAULT_WORLDS = {"foraging_sb": "antelligence.worlds.foraging_sb:FORAGING_SB",
                  "graph_coloring": "antelligence.worlds.graph_coloring:GRAPH_COLORING"}
EXP_REL = "docs/research/v4-pilot-20261011"


def nous_key() -> str:
    """The Nous key, read only here, only in live mode, exactly as colony_v2_collect does."""
    return json.loads(Path("~/.hermes/auth.json").expanduser().read_text())["providers"]["nous"]["agent_key"]


def env_value(name: str) -> str:
    """TYPESAFE_API_KEY / RUNPOD_API_KEY from ~/.hermes/.env, read only here, only in live mode."""
    for line in Path("~/.hermes/.env").expanduser().read_text().splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("'\"")
    raise SystemExit(f"{name} is not set in ~/.hermes/.env")


def parse_seeds(text: str) -> List[int]:
    return list(pilot.DEV_SEEDS if text == "dev" else pilot.EVAL_SEEDS if text == "eval"
                else [int(s) for s in text.split(",")])


def load_worlds(overrides: Sequence[str]) -> Dict[str, Any]:
    """Worlds named NAME=pkg.mod:ATTR replace the defaults; the defaults are imported only when asked for."""
    mapping = dict(o.split("=", 1) for o in overrides) or dict(DEFAULT_WORLDS)
    worlds = {}
    for name, ref in mapping.items():
        module, attr = ref.split(":")
        try:
            worlds[name] = getattr(importlib.import_module(module), attr)
        except ImportError as exc:
            if overrides:
                raise
            print(f"world {name} not importable yet ({exc}); skipping", file=sys.stderr)
    if not worlds:
        raise SystemExit("no pilot worlds available (use --world NAME=pkg.mod:ATTR)")
    return worlds


def hooks_for(args: argparse.Namespace, root: Path) -> pilot.Hooks:
    if args.dry_run:
        kit = pilot.DryKit()
        return pilot.Hooks(kit.build_policies, kit.tags, kit.rows_for, kit.backend)
    wiring = importlib.import_module("antelligence.experiments.v4_wiring")  # integrator-provided
    return wiring.make_hooks(nous_key=nous_key, env_value=env_value, ledger=root / "ledger/v4-pilot-usage.jsonl",
                             cache_dir=root / "cache/v4-pilot")


def out_dir_for(args: argparse.Namespace, root: Path, seeds: Sequence[int]) -> Path:
    if args.out_dir:
        return Path(args.out_dir)
    if args.dry_run:
        return root / "ledger/v4-pilot-dry"
    return root / (EXP_REL if pilot.uses_eval_seeds(seeds) else "ledger/v4-pilot-dev")


def write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1, sort_keys=True, default=str) + "\n")


def cmd_validity(args: argparse.Namespace, root: Path) -> int:
    worlds = load_worlds(args.world)
    seeds = parse_seeds(args.seeds)
    report = {name: pilot.validity_check(w, seeds) for name, w in worlds.items()}
    write_json(out_dir_for(args, root, seeds) / "validity.json", report)
    invalid = [f"{n}/{v}" for n, r in report.items() for v, x in r["variants"].items() if not x["valid"]]
    print(json.dumps({"invalid_variants": invalid}))
    return 1 if invalid else 0


def build_plan(args: argparse.Namespace) -> List[pilot.CellSpec]:
    if args.plan:
        return [pilot.CellSpec(**c) for c in json.loads(Path(args.plan).read_text())]
    return pilot.make_plan(sorted(load_worlds(args.world)), args.arms.split(",") if args.arms else None,
                           parse_seeds(args.seeds), args.conditions.split(","))


def cmd_plan(args: argparse.Namespace, root: Path) -> int:
    plan = build_plan(args)
    seeds = sorted({c.seed for c in plan})
    cells = pilot.load_cells(Path(args.costs_from)) if args.costs_from else []
    costs = budget.costs_from_cells(cells, pod_rate_per_hr=args.pod_rate, concurrency=args.concurrency)
    projection = budget.project(plan, costs)
    adjusted = projection.pop("plan")
    out = out_dir_for(args, root, seeds)
    write_json(out / "plan.json", [c.to_dict() for c in adjusted])
    projection["cells"] = {"planned": len(plan), "after_cuts": len(adjusted)}
    write_json(out / "projection.json", projection)
    print(json.dumps(projection, sort_keys=True, default=str))
    return 1 if projection["over_after_cuts"] else 0


def cmd_run(args: argparse.Namespace, root: Path) -> int:
    plan = build_plan(args)
    seeds = sorted({c.seed for c in plan})
    if pilot.uses_eval_seeds(seeds):
        pilot.check_committed(root)
    worlds = load_worlds(args.world)
    hooks = hooks_for(args, root)
    out = out_dir_for(args, root, seeds)
    ledger, pods = root / "ledger/v4-pilot-usage.jsonl", root / "ledger/v4-pod-costs.jsonl"

    def guard(spec: pilot.CellSpec) -> None:
        if not args.dry_run:
            for provider in pilot.providers_of_arm(spec.arm):
                budget.check_or_raise(provider, ledger=ledger, pods=pods)

    cells_path = out / "cells.jsonl"
    new = asyncio.run(pilot.run_plan(plan, worlds, hooks.build_policies, ledger_tags=hooks.ledger_tags,
                                     cells_path=cells_path, ledger_rows=hooks.ledger_rows,
                                     concurrency=args.concurrency, before_cell=guard,
                                     bundle_dir=out / "bundles" if args.bundles else None))
    print(json.dumps({"planned": len(plan), "ran": len(new), "skipped": len(plan) - len(new),
                      "errors": sum("error" in c for c in new), "cells": str(cells_path)}))
    return 0


def cmd_report_data(args: argparse.Namespace, root: Path) -> int:
    seeds = parse_seeds(args.seeds)
    out = out_dir_for(args, root, seeds)
    cells = pilot.load_cells(out / "cells.jsonl")
    if not cells:
        raise SystemExit(f"no cells in {out / 'cells.jsonl'}")
    results: Dict[str, Any] = metrics.aggregate(cells)
    for name in ("validity", "calibration-summary"):
        path = out / f"{name}.json"
        if path.exists():
            results[name.replace("-", "_")] = json.loads(path.read_text())
    results["spend_usd"] = {} if args.dry_run else budget.spend(root / "ledger/v4-pilot-usage.jsonl",
                                                                root / "ledger/v4-pod-costs.jsonl")
    results["limits_usd"] = budget.LIMITS
    results["arms_table"] = {n: {k: v for k, v in vars(a).items()} for n, a in pilot.ARMS.items()}
    write_json(out / "results.json", results)
    print(json.dumps({"results": str(out / "results.json"), "cells": len(cells),
                      "verdict": results["go_no_go"]["verdict"]}))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name: str, **defaults: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true", help="fakes only: no network, no keys")
        p.add_argument("--root", default=str(ROOT), help="repo root (gate, ledger and default output paths)")
        p.add_argument("--out-dir")
        p.add_argument("--world", action="append", default=[], metavar="NAME=pkg.mod:ATTR")
        p.add_argument("--seeds", default=defaults.get("seeds", "dev"), help="dev | eval | comma list")
        p.add_argument("--concurrency", type=int, default=4)
        return p

    add("validity")
    for name in ("plan", "run"):
        p = add(name, seeds="eval" if name == "plan" else "dev")
        p.add_argument("--arms")
        p.add_argument("--conditions", default=",".join(pilot.CONDITIONS))
        p.add_argument("--plan", help="plan.json written by `plan` (budget cuts applied)")
    pl = sub.choices["plan"]
    pl.add_argument("--costs-from", help="cells.jsonl of one plumbing run per arm")
    pl.add_argument("--pod-rate", type=float, default=0.0, help="USD per pod hour")
    sub.choices["run"].add_argument("--bundles", action="store_true", help="write run bundles, event logs, frames")
    add("report-data")
    args = parser.parse_args(argv)
    handler = {"validity": cmd_validity, "plan": cmd_plan, "run": cmd_run,
               "report-data": cmd_report_data}[args.cmd]
    return handler(args, Path(args.root))


if __name__ == "__main__":
    sys.exit(main())
