#!/usr/bin/env python3
"""Generate DPO preference pairs for Queen policy training.

Reads attested leaderboard entries, compares pairs of runs with different
pheromone params but same nanobot_count and steps, emits preference pairs to
feeds/training_datasets/queen_preferences.jsonl.

Format matches feeds/training_datasets/forecast_preferences.jsonl:
  - prompt, chosen, rejected, domain, category, chosen_score, rejected_score, meta

CLI: --leaderboard PATH --output PATH --min-score-delta 0.5 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "backend"))

TRAINING_ELIGIBLE_TRUST_TIERS = frozenset(
    {"replay_checked", "proof_staged", "verified_onchain"}
)


# ---------------------------------------------------------------------------
# Dry-run / synthetic data
# ---------------------------------------------------------------------------

_DRY_RUN_LEADERBOARD: List[Dict[str, Any]] = [
    {
        "run_id": "dry-run-001",
        "kill_rate": 55.0,
        "deliveries": 11,
        "nanobot_count": 10,
        "steps": 100,
        "trust_tier": "replay_checked",
        "pheromone_params": {"trail_decay": 0.12, "recruitment_diffusion": 5e-6},
    },
    {
        "run_id": "dry-run-002",
        "kill_rate": 30.0,
        "deliveries": 6,
        "nanobot_count": 10,
        "steps": 100,
        "trust_tier": "replay_checked",
        "pheromone_params": {"trail_decay": 0.06, "recruitment_diffusion": 1e-7},
    },
    {
        "run_id": "dry-run-003",
        "kill_rate": 20.0,
        "deliveries": 4,
        "nanobot_count": 10,
        "steps": 100,
        "trust_tier": "unverified",
        "pheromone_params": {"trail_decay": 0.03, "recruitment_diffusion": 1e-7},
    },
    {
        "run_id": "dry-run-004",
        "kill_rate": 48.0,
        "deliveries": 9,
        "nanobot_count": 5,
        "steps": 50,
        "trust_tier": "replay_checked",
        "pheromone_params": {"trail_decay": 0.10, "recruitment_diffusion": 3e-6},
    },
    {
        "run_id": "dry-run-005",
        "kill_rate": 22.0,
        "deliveries": 4,
        "nanobot_count": 5,
        "steps": 50,
        "trust_tier": "unverified",
        "pheromone_params": {"trail_decay": 0.04, "recruitment_diffusion": 1e-7},
    },
]


def _load_leaderboard(path: Path) -> List[Dict[str, Any]]:
    """Load leaderboard entries from a JSON file or directory of artifacts."""
    if path.is_dir():
        entries = []
        for f in sorted(path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if "leaderboard" in data:
                    entries.extend(data["leaderboard"])
                elif "run_id" in data:
                    entries.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return entries
    else:
        data = json.loads(path.read_text())
        if "leaderboard" in data:
            return data["leaderboard"]
        if isinstance(data, list):
            return data
        return []


def _format_params(params: Optional[Dict]) -> str:
    if not params:
        return "default pheromone params"
    td = params.get("trail_decay", "?")
    rd = params.get("recruitment_diffusion", "?")
    return f"trail_decay={td}, recruitment_diffusion={rd:.2e}" if isinstance(rd, float) else f"trail_decay={td}, recruitment_diffusion={rd}"


def _build_pair(chosen_entry: Dict, rejected_entry: Dict) -> Dict[str, Any]:
    """Build a DPO preference pair from two leaderboard entries."""
    chosen_params = chosen_entry.get("pheromone_params") or {}
    rejected_params = rejected_entry.get("pheromone_params") or {}

    chosen_score = chosen_entry.get("kill_rate", 0.0)
    rejected_score = rejected_entry.get("kill_rate", 0.0)

    nanobot_count = chosen_entry.get("nanobot_count", "?")
    steps = chosen_entry.get("steps", "?")

    prompt = (
        f"Given {nanobot_count} nanobots running for {steps} steps, "
        f"compare pheromone configurations: "
        f"A=({_format_params(chosen_params)}) vs "
        f"B=({_format_params(rejected_params)}). "
        f"Which achieves higher tumor kill rate and why?"
    )

    chosen_text = (
        f"Configuration A ({_format_params(chosen_params)}) achieves {chosen_score:.1f}% kill rate "
        f"with {chosen_entry.get('deliveries', 0)} deliveries. "
        f"This measured result is preferred because it recorded the higher verified kill rate; "
        f"this pair alone does not establish which parameter caused the difference."
    )

    rejected_text = (
        f"Configuration B ({_format_params(rejected_params)}) achieves only {rejected_score:.1f}% kill rate "
        f"with {rejected_entry.get('deliveries', 0)} deliveries. "
        f"This measured result is rejected because it recorded the lower verified kill rate under "
        f"otherwise matched run settings; no causal parameter claim is made."
    )

    return {
        "prompt": prompt,
        "chosen": chosen_text,
        "rejected": rejected_text,
        "domain": "antelligence",
        "category": "pheromone_params",
        "chosen_score": chosen_score,
        "rejected_score": rejected_score,
        "meta": {
            "chosen_run_id": chosen_entry.get("run_id", ""),
            "rejected_run_id": rejected_entry.get("run_id", ""),
            "nanobot_count": nanobot_count,
            "steps": steps,
            "chosen_trust_tier": chosen_entry.get("trust_tier", ""),
            "rejected_trust_tier": rejected_entry.get("trust_tier", ""),
        },
    }


def generate_pairs(
    entries: List[Dict],
    min_score_delta: float = 0.5,
) -> List[Dict[str, Any]]:
    """Generate preference pairs from leaderboard entries.

    Pairs runs with same nanobot_count and steps but different pheromone params.
    Only replay-checked or stronger runs are eligible, and score delta must be
    at least ``min_score_delta``.
    """
    # Group by (nanobot_count, steps)
    groups: Dict[tuple, List[Dict]] = {}
    for entry in entries:
        if entry.get("trust_tier") not in TRAINING_ELIGIBLE_TRUST_TIERS:
            continue
        key = (entry.get("nanobot_count", 0), entry.get("steps", 0))
        groups.setdefault(key, []).append(entry)

    pairs = []
    seen = set()

    for key, group in groups.items():
        # Sort by kill_rate descending
        group_sorted = sorted(group, key=lambda e: e.get("kill_rate", 0), reverse=True)
        for i, chosen in enumerate(group_sorted):
            for rejected in group_sorted[i + 1:]:
                if (chosen.get("pheromone_params") or {}) == (rejected.get("pheromone_params") or {}):
                    continue
                chosen_score = chosen.get("kill_rate", 0)
                rejected_score = rejected.get("kill_rate", 0)
                delta = chosen_score - rejected_score

                if delta < min_score_delta:
                    continue

                pair_key = (chosen.get("run_id", ""), rejected.get("run_id", ""))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                pairs.append(_build_pair(chosen, rejected))

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Queen DPO preference pairs")
    parser.add_argument("--leaderboard", type=str, default=None, help="Path to leaderboard JSON or artifact directory")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL path")
    parser.add_argument("--min-score-delta", type=float, default=0.5, help="Minimum kill_rate delta to emit a pair")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic data, don't read files")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else _ROOT / "feeds" / "training_datasets" / "queen_preferences.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        entries = _DRY_RUN_LEADERBOARD
    else:
        if not args.leaderboard:
            parser.error("--leaderboard is required unless --dry-run is set")
        lb_path = Path(args.leaderboard)
        if not lb_path.exists():
            print(f"ERROR: leaderboard path does not exist: {lb_path}", file=sys.stderr)
            sys.exit(1)
        entries = _load_leaderboard(lb_path)

    pairs = generate_pairs(entries, min_score_delta=args.min_score_delta)

    with output_path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair) + "\n")

    print(f"Wrote {len(pairs)} preference pairs to {output_path}")


if __name__ == "__main__":
    main()
