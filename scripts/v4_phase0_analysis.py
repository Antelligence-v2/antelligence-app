"""v4 pilot Phase 0 analysis: per-backend calibration cells and the escalation threshold grid.

Reads the local, gitignored calibration rows (one JSONL per backend), writes AGGREGATE results only
(phase0-summary.json and phase0-summary.md); no per-item rows or state texts leave this script.
Deterministic: no randomness, no network, no model calls.

    uv run python scripts/v4_phase0_analysis.py [--rows DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from antelligence.experiments.v4_metrics import brier, calibration_summary, mean, percentile  # noqa: E402

BACKENDS = ("laya", "jev", "deepseek", "qwen3.5-9b")
DECISION_MODELS = ("laya", "jev")
ESCALATION_MODEL = "qwen3.5-9b"
WORLD_SETS = {"both": None, "foraging_sb": "foraging_sb", "graph_coloring": "graph_coloring"}
KINDS = ("all", "judgement", "move")
NOUL_BANDS = ((0.1, 0.9), (0.2, 0.8), (0.3, 0.7), (0.35, 0.65), None)
C_MINS = (0.3, 0.4, 0.5, 0.6, 0.7, None)
GOAL_DEFAULT = {"band": (0.2, 0.8), "c_min": 0.5}
MAX_ESC_RATE = 0.5
DEFAULT_ROWS = ROOT / "ledger/v4-pilot-dev/phase0-final/calibration"
DEFAULT_OUT = ROOT / "docs/research/v4-pilot-20261011/phase0"


def load_rows(rows_dir: Path, backends: Sequence[str] = BACKENDS) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for b in backends:
        with (rows_dir / f"{b}.jsonl").open() as fh:
            out[b] = [json.loads(line) for line in fh if line.strip()]
    return out


def scored(row: Mapping[str, Any]) -> bool:
    return not row.get("error") and row.get("prob") is not None


def chance(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Judgement chance = majority-label rate; move chance = mean(|accept| / |options|). Scored rows only."""
    ok = [r for r in rows if scored(r)]
    jud = [r for r in ok if r["kind"] == "judgement"]
    mov = [r for r in ok if r["kind"] == "move"]
    j = None
    if jud:
        yes = sum(1 for r in jud if r["label"])
        j = max(yes, len(jud) - yes) / len(jud)
    m = mean(len(r.get("accept") or [r["answer"]]) / len(r["probabilities"]) for r in mov) if mov else None
    parts = [(v, n) for v, n in ((j, len(jud)), (m, len(mov))) if v is not None]
    total = sum(n for _, n in parts)
    return {"judgement": j, "move": m, "all": sum(v * n for v, n in parts) / total if total else None}


def cell_stats(rows: Sequence[Mapping[str, Any]], kind: str) -> Dict[str, Any]:
    sel = [r for r in rows if kind == "all" or r["kind"] == kind]
    s = calibration_summary(sel)
    return {"n": s["n"], "scored": s["scored"], "errors": s["errors"], "accuracy": s["accuracy"],
            "brier": s["brier"], "ece": s["ece"], "chance": chance(sel)[kind],
            "latency_median_s": s["latency_s"]["median"], "latency_p90_s": s["latency_s"]["p90"]}


def calibration_table(data: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for b, rows in data.items():
        out[b] = {}
        for wname, w in WORLD_SETS.items():
            sel = [r for r in rows if w is None or r["world"] == w]
            out[b][wname] = {k: cell_stats(sel, k) for k in KINDS}
    return out


def confidence(row: Mapping[str, Any]) -> float:
    """Rows carry no backend confidence; max probability over all options is the proxy."""
    return max(row["probabilities"].values())


def uncertain(row: Mapping[str, Any], setting: Any) -> bool:
    """Same boundary rule as EscalatingBackend: noul lo < p < hi; choice confidence < c_min. None = never."""
    if setting is None:
        return False
    if row["type"] == "noul":
        lo, hi = setting
        return lo < row["prob"] < hi
    return confidence(row) < setting


def combine(dm: Sequence[Mapping[str, Any]], slm: Mapping[str, Mapping[str, Any]], setting: Any) -> Dict[str, Any]:
    """Decision model answers when confident; the SLM's when escalated. SLM error keeps the decision model's."""
    final, esc, esc_dm, esc_slm_dm, esc_slm, lat, n_slm_err = [], 0, [], [], [], [], 0
    for r in dm:
        if not scored(r):
            continue
        use, extra = r, 0.0
        if uncertain(r, setting):
            esc += 1
            q = slm.get(r["id"])
            extra = float(q["latency_s"]) if q and q.get("latency_s") is not None else 0.0
            esc_dm.append(r)
            if q is not None and scored(q):
                use = q
                esc_slm.append(q)
                esc_slm_dm.append(r)
            else:
                n_slm_err += 1
        final.append(use)
        lat.append(float(r["latency_s"]) + extra)
    n = len(final)
    correct = sum(1 for r in final if r["correct"])
    return {
        "n": n, "escalated": esc, "escalation_rate": esc / n if n else None,
        "slm_errors_on_escalated": n_slm_err,
        "correct": correct, "accuracy": correct / n if n else None,
        "brier": brier([float(r["prob"]) for r in final], [bool(r["label"]) for r in final]),
        "latency_median_s": percentile(lat, 50), "latency_mean_s": mean(lat),
        "escalated_subset": {
            "n": len(esc_dm), "dm_accuracy": mean(float(r["correct"]) for r in esc_dm),
            "slm_scored": len(esc_slm), "slm_accuracy": mean(float(r["correct"]) for r in esc_slm),
            "dm_accuracy_on_slm_scored": mean(float(r["correct"]) for r in esc_slm_dm)},
    }


def setting_label(setting: Any) -> str:
    return "none" if setting is None else f"{setting[0]}/{setting[1]}" if isinstance(setting, tuple) else str(setting)


def grid(dm_rows: Sequence[Mapping[str, Any]], slm_rows: Sequence[Mapping[str, Any]],
         qtype: str) -> List[Dict[str, Any]]:
    slm = {r["id"]: r for r in slm_rows}
    rows = [r for r in dm_rows if r["type"] == qtype]
    settings = NOUL_BANDS if qtype == "noul" else C_MINS
    return [{"setting": setting_label(s), **combine(rows, slm, s)} for s in settings]


def propose(cells: Sequence[Mapping[str, Any]], default_label: str) -> Dict[str, Any]:
    """Max combined accuracy with escalation rate <= MAX_ESC_RATE; ties go to the lower rate, then lower Brier."""
    ok = [c for c in cells if c["escalation_rate"] <= MAX_ESC_RATE] or list(cells)
    best = min(ok, key=lambda c: (-c["correct"], c["escalation_rate"], c["brier"], c["setting"]))
    none = next(c for c in cells if c["setting"] == "none")
    top = min(cells, key=lambda c: (-c["correct"], c["escalation_rate"], c["brier"], c["setting"]))
    dflt = next((c for c in cells if c["setting"] == default_label), None)
    return {"setting": best["setting"], "correct": best["correct"], "n": best["n"], "accuracy": best["accuracy"],
            "brier": best["brier"], "escalation_rate": best["escalation_rate"],
            "items_gained_vs_none": best["correct"] - none["correct"],
            "items_gained_vs_goal_default": None if dflt is None else best["correct"] - dflt["correct"],
            "best_unconstrained": {"setting": top["setting"], "accuracy": top["accuracy"],
                                   "escalation_rate": top["escalation_rate"]},
            "goal_default": default_label, "max_escalation_rate": MAX_ESC_RATE}


def split_by_world(dm_rows, slm_rows, qtype, setting_text) -> Dict[str, Any]:
    slm = {r["id"]: r for r in slm_rows}
    setting: Any = None
    if setting_text != "none":
        setting = tuple(float(x) for x in setting_text.split("/")) if qtype == "noul" else float(setting_text)
    out = {}
    for w in ("foraging_sb", "graph_coloring"):
        rows = [r for r in dm_rows if r["type"] == qtype and r["world"] == w]
        none = combine(rows, slm, None)
        c = combine(rows, slm, setting)
        out[w] = {"n": c["n"], "escalation_rate": c["escalation_rate"], "accuracy": c["accuracy"],
                  "accuracy_no_escalation": none["accuracy"], "brier": c["brier"]}
    return out


def noul_spread(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Where a backend's P(yes) actually falls; a band outside this range can never be confident."""
    p = [float(r["prob"]) for r in rows if r["type"] == "noul" and scored(r)]
    return {"min": min(p), "p10": percentile(p, 10), "median": percentile(p, 50), "p90": percentile(p, 90),
            "max": max(p)}


def analyse(data: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    slm_rows = data[ESCALATION_MODEL]
    esc: Dict[str, Any] = {}
    proposals: Dict[str, Any] = {}
    for m in DECISION_MODELS:
        noul = grid(data[m], slm_rows, "noul")
        choice = grid(data[m], slm_rows, "choice")
        pn = propose(noul, setting_label(GOAL_DEFAULT["band"]))
        pc = propose(choice, setting_label(GOAL_DEFAULT["c_min"]))
        pn["by_world"] = split_by_world(data[m], slm_rows, "noul", pn["setting"])
        pc["by_world"] = split_by_world(data[m], slm_rows, "choice", pc["setting"])
        esc[m] = {"noul": noul, "choice": choice}
        proposals[m] = {"noul_band": pn, "choice_c_min": pc}
    return {
        "source": "local calibration rows (gitignored); 150 judgement + 150 move items per backend, development seeds",
        "backends": list(data), "calibration": calibration_table(data),
        "escalation": {"escalation_model": ESCALATION_MODEL, "grid": esc,
                       "noul_p_yes_spread": {m: noul_spread(data[m]) for m in DECISION_MODELS},
                       "choice_confidence": "max probability over all options (rows carry no backend confidence)",
                       "noul_rule": "escalate when lo < P(yes) < hi (EscalatingBackend boundaries)",
                       "slm_error_rule": "keep the decision model's answer"},
        "proposed": proposals,
        "goal_defaults": {"band": setting_label(GOAL_DEFAULT["band"]), "c_min": GOAL_DEFAULT["c_min"]},
    }


# --- markdown ---------------------------------------------------------------


def f(x: Optional[float], d: int = 3) -> str:
    return "-" if x is None else f"{x:.{d}f}"


def render_md(s: Mapping[str, Any]) -> str:
    L: List[str] = ["# Phase 0 calibration summary", "",
                    "Aggregate results only. Every number below is read from `phase0-summary.json`, produced by "
                    "`scripts/v4_phase0_analysis.py` from the local calibration rows (150 judgement and 150 move "
                    "items per backend, development seeds).", "",
                    "Accuracy is scored at 0.5 for judgements. Brier and ECE use the probability of the right "
                    "answer (moves: summed over the accepted options). Chance for a judgement is the "
                    "majority-label rate; for a move it is the mean of accepted options over all options. "
                    "Chance and all statistics use scored items only; errored items are counted in n and errors.", ""]
    for wname in WORLD_SETS:
        L += [f"## Calibration: {wname.replace('_', ' ') if wname != 'both' else 'both worlds'}", "",
              "| backend | kind | n | scored | errors | accuracy | chance | Brier | ECE | latency median s | p90 s |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for b in s["backends"]:
            for k in KINDS:
                c = s["calibration"][b][wname][k]
                L.append(f"| {b} | {k} | {c['n']} | {c['scored']} | {c['errors']} | {f(c['accuracy'])} | "
                         f"{f(c['chance'])} | {f(c['brier'])} | {f(c['ece'])} | {f(c['latency_median_s'], 2)} | "
                         f"{f(c['latency_p90_s'], 2)} |")
        L.append("")
    L += ["## Escalation grid", "",
          "The decision model answers when confident; Qwen3.5-9B answers when escalated; if Qwen errors on an "
          "escalated item the decision model's answer is kept. Noul escalates when lo < P(yes) < hi. Choice "
          "escalates when the decision model's confidence is below c_min; the rows carry no backend confidence, "
          "so the maximum probability over all options is the proxy. `none` means never escalate. "
          "`dm acc esc` and `slm acc esc` are the decision model's and Qwen's accuracy on the escalated subset "
          "(Qwen's over the items it scored; `dm acc same` is the decision model on those same items). "
          "Latency adds Qwen's wall-clock to escalated items.", ""]
    for m in DECISION_MODELS:
        for qt, label in (("noul", "noul (judgements)"), ("choice", "choice (moves)")):
            L += [f"### {m}: {label}", "",
                  "| setting | n | escalated | rate | slm errors | accuracy | Brier | dm acc esc | slm acc esc | "
                  "dm acc same | latency median s | latency mean s |",
                  "|" + "---|" * 12]
            for c in s["escalation"]["grid"][m][qt]:
                e = c["escalated_subset"]
                L.append(f"| {c['setting']} | {c['n']} | {c['escalated']} | {f(c['escalation_rate'])} | "
                         f"{c['slm_errors_on_escalated']} | {f(c['accuracy'])} | {f(c['brier'])} | "
                         f"{f(e['dm_accuracy'])} | {f(e['slm_accuracy'])} | {f(e['dm_accuracy_on_slm_scored'])} | "
                         f"{f(c['latency_median_s'], 2)} | {f(c['latency_mean_s'], 2)} |")
            L.append("")
    L += ["## Proposed thresholds", "",
          f"Rule: highest combined accuracy with escalation rate at most {MAX_ESC_RATE}; ties go to the lower "
          "escalation rate, then the lower Brier. Goal defaults are "
          f"{s['goal_defaults']['band']} for noul and c_min {s['goal_defaults']['c_min']} for choice.", "",
          "| model | question | proposed | accuracy | escalation rate | Brier | items gained vs none | "
          "items gained vs goal default |", "|---|---|---|---|---|---|---|---|"]
    for m in DECISION_MODELS:
        for key, name in (("noul_band", "noul band"), ("choice_c_min", "choice c_min")):
            p = s["proposed"][m][key]
            L.append(f"| {m} | {name} | {p['setting']} | {f(p['accuracy'])} ({p['correct']}/{p['n']}) | "
                     f"{f(p['escalation_rate'])} | {f(p['brier'])} | {p['items_gained_vs_none']} | "
                     f"{p['items_gained_vs_goal_default']} |")
    L += ["", "Notes generated from the table values:", ""]
    for m in DECISION_MODELS:
        sp = s["escalation"]["noul_p_yes_spread"][m]
        pn, pc = s["proposed"][m]["noul_band"], s["proposed"][m]["choice_c_min"]
        L.append(f"- {m}: P(yes) on judgements spans {f(sp['min'])} to {f(sp['max'])} (median {f(sp['median'])}). "
                 f"Without the rate cap the best noul setting is {pn['best_unconstrained']['setting']} "
                 f"(accuracy {f(pn['best_unconstrained']['accuracy'])}, escalation rate "
                 f"{f(pn['best_unconstrained']['escalation_rate'])}); the best choice setting is "
                 f"{pc['best_unconstrained']['setting']} (accuracy {f(pc['best_unconstrained']['accuracy'])}, "
                 f"escalation rate {f(pc['best_unconstrained']['escalation_rate'])}).")
    L += ["", "Per world at the proposed setting:", "",
          "| model | question | world | n | escalation rate | accuracy | accuracy without escalation |",
          "|---|---|---|---|---|---|---|"]
    for m in DECISION_MODELS:
        for key, name in (("noul_band", "noul band"), ("choice_c_min", "choice c_min")):
            for w, v in s["proposed"][m][key]["by_world"].items():
                L.append(f"| {m} | {name} | {w} | {v['n']} | {f(v['escalation_rate'])} | {f(v['accuracy'])} | "
                         f"{f(v['accuracy_no_escalation'])} |")
    L += ["", "Each cell has about 75 items, so a difference of a few items is within noise.", ""]
    return "\n".join(L)


def write_outputs(summary: Mapping[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "phase0-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "phase0-summary.md").write_text(render_md(summary))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    write_outputs(analyse(load_rows(a.rows)), a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
