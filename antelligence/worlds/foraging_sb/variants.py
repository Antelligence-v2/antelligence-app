"""Validity check for the foraging_sb variants (no model calls).

A variant is kept only if, on the development seeds, S' scores >= 0.9 x S on base and S scores <= 0.5 x S' on
the variant. ``python -m antelligence.worlds.foraging_sb.variants`` rewrites the committed result file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from antelligence.kernel.field import GridField
from antelligence.kernel.scheduler import RunConfig, RunResult, Scheduler
from antelligence.worlds.foraging_sb.pilot import FORAGING_SB
from antelligence.worlds.foraging_sb.world import STEPS, V1_PICKUPS, V2_FLIP_TICK

DEV_SEEDS = tuple(range(100, 110))
RESULT = Path(__file__).resolve().parents[3] / "docs/research/v4-pilot-20261011/validity-foraging_sb.json"


def run_episode(seed: int, condition: str, *, variant: Optional[str] = None, adapted: bool = False) -> RunResult:
    """One scripted run: world ``condition``; script S, or S' written for ``variant`` when ``adapted``."""
    world = FORAGING_SB.make_world(seed, condition)
    policy = FORAGING_SB.script(variant or condition, adapted=adapted)
    arm = f"S_prime_{variant}" if adapted else "S"
    config = RunConfig(f"fsb-{condition}-{seed}", seed=seed, max_ticks=STEPS, arm=arm)
    result = Scheduler(world, {}, GridField(), config, default_policy=policy, record_frames=False).run()
    result.extra["score"] = FORAGING_SB.score(world)
    return result


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 3)


def validity_check(seeds: Sequence[int] = DEV_SEEDS) -> Dict[str, Any]:
    """Per variant: mean scores of S and S' on base and on the variant, and the two pass/fail tests."""
    base_s = [run_episode(s, "base").extra["score"] for s in seeds]
    out: Dict[str, Any] = {"world": "foraging_sb", "seeds": list(seeds), "params":
                           {"v1_pickups": V1_PICKUPS, "v2_flip_tick": V2_FLIP_TICK, "steps": STEPS}, "variants": {}}
    for variant in ("v1", "v2"):
        sp_base = [run_episode(s, "base", variant=variant, adapted=True).extra["score"] for s in seeds]
        s_var = [run_episode(s, variant).extra["score"] for s in seeds]
        sp_var = [run_episode(s, variant, adapted=True).extra["score"] for s in seeds]
        row = {"score_S_base": _mean(base_s), "score_Sprime_base": _mean(sp_base),
               "score_S_variant": _mean(s_var), "score_Sprime_variant": _mean(sp_var)}
        row["sprime_keeps_base"] = row["score_Sprime_base"] >= 0.9 * row["score_S_base"]
        row["variant_breaks_s"] = row["score_S_variant"] <= 0.5 * row["score_Sprime_variant"]
        row["pass"] = row["sprime_keeps_base"] and row["variant_breaks_s"]
        out["variants"][variant] = row
    out["pass"] = all(v["pass"] for v in out["variants"].values())
    return out


def main() -> None:
    result = validity_check()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
