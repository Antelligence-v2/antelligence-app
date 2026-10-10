#!/usr/bin/env python3
"""W2 deviation D3: EXPLORATORY lenient offline re-score of stored research_qa responses.

Post hoc and NOT confirmatory; the preregistered strict analysis (w2_analyze.py) stays primary.
No model is called: every stored raw response (``raw/<model>-research_qa.jsonl``) is replayed
through the real engine (QAPolicy + ResearchQAWorld) with a lenient reply parser:

  (a) take the LAST balanced JSON object in the reply (prose before/after is ignored), ignore extra
      fields, treat the string answer "null"/"none" as abstain, and accept a missing ``evidence_ids``
      on an abstention (-> []).
  (b) evidence_isolated is also scored by PLURALITY of the non-null agent answers (ties -> no answer)
      alongside the engine's strict majority.
  (c) the two scale-ambiguous FinQA items are flagged; every count is also reported without them.

Cells whose physical call was truncated / never cached (no stored response for that agent+round)
stay failures. If a lenient parse changes what a LATER round's prompt looks like, that prompt's hash
was never cached; the response the model gave in that same (agent, round) slot in the original run is
reused (counted in ``fallback_cells``). This isolates the parsing effect; it is an approximation.

Writes <OUT>/exploratory-lenient.csv (summary) and exploratory-lenient-cells.csv (per cell).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCALE_AMBIGUOUS = ("finqa:JPM/2008/page_117.pdf-2", "finqa:AWK/2012/page_117.pdf-1")
DEFAULT_OUT = ROOT / "docs/research/slm-vs-frontier-20261008"
NULL_STRINGS = {"null", "none"}


def last_json_object(content: str) -> Optional[dict]:
    """Last top-level JSON object in ``content`` (prefers one that has an ``answer`` key)."""
    if not isinstance(content, str):
        return None
    dec = json.JSONDecoder()
    found: List[dict] = []
    i = 0
    while True:
        i = content.find("{", i)
        if i < 0:
            break
        try:
            obj, end = dec.raw_decode(content, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = end
    with_answer = [o for o in found if "answer" in o]
    pool = with_answer or found
    return pool[-1] if pool else None


def lenient_payload(content: str) -> Optional[Dict[str, Any]]:
    """Normalise a reply to the exact {answer, evidence_ids, brief} contract, or None if unrecoverable."""
    obj = last_json_object(content)
    if obj is None or "answer" not in obj:
        return None
    answer = obj["answer"]
    if isinstance(answer, str) and answer.strip().lower() in NULL_STRINGS:
        answer = None
    if answer is not None and not isinstance(answer, str):
        return None
    evidence_ids = obj.get("evidence_ids")
    if evidence_ids is None and "evidence_ids" not in obj and answer is None:
        evidence_ids = []
    brief = obj.get("brief")
    if "brief" not in obj:
        return None
    return {"answer": answer, "evidence_ids": evidence_ids, "brief": brief}


def plurality(task: Mapping[str, Any], answers: List[Optional[str]]) -> Optional[str]:
    from backend.swarm_core import _answer_key
    counts: Counter = Counter()
    rep: Dict[Any, str] = {}
    for a in answers:
        if a is None:
            continue
        k = _answer_key(task, a)
        counts[k] += 1
        rep.setdefault(k, a)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return rep[ranked[0][0]]


def set_parser(lenient: bool) -> None:
    import antelligence.worlds.research_qa.policies as pol
    import antelligence.worlds.research_qa.world as wld
    from backend.swarm_core import _PayloadError, _parse_answer as strict_parse
    if not lenient:
        pol._parse_answer = wld._parse_answer = strict_parse
        return

    def lenient_parse(content: str, task: Mapping[str, Any]) -> dict:
        payload = lenient_payload(content)
        if payload is None:
            raise _PayloadError("no recoverable JSON answer object")
        return strict_parse(json.dumps(payload), task)

    pol._parse_answer = lenient_parse
    wld._parse_answer = lenient_parse


async def run_cells(model_key: str, out: Path, modelid: str, strict_only: bool, slots: Dict[str, dict]):
    from antelligence.providers import ChatResponse, ProviderError
    from antelligence.worlds.research_qa import QAPolicy, build as qa_build

    raw: Dict[str, dict] = {}
    with (out / "raw" / f"{model_key}-research_qa.jsonl").open() as fh:
        for line in fh:
            r = json.loads(line)
            raw.setdefault(r["request_hash"], r)
    tasks = {t["task_id"]: t for t in json.loads((ROOT / "backend/research_fixtures/tasks.json").read_text())["tasks"]}

    class Provider:
        def __init__(self, cell_key):
            self.cell_key, self.fallback, self.slot_log = cell_key, 0, {}

        def describe(self):
            return {}

        async def complete(self, req):
            body = json.loads(req.messages[-1]["content"])
            slot = (body["agent_id"], body["round"])
            r = raw.get(req.request_hash)
            if r is not None:
                self.slot_log[slot] = r
            elif not strict_only and slot in slots.get(self.cell_key, {}):
                r, self.fallback = slots[self.cell_key][slot], self.fallback + 1
            if r is None:
                raise ProviderError("no stored response (truncated or never cached)")
            return ChatResponse(content=r["content"], model=r["model"], request_hash=req.request_hash,
                                prompt_tokens=r["prompt_tokens"], completion_tokens=r["completion_tokens"],
                                finish_reason=r["finish_reason"], response_id=r["response_id"], elapsed_s=0.0, extra={})

    rows = []
    with (out / "cells" / f"{model_key}.jsonl").open() as fh:
        for line in fh:
            c = json.loads(line)
            if c["world"] != "research_qa":
                continue
            key = (c["arm"], c["seed"], c["task_id"])
            task = tasks[c["task_id"]]
            prov = Provider(key)
            sched = qa_build(task, c["arm"], lambda a: QAPolicy(prov, modelid, temperature=0.7, max_tokens=512),
                             seed=c["seed"], run_id=c["run_id"])
            m = (await sched.arun()).metrics
            rows.append((c, key, m, prov, task))
    return rows


def write_comparisons(out: Path, cell_rows: List[dict]) -> None:
    """Lenient versions of the four preregistered comparisons (exploratory, uncorrected, sign test only)."""
    from antelligence.experiments.stats import sign_test_p
    ok = {(r["model"], r["arm"], r["seed"], r["task_id"]): r["lenient_correct"] for r in cell_rows}
    skip = set(SCALE_AMBIGUOUS)
    small, strong = "qwen38-27b-q3k", "claude-sonnet-5.5"
    specs = [("a1 small signal_board vs small single", small, "signal_board", small, "single"),
             ("a2 small evidence_exchange vs small single", small, "evidence_exchange", small, "single"),
             ("b1 small signal_board vs frontier-strong single", small, "signal_board", strong, "single"),
             ("b2 small evidence_exchange vs frontier-strong single", small, "evidence_exchange", strong, "single")]
    res = []
    for label, ma, aa, mb, ab in specs:
        for excl in (False, True):
            keys = [k for k in ok if k[:2] == (ma, aa) and (mb, ab, k[2], k[3]) in ok and not (excl and k[3] in skip)]
            va = [ok[k] for k in keys]
            vb = [ok[(mb, ab, k[2], k[3])] for k in keys]
            w = sum(x and not y for x, y in zip(va, vb))
            l = sum(y and not x for x, y in zip(va, vb))
            n = len(keys)
            res.append({"label": label, "scale_items": "excluded" if excl else "included", "pairs": n,
                        "treatment_acc": round(sum(va) / n, 4) if n else None,
                        "baseline_acc": round(sum(vb) / n, 4) if n else None, "treatment_wins": w,
                        "baseline_wins": l, "sign_test_p": sign_test_p(w, l) if w + l else None,
                        "note": "exploratory, post hoc, uncorrected; lenient scoring"})
    (out / "exploratory-lenient-comparisons.json").write_text(json.dumps(res, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out = Path(args.out_dir).resolve() if args.out_dir else DEFAULT_OUT
    from backend.swarm_core import _score_answer
    from backend.research_models import MODELS

    ids = {"claude-sonnet-5.5": "anthropic/claude-sonnet-5.5", "claude-haiku-5.5": "anthropic/claude-haiku-5.5",
           "qwen38-27b-q3k": MODELS["qwen"]["model_id"]}
    cell_rows, summary = [], defaultdict(Counter)
    for model_key, modelid in ids.items():
        if not (out / "cells" / f"{model_key}.jsonl").exists():
            continue
        # Pass 1 (engine's own strict parser): per-slot original responses + replay fidelity check.
        set_parser(False)
        strict = asyncio.run(run_cells(model_key, out, modelid, True, {}))
        slots = {key: dict(p.slot_log) for _, key, _, p, _ in strict}
        faithful = sum(m["status"] == c["status"] for c, _, m, _, _ in strict)
        print(f"{model_key}: strict replay matches stored status for {faithful}/{len(strict)} cells", file=sys.stderr)
        set_parser(True)
        lenient = asyncio.run(run_cells(model_key, out, modelid, False, slots))
        for (c, key, m, prov, task) in lenient:
            tid = c["task_id"]
            fin = m["final_answers"]
            plural_ok = None
            if c["arm"] == "evidence_isolated" and m["status"] in ("completed", "abstained"):
                plural_ok = bool(_score_answer(task, plurality(task, fin)))
            rec = {"model": model_key, "domain": c["domain"], "arm": c["arm"], "seed": c["seed"], "task_id": tid,
                   "scale_ambiguous": tid in SCALE_AMBIGUOUS, "strict_status": c["status"],
                   "strict_correct": bool(c["correct"]), "lenient_status": m["status"],
                   "lenient_correct": bool(m["correct"]), "lenient_plurality_correct": plural_ok,
                   "fallback_calls": prov.fallback}
            cell_rows.append(rec)
            for flag in ("all", "excl"):
                if flag == "excl" and rec["scale_ambiguous"]:
                    continue
                s = summary[(model_key, c["domain"], c["arm"], flag)]
                s["n"] += 1
                s["strict_correct"] += rec["strict_correct"]
                s["lenient_correct"] += rec["lenient_correct"]
                s["plurality_correct"] += bool(plural_ok)
                s[f"lenient_{m['status']}"] += 1
                s["fallback_cells"] += prov.fallback > 0
    with (out / "exploratory-lenient-cells.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(cell_rows[0]))
        w.writeheader()
        w.writerows(cell_rows)
    fields = ["model", "domain", "arm", "scale_items", "n", "strict_correct", "strict_acc", "lenient_correct",
              "lenient_acc", "plurality_correct", "plurality_acc", "lenient_completed", "lenient_abstained",
              "lenient_invalid", "lenient_error", "fallback_cells"]
    with (out / "exploratory-lenient.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        for (model, domain, arm, flag), s in sorted(summary.items()):
            n = s["n"]
            plural = arm == "evidence_isolated"
            w.writerow({"model": model, "domain": domain, "arm": arm,
                        "scale_items": "included" if flag == "all" else "excluded", "n": n,
                        "strict_correct": s["strict_correct"], "strict_acc": round(s["strict_correct"] / n, 4),
                        "lenient_correct": s["lenient_correct"], "lenient_acc": round(s["lenient_correct"] / n, 4),
                        "plurality_correct": s["plurality_correct"] if plural else "",
                        "plurality_acc": round(s["plurality_correct"] / n, 4) if plural else "",
                        "lenient_completed": s["lenient_completed"], "lenient_abstained": s["lenient_abstained"],
                        "lenient_invalid": s["lenient_invalid"], "lenient_error": s["lenient_error"],
                        "fallback_cells": s["fallback_cells"]})
    write_comparisons(out, cell_rows)
    print(f"wrote {len(cell_rows)} cells")


if __name__ == "__main__":
    main()
