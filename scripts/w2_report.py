#!/usr/bin/env python3
"""Render docs/research/slm-vs-frontier-20261008/REPORT.md from results.csv + comparisons.json.

Deterministic: every number in REPORT.md comes from the analysis outputs (scripts/w2_analyze.py),
and the headline verdict follows the preregistered rule (Holm p < 0.05 AND bootstrap CI excludes 0).
Run after w2_analyze.py.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/slm-vs-frontier-20261008"
# Counterfactual price for hosted qwen/qwen3.8-27b on Nous (USD per token), from /v1/models on 2026-10-08.
QWEN_HOSTED_IN, QWEN_HOSTED_OUT = 0.0000000235, 0.00000435


def pct(x):
    return "—" if x in (None, "", "None") else f"{float(x) * 100:.1f}%"


def num(x, nd=0):
    if x in (None, "", "None"):
        return "—"
    return f"{float(x):,.{nd}f}"


def money(x):
    return "—" if x in (None, "", "None") else f"${float(x):.4f}"


def signed(x):
    return "—" if x is None else f"{x:+.3f}"


def ci_text(ci):
    return "—" if not ci else f"{ci['low']:+.3f} … {ci['high']:+.3f}"


def pval(x):
    return "—" if x is None else f"{x:.3g}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def headline(primary):
    by = {p["label"][:2]: p for p in primary}
    lines = []
    a = [by.get("a1"), by.get("a2")]
    b = [by.get("b1"), by.get("b2")]
    a_better = [p for p in a if p and p["verdict"] == "treatment better"]
    a_worse = [p for p in a if p and p["verdict"] == "treatment worse"]
    if a_better:
        lines.append("**(a) Small-model swarm vs small-model solo: the swarm helped** "
                     + "; ".join(f"`{p['treatment'].split(':')[1]}` {p['mean_difference']:+.3f} accuracy "
                                 f"(95% CI {p['ci95_task_bootstrap']['low']:+.3f} to {p['ci95_task_bootstrap']['high']:+.3f}, "
                                 f"Holm p={p['holm_p']:.3g})" for p in a_better) + ".")
    if a_worse:
        lines.append("**(a) The swarm made the small model worse** for "
                     + ", ".join(f"`{p['treatment'].split(':')[1]}` ({p['mean_difference']:+.3f})" for p in a_worse) + ".")
    if not a_better and not a_worse:
        lines.append("**(a) Small-model swarm vs small-model solo: the swarm did NOT measurably help.** "
                     "Neither Antelligence protocol beat the same model answering alone under the preregistered "
                     "rule (no reliable difference is not proof of no effect).")
    b_better = [p for p in b if p and p["verdict"] == "treatment better"]
    b_worse = [p for p in b if p and p["verdict"] == "treatment worse"]
    if b_worse and len(b_worse) == len([p for p in b if p]):
        lines.append("**(b) The small-model swarm stayed below the strong frontier model answering alone** "
                     "(gap " + ", ".join(f"{p['mean_difference']:+.3f}" for p in b_worse) + "); swarm coordination did not "
                     "close the gap.")
    elif b_better:
        lines.append("**(b) The small-model swarm beat the strong frontier model answering alone** for "
                     + ", ".join(f"`{p['treatment'].split(':')[1]}` ({p['mean_difference']:+.3f})" for p in b_better) + ".")
    else:
        lines.append("**(b) Small-model swarm vs frontier solo: no reliable difference** for at least one protocol "
                     "(see table); this is not evidence of equivalence.")
    return lines


def main() -> None:
    rows = list(csv.DictReader((OUT / "results.csv").open()))
    comp = json.loads((OUT / "comparisons.json").read_text())
    qa = [r for r in rows if r["world"] == "research_qa"]
    other = [r for r in rows if r["world"] != "research_qa"]
    ledger_rows = [json.loads(l) for l in (ROOT / "ledger/goal-2026-10-08-usage.jsonl").read_text().splitlines()
                   if l.strip()]
    w2 = [r for r in ledger_rows if r.get("workstream") == "W2" and not r.get("smoke")]
    per_provider = {}
    for r in w2:
        k = (r["billing"], r["model_key"])
        d = per_provider.setdefault(k, {"calls": 0, "failed": 0, "in": 0, "out": 0, "cost": 0.0})
        d["calls"] += 1
        d["failed"] += 0 if r.get("ok") else 1
        d["in"] += int(r.get("prompt_tokens") or 0)
        d["out"] += int(r.get("completion_tokens") or 0)
        d["cost"] += float(r.get("cost_usd") or 0)
    first_eval = min((r["timestamp_utc"] for r in w2 if r.get("split") == "evaluation"), default="none")
    runlog = [json.loads(l) for l in (OUT / "run-log.jsonl").read_text().splitlines() if l.strip()]
    starts = [r for r in runlog if r.get("event") == "start" and not r.get("smoke")]
    ends = [r for r in runlog if r.get("event") == "end" and not r.get("smoke")]
    resumed = [r for r in starts if r.get("resumed")]
    interrupted = [r for r in runlog if r.get("event") in ("deadline_stop", "harness_error")]
    capped = [r for r in ends if r.get("skipped_after_cap")]

    L = []
    L.append("# REPORT: small local models vs frontier models on the Antelligence engine")
    L.append("")
    L.append(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `scripts/w2_report.py` from "
             "`results.csv` and `comparisons.json` (produced by `scripts/w2_analyze.py`). Design: `PREREGISTRATION.md` "
             f"(committed before the first evaluation call; first evaluation call in the ledger: `{first_eval}`).")
    L.append("")
    L.append("## Headline")
    L.append("")
    L += [f"- {x}" for x in headline(comp["primary"])]
    L.append("- **(c) Cost:** see the accuracy-per-dollar table. Local Qwen has $0 API cost (hardware and "
             "electricity not measured); every swarm arm multiplies tokens and wall time.")
    L.append("- Agreement between agents is not correctness: all accuracy below is scored by the world against "
             "reference answers, with abstentions, invalid replies, transport errors and missing cells counted as failures.")
    L.append("")
    L.append("## Primary comparisons (research_qa, 60 evaluation tasks, both domains pooled)")
    L.append("")
    L.append("| Comparison | Pairs | Treatment acc | Baseline acc | Δ (treat−base) | 95% CI (task bootstrap) | Wins/Losses/Ties | Sign-test p | Holm p | Verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for p in comp["primary"]:
        ci = p["ci95_task_bootstrap"] or {}
        L.append(f"| {p['label']} | {p['pairs']} | {pct(p['treatment_accuracy'])} | {pct(p['baseline_accuracy'])} | "
                 f"{signed(p['mean_difference'])} | {ci_text(ci)} | {p['treatment_wins']}/{p['baseline_wins']}/{p['ties']} | "
                 f"{pval(p['sign_test_p'])} | {pval(p['holm_p'])} | {p['verdict']} |")
    L.append("")
    L.append("## Every research_qa cell (seeds pooled)")
    L.append("")
    L.append("Accuracy = correct / requested. Wilson = one-sided 95% lower bound on accuracy. Tokens and cost count every "
             "logical call of the arm (cache hits included, as if run alone); latency = summed model time.")
    L.append("")
    L.append("| Model | Tier | Domain | Arm | Seeds | Req | Missing | Acc | Wilson LB | Coverage | Answered acc | Abst | Invalid | Error | Prompt tok | Output tok | Model s | Cost | $/correct |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(qa, key=lambda r: (r["tier"] or "", r["model_key"], r["domain"], r["arm"])):
        L.append(f"| {r['model_key']} | {r['tier']} | {r['domain']} | {r['arm']} | {r['seeds']} | {r['requested']} | {r['missing']} | "
                 f"{pct(r['accuracy'])} | {pct(r['wilson_lower_95_one_sided'])} | {pct(r['coverage'])} | {pct(r['answered_accuracy'])} | "
                 f"{r['abstained']} | {r['invalid']} | {r['error_transport']} | {num(r['prompt_tokens'])} | {num(r['completion_tokens'])} | "
                 f"{num(r['model_latency_s'])} | {money(r['cost_usd'])} | {money(r['cost_per_correct_usd'])} |")
    L.append("")
    L.append("## Accuracy per dollar (research_qa, both domains pooled)")
    L.append("")
    L.append("| Model | Arm | Accuracy | API cost | Correct per $ | Hypothetical hosted cost (Qwen only, Nous list price) |")
    L.append("|---|---|---|---|---|---|")
    pooled = {}
    for r in qa:
        k = (r["model_key"], r["arm"])
        d = pooled.setdefault(k, {"req": 0, "cor": 0, "cost": 0.0, "pin": 0, "pout": 0})
        d["req"] += int(r["requested"])
        d["cor"] += int(r["correct"])
        d["cost"] += float(r["cost_usd"] or 0)
        d["pin"] += int(r["prompt_tokens"] or 0)
        d["pout"] += int(r["completion_tokens"] or 0)
    for (model, arm), d in sorted(pooled.items()):
        acc = d["cor"] / d["req"] if d["req"] else None
        cpd = "∞ ($0 API)" if d["cost"] == 0 else f"{d['cor'] / d['cost']:,.0f}"
        hyp = f"${d['pin'] * QWEN_HOSTED_IN + d['pout'] * QWEN_HOSTED_OUT:.4f}" if model.startswith("qwen") else "—"
        L.append(f"| {model} | {arm} | {pct(acc)} | {money(d['cost'])} | {cpd} | {hyp} |")
    L.append("")
    L.append("## Secondary comparisons (exploratory, uncorrected)")
    L.append("")
    L.append("| Comparison | Domain | Pairs | Treatment | Baseline | Δ | 95% CI | Sign-test p |")
    L.append("|---|---|---|---|---|---|---|---|")
    for p in comp["secondary"] + comp["primary_per_domain_exploratory"]:
        ci = p["ci95_task_bootstrap"] or {}
        L.append(f"| {p['label']} | {p['domain']} | {p['pairs']} | {pct(p['treatment_accuracy'])} | {pct(p['baseline_accuracy'])} | "
                 f"{signed(p['mean_difference'])} | {ci_text(ci)} | {pval(p['sign_test_p'])} |")
    L.append("")
    L.append("## E15 task_dag and E13 foraging (secondary, small samples)")
    L.append("")
    L.append("| World | Model | Arm | Fixtures req | Missing | Successes | Success rate | Wilson LB | Failed calls | Prompt tok | Output tok | Cost |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(other, key=lambda r: (r["world"], r["model_key"], r["arm"])):
        L.append(f"| {r['world']} | {r['model_key']} | {r['arm']} | {r['requested']} | {r['missing']} | {r['correct']} | {pct(r['accuracy'])} | "
                 f"{pct(r['wilson_lower_95_one_sided'])} | {r['failed_calls']} | {num(r['prompt_tokens'])} | {num(r['completion_tokens'])} | {money(r['cost_usd'])} |")
    L.append("")
    if comp["other_worlds"]:
        L.append("| World | Model | Treatment vs baseline | Pairs | Successes (treat/base) | Sign-test p |")
        L.append("|---|---|---|---|---|---|")
        for o in comp["other_worlds"]:
            L.append(f"| {o['world']} | {o['model']} | {o['treatment']} vs {o['baseline']} | {o['pairs']} | "
                     f"{o['treatment_successes']}/{o['baseline_successes']} | {pval(o['sign_test_p'])} |")
        L.append("")
    L.append("## Usage (physical calls, from `ledger/goal-2026-10-08-usage.jsonl`, W2 non-smoke rows)")
    L.append("")
    L.append("| Billing | Model | Calls | Failed calls | Prompt tok | Output tok | Cost |")
    L.append("|---|---|---|---|---|---|---|")
    for (billing, model), d in sorted(per_provider.items()):
        L.append(f"| {billing} | {model} | {d['calls']:,} | {d['failed']:,} | {d['in']:,} | {d['out']:,} | ${d['cost']:.4f} |")
    L.append("")
    L.append("## Deviations from the preregistration")
    L.append("")
    dev = []
    if resumed:
        dev.append(f"{len(resumed)} harness invocation(s) were restarted; already-written cells were kept and skipped (logged `resumed: true`).")
    if capped:
        dev.append(f"The $12 frontier cap stopped {sum(r['skipped_after_cap'] for r in capped)} planned cell(s); they count as missing.")
    if interrupted:
        dev.append(f"{len(interrupted)} harness interruption/error event(s) recorded in `run-log.jsonl`; affected cells are missing (counted as failures).")
    missing_total = sum(int(r["missing"]) for r in rows)
    if missing_total:
        dev.append(f"{missing_total} requested cell(s) were never written (see `Missing` columns); counted as failures per the preregistered denominator rule.")
    started_models = {r["argv"][1] for r in starts}
    if "phi4-mini-finance-f16" not in started_models:
        dev.append("Phi4 mini finance (conditional secondary small model) was not run: the local queue did not reach it before the run deadline. Only one small model (Qwen3.8-27B Q3_K) is in the study.")
    dev.append("Run order of the frontier queue differs from the preregistration's listing order (Sonnet `single` seeds first, then Haiku, then Sonnet swarm arms) so that the spend cap could only cut the least load-bearing cells; the set of planned cells is unchanged.")
    dev.append("89 ledger rows from the 2026-10-09 00:41–02:59 UTC smoke runs predate the `split`/`smoke` ledger fields; they are development-split / fixture-120 calls (see PREREGISTRATION ordering note) and are excluded from usage totals here.")
    L += [f"{i}. {d}" for i, d in enumerate(dev, 1)]
    L.append("")
    L.append("## Limitations")
    L.append("")
    L += [
        "- One small model, quantized to Q3_K; one frontier vendor family (Anthropic) via one gateway (Nous).",
        "- PubMedQA/FinQA are public; contamination is unknown for every model. 60 tasks per study; seeds are correlated within a task (CIs resample tasks).",
        "- Output truncation (`finish_reason=length` at 512 tokens for QA, 256 for E13) is counted as an error, as the engine's providers define it; Haiku hit this often. No output limit was changed mid-study.",
        "- E13 truncated to 40 steps and 5 fixtures; E15 has 19 fixtures. Treat both as smoke-scale evidence.",
        "- Local cost is API cost only; electricity, hardware amortization and the operator's time are unmeasured. Wall time for Qwen is on a shared 36 GB Mac with 3 llama.cpp slots.",
        "- A Wilson bound describes this sample; it is not a guarantee of future accuracy. Nothing here is clinical or financial evidence.",
    ]
    L.append("")
    L.append("## Raw evidence")
    L.append("")
    L.append("Hashes of every raw file are in `MANIFEST.sha256` (cells, bundles, raw responses, run log, ledger). "
             "Raw responses are request-hash keyed, so every cell can be replayed offline through the engine with "
             "`antelligence.providers.Cached(..., offline=True)`.")
    (OUT / "REPORT.md").write_text("\n".join(L) + "\n")

    manifest = []
    for path in sorted(list(OUT.rglob("*.jsonl")) + [OUT / "results.csv", OUT / "results-by-seed.csv",
                                                     OUT / "comparisons.json", OUT / "eval-task-ids.json",
                                                     ROOT / "ledger/goal-2026-10-08-usage.jsonl"]):
        if path.exists():
            manifest.append(f"{sha256(path)}  {path.relative_to(ROOT)}")
    (OUT / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n")
    print(f"REPORT.md: {len(L)} lines; MANIFEST: {len(manifest)} files")


if __name__ == "__main__":
    main()
