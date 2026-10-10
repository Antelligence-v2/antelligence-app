#!/usr/bin/env python3
"""Colony-v2 analysis: implements PREREGISTRATION.md sections 5-9, fully offline from cells/*.jsonl.

Reads ``cells/<model>-<split>.jsonl`` (written by colony_v2_collect.py), assembles every arm from
those replies, and writes ``results.json`` plus a ``REPORT.md`` generated only from results.json.
An arm whose cells are missing is reported as "not run"; nothing crashes.

Statistics
* McNemar: exact two-sided binomial test on the discordant pairs.
* Newcombe (1998), "Improved confidence intervals for the difference between binomial proportions
  based on paired data", Statistics in Medicine 17:2635-2650, method 10: Wilson score intervals for
  the two paired proportions combined through a continuity-corrected phi.
* Wilson score intervals for single proportions; Holm step-down across the two domains.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.kernel.aggregate import ABSTAIN, FORCED, UNVERIFIED, Aggregator, Vote, canonical_answer  # noqa: E402
from antelligence.kernel.independence import independence  # noqa: E402
from antelligence.kernel.reputation import EVALUATOR, LABEL, ReputationLedger  # noqa: E402

EXP = ROOT / "docs/research/colony-v2-20261010"
DOMAINS = ("medical", "finance")
CHANCE = {"medical": 1 / 3, "finance": 1 / 2}
CHOICES = {"medical": ["yes", "no", "maybe"], "finance": None}
MEMBERS = {"colony_local": ("qwen", "phi", "gemma"), "colony_haiku": ("qwen", "phi", "haiku")}
ALL_MODELS = ("qwen", "phi", "gemma", "haiku")
TAU, MIN_SUPPORT = 0.6, 1.0
ABLATIONS = {"a_no_correlation": {"use_correlation": False}, "b_no_reputation": {"use_reputation": False},
             "c_no_verification": {"use_verification": False},
             "d_plain_plurality": {"use_correlation": False, "use_reputation": False, "use_verification": False}}
# Proposed thresholds for the explained-null checklist where the preregistration says "near 0" / "about equal".
NEAR_ZERO_WEIGHT, RHO_SHIFT = 0.25, 0.3


class NotRun(Exception):
    pass


# ------------------------------------------------------------------ statistics
def wilson(k: int, n: int, z: float = 1.959964) -> Optional[Tuple[float, float]]:
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar p from discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def newcombe_paired(a: int, b: int, c: int, d: int) -> Tuple[float, float, float]:
    """Newcombe method 10 for p1 - p2 with p1=(a+b)/N, p2=(a+c)/N; returns (diff, lower, upper)."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    marg = (a + b) * (c + d) * (a + c) * (b + d)
    corr = a * d - b * c
    if corr > n / 2:
        corr -= n / 2
    elif corr > 0:
        corr = 0.0
    phi = corr / math.sqrt(marg) if marg > 0 else 0.0
    lo = (p1 - p2) - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = (p1 - p2) + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return p1 - p2, lo, hi


def holm(pvals: Sequence[float]) -> List[float]:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def ece_brier(pairs: Sequence[Tuple[float, bool]], bins: int = 10) -> Dict[str, Any]:
    if not pairs:
        return {"n": 0, "ece": None, "brier": None}
    table: Dict[int, List[Tuple[float, bool]]] = {}
    for conf, ok in pairs:
        table.setdefault(min(int(conf * bins), bins - 1), []).append((conf, ok))
    ece = sum(len(v) / len(pairs) * abs(sum(o for _, o in v) / len(v) - sum(c for c, _ in v) / len(v))
              for v in table.values())
    return {"n": len(pairs), "ece": round(ece, 6), "brier": round(sum((c - o) ** 2 for c, o in pairs) / len(pairs), 6)}


# ------------------------------------------------------------------------ data
class Data:
    SPLITS = ("development", "evaluation")

    def __init__(self, cells: Sequence[Dict[str, Any]]) -> None:
        self.cells = {(c["model"], c["split"], c["task_id"], c["sample"]): c for c in cells}
        self.tasks: Dict[str, Dict[str, str]] = {"development": {}, "evaluation": {}}
        for c in cells:
            self.tasks[c["split"]][c["task_id"]] = c["domain"]
        self.truth: Dict[Tuple[str, str], bool] = {}
        for c in cells:  # a canonical answer is right or wrong for its task, whoever gave it
            if c["answer"] is not None:
                self.truth[(c["task_id"], canonical_answer(c["answer"]))] = bool(c["correct"])

    @classmethod
    def load(cls, cells_dir: Path) -> "Data":
        rows = [json.loads(ln) for f in sorted(cells_dir.glob("*.jsonl")) if f.stem.rpartition("-")[2] in cls.SPLITS
                for ln in f.read_text().splitlines() if ln.strip()] if cells_dir.exists() else []
        return cls(rows)

    def need(self, model: str, split: str, sample: int) -> None:
        if not self.tasks[split] or any((model, split, t, sample) not in self.cells for t in self.tasks[split]):
            raise NotRun(f"{model} {split} sample {sample} missing")

    def row(self, model: str, split: str, task: str, sample: int) -> Dict[str, Any]:
        return self.cells[(model, split, task, sample)]


def answer_of(row: Dict[str, Any]) -> Optional[str]:
    return canonical_answer(row["answer"]) if row["status"] == "completed" and row["answer"] is not None else None


def verification_of(row: Dict[str, Any]) -> str:
    return (row.get("verification") or {}).get("status", UNVERIFIED)


Seats = List[Tuple[str, str, str, int]]  # (seat label, persona, model, sample)


def solo(data: Data, model: str, split: str, k: int) -> Dict[str, Dict[str, Any]]:
    """Plurality of the first k samples; ties go to the earliest sample among the tied answers."""
    for s in range(1, k + 1):
        data.need(model, split, s)
    out = {}
    for t in data.tasks[split]:
        answers = [answer_of(data.row(model, split, t, s)) for s in range(1, k + 1)]
        votes = [a for a in answers if a is not None]
        top = None
        if votes:
            counts = Counter(votes)
            top = max(counts, key=lambda a: (counts[a], -votes.index(a)))
        out[t] = {"answer": top, "correct": top is not None and data.truth.get((t, top)) is True,
                  "conf": None if top is None else counts[top] / k}
    return out


def dev_rho(data: Data, seats: Seats) -> Dict[Tuple[str, str], Optional[float]]:
    """Error-correlation lookup from development errors (min_overlap 20, prior 0)."""
    errors = {}
    for label, _, model, s in seats:
        data.need(model, "development", s)
        errors[label] = {t: int(not data.row(model, "development", t, s)["correct"]) for t in data.tasks["development"]}
    rep = independence(errors, agents=[x[0] for x in seats], min_overlap=20, prior=0.0, bootstrap=0)
    return {(a, b): rep.rho[a][b] for a in rep.agents for b in rep.agents if a != b}


def warm_ledger(data: Data) -> ReputationLedger:
    """Dev-split warm-up: sample-1 label verdicts per model and domain, written by the evaluator."""
    ledger = ReputationLedger()
    for m in ALL_MODELS:
        if all((m, "development", t, 1) in data.cells for t in data.tasks["development"]):
            for t, d in data.tasks["development"].items():
                ledger.record(persona=m, area=d, channel=LABEL, success=bool(data.row(m, "development", t, 1)["correct"]),
                              author=EVALUATOR, ref=t)
    return ledger


def reliability(ledger: Optional[ReputationLedger], domain: str) -> Callable[[str, float], float]:
    if ledger is None:  # cold start: every persona sits exactly at chance, so every weight is 0
        return lambda persona, chance: chance
    return lambda persona, chance: ledger.accuracy(persona, domain, chance=CHANCE[domain])


def colony(data: Data, seats: Seats, ledger: Optional[ReputationLedger], rho: Dict, *, mode: str = FORCED,
           tau: float = TAU, split: str = "evaluation", **flags: bool) -> Dict[str, Dict[str, Any]]:
    for _, _, m, s in seats:
        data.need(m, split, s)
    aggs = {d: Aggregator(reliability=reliability(ledger, d), correlation=lambda a, b: rho.get((a, b)), mode=mode,
                          tau=tau, min_support=MIN_SUPPORT, **flags) for d in DOMAINS}
    out = {}
    for t, d in data.tasks[split].items():
        votes = [Vote(label, persona, answer_of(r), verification_of(r)) for label, persona, m, s in seats
                 for r in [data.row(m, split, t, s)]]
        dec = aggs[d].decide(votes, choices=CHOICES[d])
        ans = dec.answer
        out[t] = {"answer": ans, "correct": ans is not None and data.truth.get((t, ans)) is True,
                  "conf": None if ans is None else dec.posterior[ans], "support": dec.support_n_eff}
    return out


# ---------------------------------------------------------------- comparisons
def accuracy(arm: Dict[str, Dict[str, Any]], tasks: Dict[str, str]) -> Dict[str, Any]:
    out = {}
    for name, ds in [*[(d, (d,)) for d in DOMAINS], ("all", DOMAINS)]:
        ids = [t for t, d in tasks.items() if d in ds and t in arm]
        k = sum(arm[t]["correct"] for t in ids)
        answered = [t for t in ids if arm[t]["answer"] is not None]
        ka = sum(arm[t]["correct"] for t in answered)
        out[name] = {"k": k, "n": len(ids), "acc": k / len(ids) if ids else None, "ci": wilson(k, len(ids)),
                     "no_answer": len(ids) - len(answered), "acc_answered": ka / len(answered) if answered else None}
    return out


def paired(a: Dict[str, Dict[str, Any]], b: Dict[str, Dict[str, Any]], tasks: Dict[str, str]) -> Dict[str, Any]:
    rows = {}
    for d in DOMAINS:
        ids = [t for t, dom in tasks.items() if dom == d and t in a and t in b]
        n11 = sum(a[t]["correct"] and b[t]["correct"] for t in ids)
        n10 = sum(a[t]["correct"] and not b[t]["correct"] for t in ids)
        n01 = sum(not a[t]["correct"] and b[t]["correct"] for t in ids)
        n00 = len(ids) - n11 - n10 - n01
        if not ids:
            rows[d] = {"n": 0}
            continue
        diff, lo, hi = newcombe_paired(n11, n10, n01, n00)
        rows[d] = {"n": len(ids), "acc_a": (n11 + n10) / len(ids), "acc_b": (n11 + n01) / len(ids), "diff": diff,
                   "a_only": n10, "b_only": n01, "p": mcnemar_exact(n10, n01), "ci": [lo, hi]}
    live = [d for d in DOMAINS if rows[d].get("n")]
    for d, adj in zip(live, holm([rows[d]["p"] for d in live])):
        rows[d]["p_holm"] = adj
        rows[d]["win"] = adj < 0.05 and rows[d]["ci"][0] > 0
        rows[d]["statement"] = ("colony wins" if rows[d]["win"] else
                                f"no gain above 5 points (upper bound {rows[d]['ci'][1]:+.3f})" if rows[d]["ci"][1] < 0.05
                                else "not detected at this sample size")
    return {"domains": rows, "any_win": any(rows[d].get("win") for d in live)}


# ------------------------------------------------------------------- the run
def attempt(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except NotRun as exc:
        return {"status": "not run", "reason": str(exc)}


def best_member(data: Data, members: Sequence[str]) -> Dict[str, Any]:
    scores = {}
    for m in members:
        scores[m] = accuracy(solo(data, m, "development", 3), data.tasks["development"])["all"]["acc"]
    best = max(members, key=lambda m: (scores[m], -members.index(m)))
    return {"best": best, "dev_solo3_accuracy": scores}


def analyze(data: Data, w2_used: Sequence[str], gpu: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ev, dev = data.tasks["evaluation"], data.tasks["development"]
    ledger = warm_ledger(data)
    res: Dict[str, Any] = {"meta": {"eval_tasks": len(ev), "dev_tasks": len(dev),
                                    "cells": dict(Counter(f"{m}-{s}" for m, s, _, _ in data.cells)),
                                    "w2_used_eval_tasks": len(w2_used)}, "arms": {}, "gpu": gpu}
    arms: Dict[str, Dict[str, Dict[str, Any]]] = {}
    seatsets: Dict[str, Seats] = {}

    def add(name: str, builder: Callable[[], Dict], seats: Seats) -> None:
        seatsets[name] = seats
        out = attempt(builder)
        if "status" in out and out["status"] == "not run":
            res["arms"][name] = out
        else:
            arms[name] = out
            res["arms"][name] = {"status": "ok", "accuracy": accuracy(out, ev)}

    for m in ALL_MODELS:
        for k in (1, 3):
            add(f"solo{k}[{m}]", lambda m=m, k=k: solo(data, m, "evaluation", k), [(m, m, m, s) for s in range(1, k + 1)])
    bests: Dict[str, Any] = {}
    for cname, members in MEMBERS.items():
        bests[cname] = attempt(lambda members=members: best_member(data, members))
    res["best_members"] = bests
    first = lambda ms: [(m, m, m, 1) for m in ms]  # noqa: E731
    rhos: Dict[str, Dict] = {}
    for cname, members in MEMBERS.items():
        seats = first(members)
        rho = attempt(lambda seats=seats: dev_rho(data, seats))
        if isinstance(rho, dict) and "status" in rho:
            for n in (cname, f"{cname}_cold", f"{cname}_abstain"):
                res["arms"][n] = rho
            continue
        rhos[cname] = rho
        add(cname, lambda seats=seats, rho=rho: colony(data, seats, ledger, rho), seats)
        add(f"{cname}_cold", lambda seats=seats, rho=rho: colony(data, seats, None, rho), seats)
        best = bests[cname].get("best")
        if best:
            copies = [(f"{best}#{s}", best, best, s) for s in (1, 2, 3)]
            crho = attempt(lambda copies=copies: dev_rho(data, copies))
            if "status" not in crho:
                add(f"{cname}_e_single_model", lambda copies=copies, crho=crho: colony(data, copies, ledger, crho), copies)
        for ab, flags in ABLATIONS.items():
            add(f"{cname}_{ab}", lambda seats=seats, rho=rho, flags=flags: colony(data, seats, ledger, rho, **flags), seats)
    # S7: with / without Gemma
    for name, members in (("colony_local_noG", ("qwen", "phi")), ("colony_haiku_withG", ("qwen", "phi", "gemma", "haiku"))):
        seats = first(members)
        rho = attempt(lambda seats=seats: dev_rho(data, seats))
        if "status" in rho:
            res["arms"][name] = rho
            continue
        rhos[name] = rho
        add(name, lambda seats=seats, rho=rho: colony(data, seats, ledger, rho), seats)
        b = attempt(lambda members=members: best_member(data, members))
        bests[name] = b
        if "best" in b:
            k = len(members)
            add(f"solo{k}[{b['best']}]", lambda b=b, k=k: solo(data, b["best"], "evaluation", k),
                [(b["best"], b["best"], b["best"], s) for s in range(1, k + 1)])

    # ---- P1 / P2 and S6 (untouched items)
    fresh = {t: d for t, d in ev.items() if t not in set(w2_used)}

    def comparison(cname: str, subset: Dict[str, str]) -> Dict[str, Any]:
        best = bests[cname].get("best")
        base = f"solo3[{best}]"
        if cname not in arms or best is None or base not in arms:
            return {"status": "not run", "reason": "colony or best-member baseline missing"}
        return {"status": "ok", "best_member": best, "baseline": base, **paired(arms[cname], arms[base], subset)}

    res["primary"] = {"P1": {"colony": "colony_local", **comparison("colony_local", ev)},
                      "P2": {"colony": "colony_haiku", **comparison("colony_haiku", ev)}}
    res["S6_untouched"] = {"items": len(fresh), "P1": comparison("colony_local", fresh), "P2": comparison("colony_haiku", fresh)}
    res["S5_cold_start"] = {}
    for c in MEMBERS:
        base = f"solo3[{bests[c].get('best')}]"
        if c in arms and f"{c}_cold" in arms and base in arms:
            res["S5_cold_start"][c] = {"vs_warm": paired(arms[f"{c}_cold"], arms[c], ev),
                                       "vs_best_solo3": paired(arms[f"{c}_cold"], arms[base], ev)}
        else:
            res["S5_cold_start"][c] = {"status": "not run"}
    res["S1_ablations"] = {c: {ab: {"accuracy": res["arms"][f"{c}_{ab}"]["accuracy"], "vs_full": paired(arms[f"{c}_{ab}"], arms[c], ev)}
                               for ab in [*ABLATIONS, "e_single_model"] if f"{c}_{ab}" in arms}
                           for c in MEMBERS if c in arms}
    res["S7_gemma"] = {}
    for name, others in (("colony_local_noG", 2), ("colony_haiku_withG", 4)):
        best = (bests.get(name) or {}).get("best")
        base = f"solo{others}[{best}]"
        res["S7_gemma"][name] = ({"status": "not run"} if name not in arms or base not in arms else
                                 {"status": "ok", "baseline": base, **paired(arms[name], arms[base], ev)})

    # ---- S2 independence, dev vs eval rho
    res["S2_independence"] = {}
    for name in ("colony_local", "colony_haiku", "colony_haiku_withG"):
        members = MEMBERS.get(name, ALL_MODELS)
        try:
            for m in members:
                data.need(m, "evaluation", 1)
            err = {m: {t: int(not data.row(m, "evaluation", t, 1)["correct"]) for t in ev} for m in members}
            rep = independence(err, agents=list(members), min_overlap=20, prior=0.0, bootstrap=1000, seed=0).to_dict()
            dev_r = rhos.get(name, {})
            pairs = {f"{a}|{b}": {"dev": dev_r.get((a, b)), "eval": rep["rho"][a][b]} for a in members for b in members if a < b}
            res["S2_independence"][name] = {k: rep[k] for k in ("items", "error_rate", "n_eff", "n_eff_ci", "n_eff_rate_adjusted",
                                                                "n_eff_rate_adjusted_ci", "rho", "rho_adjusted", "flags")}
            res["S2_independence"][name]["dev_vs_eval_rho"] = pairs
        except NotRun as exc:
            res["S2_independence"][name] = {"status": "not run", "reason": str(exc)}

    # ---- S3 abstain, S4 calibration
    res["S3_abstain"], res["S4_calibration"] = {}, {}
    for c, rho in rhos.items():
        if c not in MEMBERS or c not in arms:
            continue
        seats = seatsets[c]
        curve = []
        for tau in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]:
            out = colony(data, seats, ledger, rho, mode=ABSTAIN, tau=tau)
            curve.append({"tau": tau, **_coverage(out, ev)})
        res["S3_abstain"][c] = {"headline": _coverage(colony(data, seats, ledger, rho, mode=ABSTAIN), ev),
                                "tau": TAU, "min_support": MIN_SUPPORT, "risk_coverage": curve}
        base = f"solo3[{bests[c].get('best')}]"
        res["S4_calibration"][c] = {"colony": ece_brier([(v["conf"], v["correct"]) for v in arms[c].values() if v["answer"]]),
                                    "solo3_vote_share": ece_brier([(v["conf"], v["correct"]) for v in arms[base].values() if v["answer"]])
                                    if base in arms else {"status": "not run"}}

    # ---- reputation weights (warm-up) for the explained-null checklist
    res["warmup"] = {m: {d: _weight(ledger, m, d) for d in DOMAINS} for m in ALL_MODELS
                     if all((m, "development", t, 1) in data.cells for t in dev) and dev}
    res["S8_verification"] = _verification(data)
    res["format_failures"] = _format(data)
    res["S9_cost"] = {n: _cost(data, s) for n, s in seatsets.items() if n in arms}
    res["explained_null"] = _checklist(res)
    return res


def _coverage(out: Dict, tasks: Dict[str, str]) -> Dict[str, Any]:
    res = {}
    for name, ds in [*[(d, (d,)) for d in DOMAINS], ("all", DOMAINS)]:
        ids = [t for t, d in tasks.items() if d in ds]
        got = [t for t in ids if out[t]["answer"] is not None]
        k = sum(out[t]["correct"] for t in got)
        res[name] = {"coverage": len(got) / len(ids) if ids else None, "answered": len(got), "n": len(ids),
                     "selective_accuracy": k / len(got) if got else None, "ci": wilson(k, len(got))}
    return res


def _weight(ledger: ReputationLedger, m: str, d: str) -> Dict[str, float]:
    p = ledger.accuracy(m, d, chance=CHANCE[d])
    k = round(1 / CHANCE[d])
    return {"posterior_accuracy": p, "weight": min(4.0, max(0.0, math.log((k - 1) * p / (1 - p)))), "n": ledger.standing(m, d, chance=CHANCE[d]).n}


def _verification(data: Data) -> Dict[str, Any]:
    health: Dict[str, Any] = {}
    acc: Dict[str, Dict[str, List[int]]] = {}
    for (m, split, t, s), r in data.cells.items():
        status = "no_claim" if r["answer"] is None else verification_of(r)
        health.setdefault(m, {}).setdefault(r["domain"], Counter())[status] += 1
        if r["answer"] is not None:
            for key in (m, "all"):
                a = acc.setdefault(key, {}).setdefault(status, [0, 0])
                a[0] += bool(r["correct"])
                a[1] += 1
    return {"counts": {m: {d: dict(c) for d, c in v.items()} for m, v in health.items()},
            "accuracy_by_status": {m: {s: {"k": k, "n": n, "acc": k / n, "ci": wilson(k, n)} for s, (k, n) in v.items()}
                                   for m, v in acc.items()},
            "note": "verification checks grounding, not correctness"}


def _format(data: Data) -> Dict[str, Any]:
    c: Dict[str, Counter] = {}
    for (m, split, _, _), r in data.cells.items():
        key = f"{m}|{split}|{r['domain']}"
        c.setdefault(key, Counter())["cells"] += 1
        c[key]["format_failures"] += bool(r["format_failure"])
        c[key]["provider_errors"] += r["status"] == "error"
        c[key]["truncated"] += bool(r.get("truncated"))
    return {k: {**v, "rate": v["format_failures"] / v["cells"]} for k, v in sorted(c.items())}


def _cost(data: Data, seats: Seats) -> Dict[str, Any]:
    rows = [data.row(m, "evaluation", t, s)["usage"] for _, _, m, s in seats for t in data.tasks["evaluation"]]
    return {"calls": sum(u["calls"] for u in rows), "prompt_tokens": sum(u["prompt_tokens"] for u in rows),
            "completion_tokens": sum(u["completion_tokens"] for u in rows), "model_latency_s": round(sum(u["latency_s"] for u in rows), 1)}


def _checklist(res: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for c, members in MEMBERS.items():
        p = res["primary"]["P1" if c == "colony_local" else "P2"]
        s2, ver = res["S2_independence"].get(c, {}), res["S8_verification"]["accuracy_by_status"]
        if p.get("status") != "ok" or "n_eff_rate_adjusted" not in s2:
            out[c] = {"status": "not run"}
            continue
        shifts = [abs(v["dev"] - v["eval"]) for v in s2["dev_vs_eval_rho"].values() if v["dev"] is not None and v["eval"] is not None]
        wts = {m: sum(res["warmup"][m][d]["weight"] for d in DOMAINS) / 2 for m in members if m in res["warmup"]}
        vv, uu = [ver.get("all", {}).get(s) for s in ("verified", "unverified")]
        out[c] = {"colony_won_somewhere": p["any_win"],
                  "seats_not_independent": {"n_eff_rate_adjusted": s2["n_eff_rate_adjusted"], "flag": s2["n_eff_rate_adjusted"] < 1.5},
                  "weak_members_near_zero_weight": {"mean_weights": wts, "flag": [m for m, w in wts.items() if w < NEAR_ZERO_WEIGHT]},
                  "verification_no_signal": {"verified": vv, "unverified": uu,
                                             "flag": bool(vv and uu and vv["ci"][0] <= uu["ci"][1] and uu["ci"][0] <= vv["ci"][1])},
                  "dev_rho_did_not_transfer": {"max_abs_shift": max(shifts) if shifts else None,
                                               "flag": bool(shifts and max(shifts) > RHO_SHIFT)}}
    return out


# ------------------------------------------------------------------- report
def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _ci(ci: Optional[Sequence[float]]) -> str:
    return "n/a" if not ci else f"{100 * ci[0]:.1f}-{100 * ci[1]:.1f}%"


def render(res: Dict[str, Any]) -> str:
    L: List[str] = ["# Colony v2 results", "",
                    "Generated from `results.json`; every number below is read from it. Spec: `PREREGISTRATION.md`.",
                    f"Evaluation items: {res['meta']['eval_tasks']}; development items: {res['meta']['dev_tasks']}.", ""]

    def table(head: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        L.extend(["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *["| " + " | ".join(map(str, r)) + " |" for r in rows], ""])

    L += ["## Headline (P1 and P2)", "",
          "Does the mixed colony answer more questions correctly than its best member given the same number of calls? "
          "Paired by item, exact McNemar test, Holm-corrected over the two domains, with a Newcombe 95% interval for the gain.", ""]
    for key, p in res["primary"].items():
        L.append(f"**{key}: {p['colony']}**" + (f" against {p.get('baseline')} (best member chosen on development data)" if p.get("status") == "ok" else ""))
        L.append("")
        if p.get("status") != "ok":
            L += [f"Not run: {p.get('reason')}", ""]
            continue
        table(["Domain", "Items", "Colony", "Best member", "Gain", "95% interval", "Colony-only right", "Member-only right", "Holm p", "Result"],
              [[d, r["n"], _pct(r["acc_a"]), _pct(r["acc_b"]), f"{100 * r['diff']:+.1f} pts", f"{100 * r['ci'][0]:+.1f} to {100 * r['ci'][1]:+.1f}",
                r["a_only"], r["b_only"], f"{r['p_holm']:.3f}", r["statement"]] for d, r in p["domains"].items() if r.get("n")])
    L += ["## All arms (evaluation split)", ""]
    ok = {n: a for n, a in res["arms"].items() if a.get("status") == "ok"}
    table(["Arm", "Medical", "Finance", "Both", "No answer"], [[n, *[f"{_pct(a['accuracy'][d]['acc'])} ({_ci(a['accuracy'][d]['ci'])})" for d in ("medical", "finance", "all")],
                                                           a["accuracy"]["all"]["no_answer"]] for n, a in sorted(ok.items())])
    nr = [f"`{n}`: {a.get('reason')}" for n, a in res["arms"].items() if a.get("status") != "ok"]
    if nr:
        L += ["Not run:", *[f"- {x}" for x in nr], ""]
    L += ["Strict scoring: a failed or cut-off reply counts as wrong. Accuracy among answered items is in `results.json` (`acc_answered`).", "",
          "## Secondary results", "", "### S1 ablations (accuracy, both domains; difference counts against the full colony)", ""]
    for c, abl in res["S1_ablations"].items():
        table(["Variant", "Accuracy", "Full-only right (medical/finance)", "Variant-only right (medical/finance)"],
              [[f"{c}_{n}", _pct(a["accuracy"]["all"]["acc"]), "/".join(str(a["vs_full"]["domains"][d].get("b_only")) for d in DOMAINS),
                "/".join(str(a["vs_full"]["domains"][d].get("a_only")) for d in DOMAINS)] for n, a in abl.items()])
    L += ["### S2 independence (evaluation errors, one sample per member)", ""]
    table(["Colony", "Effective independent members (raw)", "Rate-adjusted (headline)", "95% interval", "Error rates"],
          [[c, f"{s['n_eff']:.2f}" if isinstance(s.get("n_eff"), (int, float)) else s.get("n_eff", "not run"),
            f"{s['n_eff_rate_adjusted']:.2f}" if "n_eff_rate_adjusted" in s else "n/a", s.get("n_eff_rate_adjusted_ci") or "n/a", s.get("error_rate", "")]
           for c, s in res["S2_independence"].items()])
    L += ["### S3 abstain mode (tau 0.6, min support 1.0)", ""]
    table(["Colony", "Domain", "Coverage", "Accuracy when answering", "95% interval"],
          [[c, d, _pct(v[d]["coverage"]), _pct(v[d]["selective_accuracy"]), _ci(v[d]["ci"])] for c, s in res["S3_abstain"].items() for v in [s["headline"]] for d in (*DOMAINS, "all")])
    L += ["Risk-coverage points (both domains), by confidence threshold:", ""]
    table(["Colony", "tau", "Coverage", "Accuracy when answering"],
          [[c, pt["tau"], _pct(pt["all"]["coverage"]), _pct(pt["all"]["selective_accuracy"])] for c, s in res["S3_abstain"].items() for pt in s["risk_coverage"]])
    L += ["### S4 calibration (10 bins; lower is better)", ""]
    table(["Colony", "Colony ECE", "Colony Brier", "Self-consistency ECE", "Self-consistency Brier"],
          [[c, v["colony"]["ece"], v["colony"]["brier"], v["solo3_vote_share"].get("ece", "not run"), v["solo3_vote_share"].get("brier", "not run")] for c, v in res["S4_calibration"].items()])
    L += ["### S5 cold start (no warm-up) against the warm colony and the best member", ""]
    table(["Colony", "Domain", "Cold vs warm gain", "Cold vs best-member gain", "Holm p (vs best)"],
          [[c, d, f"{100 * v['vs_warm']['domains'][d]['diff']:+.1f} pts", f"{100 * v['vs_best_solo3']['domains'][d]['diff']:+.1f} pts",
            f"{v['vs_best_solo3']['domains'][d]['p_holm']:.3f}"] for c, v in res["S5_cold_start"].items() if "vs_warm" in v for d in DOMAINS if v["vs_warm"]["domains"][d].get("n")])
    L += ["### S6 the 40 evaluation items W2 never used", ""]
    table(["Test", "Domain", "Items", "Gain", "95% interval", "Holm p", "Result"],
          [[k, d, r["n"], f"{100 * r['diff']:+.1f} pts", f"{100 * r['ci'][0]:+.1f} to {100 * r['ci'][1]:+.1f}", f"{r['p_holm']:.3f}", r["statement"]]
           for k in ("P1", "P2") for p in [res["S6_untouched"][k]] if p.get("status") == "ok" for d, r in p["domains"].items() if r.get("n")])
    L += ["### S7 with and without Gemma (against the matched-call best member)", ""]
    table(["Colony", "Baseline", "Domain", "Gain", "95% interval", "Holm p", "Result"],
          [[c, v["baseline"], d, f"{100 * r['diff']:+.1f} pts", f"{100 * r['ci'][0]:+.1f} to {100 * r['ci'][1]:+.1f}", f"{r['p_holm']:.3f}", r["statement"]]
           for c, v in res["S7_gemma"].items() if v.get("status") == "ok" for d, r in v["domains"].items() if r.get("n")])
    L += ["### S8 verification health", "", "Verification checks that claims are grounded in the cited passage. It is not accuracy.", ""]
    table(["Model", "Status", "Answers", "Correct", "Accuracy (95% interval)"],
          [[m, s, v["n"], v["k"], f"{_pct(v['acc'])} ({_ci(v['ci'])})"] for m, d in res["S8_verification"]["accuracy_by_status"].items() for s, v in sorted(d.items())])
    L += ["### S9 cost (evaluation split)", ""]
    table(["Arm", "Calls", "Prompt tokens", "Completion tokens", "Summed model latency (s)"],
          [[n, c["calls"], c["prompt_tokens"], c["completion_tokens"], c["model_latency_s"]] for n, c in sorted(res["S9_cost"].items())])
    L += [f"GPU time and dollars: {res['gpu'] or 'not recorded (pass --gpu-hours and --gpu-usd from the pod `down` output)'}", "",
          "## Explained-null checklist (section 9)", "", "Applies when a colony does not win. Thresholds for 'near 0' and 'about equal' are this report's proposals.", ""]
    for c, v in res["explained_null"].items():
        if v.get("status") == "not run":
            L += [f"- `{c}`: not run", ""]
            continue
        L += [f"**{c}** (won in some domain: {v['colony_won_somewhere']})", "",
              f"- Seats not independent (rate-adjusted effective members {v['seats_not_independent']['n_eff_rate_adjusted']:.2f}, flag below 1.5): {v['seats_not_independent']['flag']}",
              f"- Weak members with weight near 0 (mean warm-up weights {v['weak_members_near_zero_weight']['mean_weights']}): {v['weak_members_near_zero_weight']['flag'] or 'none'}",
              f"- Verification did not separate good from bad (verified vs unverified accuracy intervals overlap): {v['verification_no_signal']['flag']}",
              f"- Development correlation did not transfer (largest dev-to-eval shift {v['dev_rho_did_not_transfer']['max_abs_shift']}): {v['dev_rho_did_not_transfer']['flag']}", ""]
    L += ["## Deviations", "", "None recorded by the analysis. Add any departure from the preregistration here.", ""]
    return "\n".join(L)


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cells-dir", default=str(EXP / "cells"))
    p.add_argument("--out-dir", default=str(EXP))
    p.add_argument("--w2-file", default=str(EXP / "w2-used-eval-tasks.json"))
    p.add_argument("--gpu-hours", type=float), p.add_argument("--gpu-usd", type=float)
    p.add_argument("--print-best", action="store_true", help="print the dev-chosen best member per colony and exit")
    args = p.parse_args(argv)
    data = Data.load(Path(args.cells_dir))
    if args.print_best:
        print(json.dumps({c: attempt(lambda m=m: best_member(data, m)) for c, m in MEMBERS.items()}, indent=1))
        return {}
    gpu = None if args.gpu_hours is None else {"hours": args.gpu_hours, "usd": args.gpu_usd}
    res = analyze(data, json.loads(Path(args.w2_file).read_text())["task_ids"], gpu)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    (out / "REPORT.md").write_text(render(json.loads((out / "results.json").read_text())) + "\n")
    print(f"wrote {out / 'results.json'} and REPORT.md")
    return res


if __name__ == "__main__":
    main()
