"""v4 pilot budget guard and projection (goal section 8).

Spend comes from local files only: the usage ledger (one JSONL row per physical call, ``cost_usd``)
and the pod cost records written by ``scripts/v4_pod.py``. Hard stops are checked before each paid
batch. ``project`` is pure: given a plan and measured per-cell costs it returns the adjusted plan
and the cut decisions, in the order the goal fixes.
"""

from __future__ import annotations

import dataclasses
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

LIMITS = {"nous": 4.50, "runpod": 2.75, "jev": 1.50}  # hard stops; budgets are $5, $3 and ~$0.80 expected
DS_ARM = "DS-all"
QUEEN_ARMS = ("F-Laya", "F-Jev", "F-Jev-noEsc")
RUNPOD_CUT_ORDER = ("Q-all-qwen3.5-27b", "Q-all-qwen3.5-4b")
FORAGING = "foraging_sb"
PROVIDERS = tuple(LIMITS)


class BudgetExceeded(RuntimeError):
    """A hard stop was reached; no further paid batch may start."""


def read_jsonl(path: Optional[Path]) -> List[Dict[str, Any]]:
    """Rows of a JSONL file; a missing file is empty and a torn last line is skipped."""
    if path is None or not Path(path).exists():
        return []
    rows = []
    for line in Path(path).read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def provider_of(row: Mapping[str, Any]) -> Optional[str]:
    """Which budget a ledger row bills to (vLLM and Laya calls are $0 per call; pods bill separately)."""
    text = f"{row.get('backend', '')} {row.get('model', '')}".lower()
    if "nous" in text or "deepseek" in text:
        return "nous"
    if "jev" in text:
        return "jev"
    return None


def ledger_spend(rows: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = defaultdict(float)
    for row in rows:
        provider = provider_of(row)
        if provider and row.get("cost_usd"):
            out[provider] += float(row["cost_usd"])
    return dict(out)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def pod_spend(records: Sequence[Mapping[str, Any]], now: Optional[datetime] = None) -> float:
    """RunPod dollars: hours between each pod's start and stop record times its rate.

    A pod with no stop record is still billing, so it is charged up to ``now``.
    """
    now = now or datetime.now(timezone.utc)
    starts: Dict[str, Mapping[str, Any]] = {}
    total = 0.0
    for rec in records:
        if rec.get("event") == "start":
            starts[rec["pod_id"]] = rec
        elif rec.get("event") == "stop" and rec["pod_id"] in starts:
            start = starts.pop(rec["pod_id"])
            total += (_utc(rec["utc"]) - _utc(start["utc"])).total_seconds() / 3600 * float(start["rate_per_hr"])
    for start in starts.values():
        total += (now - _utc(start["utc"])).total_seconds() / 3600 * float(start["rate_per_hr"])
    return total


def spend(ledger: Optional[Path], pods: Optional[Path], now: Optional[datetime] = None) -> Dict[str, float]:
    out = {p: 0.0 for p in PROVIDERS}
    out.update(ledger_spend(read_jsonl(ledger)))
    out["runpod"] = pod_spend(read_jsonl(pods), now)
    return out


def check_or_raise(provider: str, *, ledger: Optional[Path], pods: Optional[Path], pending_usd: float = 0.0,
                   limits: Mapping[str, float] = LIMITS, now: Optional[datetime] = None) -> float:
    """Raise BudgetExceeded when spend (plus a batch's expected cost) reaches the hard stop; else return spend."""
    if provider not in limits:
        raise KeyError(f"unknown provider {provider!r}")
    spent = spend(ledger, pods, now)[provider]
    if spent + pending_usd >= limits[provider]:
        raise BudgetExceeded(f"{provider} hard stop: ${spent:.4f} spent + ${pending_usd:.4f} pending "
                             f">= ${limits[provider]:.2f}")
    return spent


# --- projection --------------------------------------------------------------


def cost_key(world: str, arm: str) -> str:
    return f"{world}|{arm}"


def costs_from_cells(cells: Sequence[Mapping[str, Any]], *, pod_rate_per_hr: float = 0.0,
                     concurrency: int = 1) -> Dict[str, Dict[str, float]]:
    """Mean per-cell cost by (world, arm) from plumbing cells.

    ``cost_by_provider`` and ``queen_cost_usd`` come from each cell. RunPod is wall-clock times the pod
    rate divided by the number of episodes sharing the pod, for arms that bill a pod (``pod`` flag).
    """
    groups: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for c in cells:
        if not c.get("error"):
            groups[cost_key(c["world"], c["arm"])].append(c)
    out: Dict[str, Dict[str, float]] = {}
    for key, group in groups.items():
        n = len(group)
        entry = {p: sum(c.get("cost_by_provider", {}).get(p, 0.0) for c in group) / n for p in ("nous", "jev")}
        entry["queen_nous"] = sum(c.get("queen_cost_usd", 0.0) for c in group) / n
        entry["runpod"] = (sum(c.get("wall_s", 0.0) for c in group if c.get("pod")) / n / 3600
                           * pod_rate_per_hr / max(1, concurrency))
        out[key] = entry
    return out


def _totals(plan: Sequence[Any], costs: Mapping[str, Mapping[str, float]],
            overhead: Mapping[str, float]) -> Dict[str, float]:
    total = {p: 0.0 for p in PROVIDERS}
    for cell in plan:
        c = costs.get(cost_key(cell.world, cell.arm), {})
        queen = c.get("queen_nous", 0.0)
        if cell.queen_every and cell.queen_every > 10 and cell.arm in QUEEN_ARMS:
            queen_scale = 10.0 / cell.queen_every  # fewer queen turns, proportionally less queen spend
        else:
            queen_scale = 1.0
        total["nous"] += c.get("nous", 0.0) - queen * (1 - queen_scale)
        total["jev"] += c.get("jev", 0.0)
        total["runpod"] += c.get("runpod", 0.0)
    for arm in {c.arm for c in plan}:
        total["runpod"] += overhead.get(arm, 0.0)
    return total


def project(plan: Sequence[Any], costs: Mapping[str, Mapping[str, float]], *,
            limits: Mapping[str, float] = LIMITS, overhead: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """Project spend and apply the section 8 cuts, in order, until each provider fits its hard stop.

    Nous: DS-all foraging to 2 seeds per condition, then the queen speaks every 20 ticks.
    RunPod: drop Q-all Qwen3.5-27B, then Q-all Qwen3.5-4B. Jev has no cut: it is reported if over.
    ``overhead`` is a fixed RunPod cost (pod start-up) per arm, dropped with the arm.
    """
    overhead = overhead or {}
    current = list(plan)
    decisions: List[Dict[str, Any]] = []
    initial = _totals(current, costs, overhead)

    def cut(provider: str, name: str, apply: Callable[[List[Any]], List[Any]]) -> None:
        nonlocal current
        before = _totals(current, costs, overhead)
        if before[provider] <= limits[provider]:
            return
        current = apply(current)
        after = _totals(current, costs, overhead)
        decisions.append({"provider": provider, "cut": name, "projected_before": before[provider],
                          "projected_after": after[provider], "limit": limits[provider]})

    def two_seeds(cells: List[Any]) -> List[Any]:
        kept: Dict[Any, int] = defaultdict(int)
        out = []
        for c in sorted(cells, key=lambda c: c.seed):
            if c.arm == DS_ARM and c.world == FORAGING:
                kept[c.condition] += 1
                if kept[c.condition] > 2:
                    continue
            out.append(c)
        return [c for c in cells if c in out]

    def every_20(cells: List[Any]) -> List[Any]:
        return [dataclasses.replace(c, queen_every=20) if c.arm in QUEEN_ARMS else c for c in cells]

    cut("nous", "DS-all foraging to 2 seeds per condition", two_seeds)
    cut("nous", "queen speaks every 20 ticks", every_20)
    for arm in RUNPOD_CUT_ORDER:
        cut("runpod", f"drop {arm}", lambda cells, arm=arm: [c for c in cells if c.arm != arm])
    final = _totals(current, costs, overhead)
    return {"plan": current, "decisions": decisions, "projected_initial": initial, "projected_final": final,
            "limits": dict(limits), "over_after_cuts": [p for p in PROVIDERS if final[p] > limits[p]],
            "unpriced_arms": sorted({c.arm for c in plan if cost_key(c.world, c.arm) not in costs})}
