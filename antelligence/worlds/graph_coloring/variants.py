"""Validity check for the coloring variants (no model calls): ``python -m antelligence.worlds.graph_coloring.variants``.

A variant is kept only if, on development seeds, score_S' >= 0.9 * score_S on the base task AND
score_S <= 0.5 * score_S' on the variant. Result: docs/research/v4-pilot-20261011/validity-graph_coloring.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Sequence

from antelligence.kernel.field import GridField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.worlds.graph_coloring.pilot import GRAPH_COLORING

DEV_SEEDS = tuple(range(100, 110))
VARIANTS = ("v1", "v2")
OUT = Path(__file__).resolve().parents[3] / "docs/research/v4-pilot-20261011/validity-graph_coloring.json"

NOTES = {
    "v1": "As briefed: each message dropped with p=0.3 (seeded). One-shot announcements; S' resends until acked.",
    "v2": ("Liar announces a random colour to each neighbour EVERY round (it chatters), is fixed to agent 1, and "
           "S waits for neighbours' reports to settle. With the briefed one-shot liar the fraction-of-edges "
           "scorer left S at ~0.9 of S' (a lie about an excluded edge cannot hurt an honest edge); see README."),
}


def run_score(seed: int, condition: str, *, adapted: bool, variant: str = "base") -> float:
    """Score of one scripted run. ``condition`` is the world's; ``variant`` picks which S' (adapted only)."""
    world = GRAPH_COLORING.make_world(seed, condition)
    policy = GRAPH_COLORING.script(variant if adapted else "base", adapted=adapted)
    Scheduler(world, {}, GridField(), RunConfig(f"validity-{condition}-{seed}", seed=seed, max_ticks=world.rounds),
              default_policy=policy).run()
    return GRAPH_COLORING.score(world)


def validity_check(seeds: Sequence[int] = DEV_SEEDS) -> Dict[str, Any]:
    result: Dict[str, Any] = {"world": "graph_coloring", "seeds": list(seeds), "variants": {}}
    for variant in VARIANTS:
        per_seed = [{"seed": s,
                     "S_base": run_score(s, "base", adapted=False),
                     "Sprime_base": run_score(s, "base", adapted=True, variant=variant),
                     "S_variant": run_score(s, variant, adapted=False),
                     "Sprime_variant": run_score(s, variant, adapted=True, variant=variant)} for s in seeds]
        keys = ("S_base", "Sprime_base", "S_variant", "Sprime_variant")
        m = {k: round(mean(r[k] for r in per_seed), 4) for k in keys}
        base_ok = m["Sprime_base"] >= 0.9 * m["S_base"]
        variant_ok = m["S_variant"] <= 0.5 * m["Sprime_variant"]
        result["variants"][variant] = {
            "score_S_base": m["S_base"], "score_Sprime_base": m["Sprime_base"],
            "score_S_variant": m["S_variant"], "score_Sprime_variant": m["Sprime_variant"],
            "ratio_Sprime_over_S_base": round(m["Sprime_base"] / m["S_base"], 4),
            "ratio_S_over_Sprime_variant": round(m["S_variant"] / m["Sprime_variant"], 4),
            "base_ok": base_ok, "variant_ok": variant_ok, "pass": base_ok and variant_ok,
            "note": NOTES[variant], "per_seed": per_seed,
        }
    result["all_pass"] = all(v["pass"] for v in result["variants"].values())
    return result


def main(argv: Sequence[str] = ()) -> int:
    result = validity_check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: {x: v[x] for x in v if x.startswith(("score", "pass"))}
                      for k, v in result["variants"].items()}, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
