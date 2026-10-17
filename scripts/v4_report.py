"""Generate REPORT.md from the v4 pilot results.json (stdlib only, deterministic).

Usage: python v4_report.py <results.json> <REPORT.md>

Every number is read from results.json; nothing is typed by hand. Missing values print as an em dash.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

DASH = "—"
DS, FRAMEWORK = "DS-all", ("F-Jev", "F-Laya")
INCOMPLETE_LIMIT = 0.20  # preregistration section 8: an arm missing more than 20% of planned cells is incomplete
CONDITIONS = ("base", "v1", "v2")


def num(x: Any, nd: int) -> str:
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return DASH
    return f"{x:.{nd}f}"


def g3(x: Any) -> str:
    return num(x, 3)


def sec(x: Any) -> str:
    return num(x, 2)


def usd(x: Any) -> str:
    return DASH if x is None else "$" + num(x, 4)


def cnt(x: Any) -> str:
    return DASH if x is None or isinstance(x, bool) else f"{int(x)}" if isinstance(x, (int, float)) else DASH


def flag(x: Any) -> str:
    return DASH if x is None else "yes" if x else "no"


def get(d: Any, *path: str) -> Any:
    for p in path:
        if not isinstance(d, Mapping):
            return None
        d = d.get(p)
    return d


def arm_order(names: Sequence[str]) -> List[str]:
    first = ["S", "S-prime", DS, "F-Jev", "F-Laya"]
    return [a for a in first if a in names] + sorted(a for a in names if a not in first)


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


# --- completeness ------------------------------------------------------------


def planned_counts(results: Mapping[str, Any]) -> Optional[Dict[str, int]]:
    """Planned cells per arm: top-level ``planned_cells`` {arm: n}, else ``arms[arm].planned_cells``."""
    top = results.get("planned_cells")
    if isinstance(top, Mapping) and top:
        return {a: int(n) for a, n in top.items()}
    per = {a: s["planned_cells"] for a, s in (results.get("arms") or {}).items()
           if isinstance(s, Mapping) and s.get("planned_cells") is not None}
    return {a: int(n) for a, n in per.items()} if per else None


def completeness(results: Mapping[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
    planned = planned_counts(results)
    if planned is None:
        return None
    out: Dict[str, Dict[str, Any]] = {}
    for arm in arm_order(list(planned)):
        s = get(results, "arms", arm) or {}
        done = int(s.get("cells", 0)) - int(s.get("errors", 0))
        out[arm] = {"planned": planned[arm], "cells": s.get("cells", 0), "errors": s.get("errors", 0),
                    "incomplete": planned[arm] > 0 and (planned[arm] - done) > INCOMPLETE_LIMIT * planned[arm]}
    return out


# --- sections ------------------------------------------------------------------


def header(r: Mapping[str, Any]) -> List[str]:
    prereg = r.get("prereg_commit") or "see PREREGISTRATION.md"
    return ["# Antelligence v4 pilot report", "",
            "Generated from `results.json` by `v4_report.py`. No number in this file is typed by hand.", "",
            "- Pilot: v4 pilot, can a queen and small workers handle surprises?",
            f"- Preregistration commit: {prereg}",
            f"- Cells in results: {cnt(r.get('cells'))}", "",
            "> **Pilot estimates.** " + str(r.get("note") or "Small sample; detects only large effects").rstrip(".")
            + ". Do not read these as confirmed effects.", ""]


def verdict_section(r: Mapping[str, Any], comp: Optional[Mapping[str, Mapping[str, Any]]]) -> List[str]:
    v = r.get("go_no_go") or {}
    rule = v.get("rule") or {}
    margin, nogo = rule.get("go_margin"), rule.get("no_go_g")
    raw = v.get("verdict")
    forced = bool(comp) and any(comp.get(a, {}).get("incomplete") for a in (DS, *FRAMEWORK) if a in comp)
    final = "unclear" if forced else raw
    out = ["## Go / no-go verdict", "",
           f"**Verdict: {str(final).upper() if final else DASH}**", ""]
    if forced:
        out += [f"Rule verdict was `{raw}`, overridden to `unclear` because DS-all, F-Jev or F-Laya is incomplete "
                "(preregistration section 8).", ""]
    out += ["Rule (fixed in the preregistration):",
            f"- Go: a framework arm's paired mean G is at least DS-all's paired mean G minus {num(margin, 2)}, "
            "and its median seconds per decision is lower than DS-all's.",
            f"- No-go: both framework arms have paired mean G below {num(nogo, 2)}. No-go takes precedence.",
            "- Otherwise: unclear.", "",
            f"- Paired keys (world, seed, condition): {cnt(v.get('paired_keys'))}",
            f"- DS-all paired mean G: {g3(get(v, 'ds_all', 'mean_g'))}",
            f"- DS-all median s/decision: {sec(get(v, 'ds_all', 'median_s_per_decision'))}",
            f"- go_also_holds: {flag(v.get('go_also_holds'))}",
            f"- Arms meeting Go: {', '.join(v.get('go_arms') or []) or 'none'}", ""]
    rows = []
    for arm in arm_order(list((v.get("arms") or {}).keys())):
        a = v["arms"][arm]
        rows.append([arm, g3(a.get("mean_g")), sec(a.get("median_s_per_decision")), flag(a.get("g_within_margin")),
                     flag(a.get("faster")), flag(a.get("go")), flag(a.get("below_no_go_line"))])
    return out + table(["Arm", "Paired mean G", "Median s/decision", "G within margin", "Faster than DS-all", "Go",
                        "Below no-go line"], rows)


def comparison_section(r: Mapping[str, Any]) -> List[str]:
    comps = r.get("comparisons_mean_g_diff") or {}
    level = next((c.get("level") for c in comps.values() if c.get("level") is not None), None)
    resamples = next((c.get("resamples") for c in comps.values() if c.get("resamples") is not None), None)
    rows = []
    for name in sorted(comps):
        c = comps[name]
        rows.append([name.replace("_vs_", " vs "), cnt(c.get("pairs")), cnt(c.get("seeds")), g3(c.get("mean_diff")),
                     f"[{g3(c.get('low'))}, {g3(c.get('high'))}]"])
    out = ["## Primary comparison", "",
           "Mean G difference on shared (world, seed, condition) keys; percentile bootstrap over seed clusters"
           f" (confidence level {num(level, 2)}, {cnt(resamples)} resamples). Pilot estimates.", ""]
    return out + table(["Comparison", "Pairs", "Seeds", "Mean diff", "95% CI"], rows)


def arm_tables(arms: Mapping[str, Mapping[str, Any]], title: str) -> List[str]:
    names = arm_order(list(arms))
    specs: Sequence[tuple] = (
        ("Score and gap recovered", [
            ("Cells", lambda s: cnt(s.get("cells"))), ("Errors", lambda s: cnt(s.get("errors"))),
            ("Mean G", lambda s: g3(s.get("mean_g"))),
            ("Mean G V1", lambda s: g3(get(s, "mean_g_by_condition", "v1"))),
            ("Mean G V2", lambda s: g3(get(s, "mean_g_by_condition", "v2"))),
            ("Base share of S", lambda s: g3(s.get("base_share_of_S"))),
            ("Score base", lambda s: g3(get(s, "score_by_condition", "base"))),
            ("Score V1", lambda s: g3(get(s, "score_by_condition", "v1"))),
            ("Score V2", lambda s: g3(get(s, "score_by_condition", "v2"))),
            ("G undefined", lambda s: cnt(s.get("g_undefined")))]),
        ("Time, calls and cost", [
            ("Median s/decision", lambda s: sec(get(s, "s_per_decision", "median"))),
            ("p90 s/decision", lambda s: sec(get(s, "s_per_decision", "p90"))),
            ("Ticks (mean)", lambda s: sec(s.get("ticks_mean"))),
            ("Wall s (mean)", lambda s: sec(s.get("wall_s_mean"))),
            ("Calls", lambda s: cnt(s.get("calls"))), ("Input tokens", lambda s: cnt(s.get("input_tokens"))),
            ("Output tokens", lambda s: cnt(s.get("output_tokens"))), ("Cost", lambda s: usd(s.get("cost_usd")))]),
        ("Worker behaviour", [
            ("Compliance", lambda s: g3(s.get("compliance"))),
            ("Report precision", lambda s: g3(s.get("report_precision"))),
            ("Reports", lambda s: cnt(s.get("reports"))),
            ("Escalation rate", lambda s: g3(s.get("escalation_rate"))),
            ("Policy failures", lambda s: cnt(s.get("policy_failures")))]),
    )
    out = [title, ""]
    for sub, cols in specs:
        out += [f"**{sub}**", ""]
        fns: List[Callable[[Mapping[str, Any]], str]] = [f for _, f in cols]
        out += table(["Arm"] + [c for c, _ in cols], [[a] + [f(arms[a]) for f in fns] for a in names])
    return out


def completeness_section(comp: Optional[Mapping[str, Mapping[str, Any]]]) -> List[str]:
    out = ["## Incomplete-arm rule", "",
           "An arm missing more than 20% of its planned cells is reported as incomplete. The verdict is `unclear` "
           "if DS-all, F-Jev or F-Laya is incomplete.", ""]
    if comp is None:
        return out + ["Planned counts not provided.", ""]
    rows = [[a, cnt(c["planned"]), cnt(c["cells"]), cnt(c["errors"]), "INCOMPLETE" if c["incomplete"] else "complete"]
            for a, c in comp.items()]
    return out + table(["Arm", "Planned cells", "Cells", "Errors", "Status"], rows)


def render(results: Mapping[str, Any]) -> str:
    comp = completeness(results)
    lines: List[str] = header(results)
    lines += verdict_section(results, comp)
    lines += comparison_section(results)
    lines += arm_tables(results.get("arms") or {}, "## Per-arm results (all worlds)")
    for world in sorted(results.get("by_world") or {}):
        lines += arm_tables(results["by_world"][world], f"## Per-world results: {world}")
    lines += completeness_section(comp)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python v4_report.py <results.json> <REPORT.md>", file=sys.stderr)
        return 2
    results = json.loads(Path(args[0]).read_text())
    Path(args[1]).write_text(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
