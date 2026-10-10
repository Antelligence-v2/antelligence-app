#!/usr/bin/env python3
"""D2 sensitivity table: research_qa accuracy and truncation at max_tokens 512 (primary) vs 2048.

Only (model, seed) pairs that are COMPLETE in the 2048 run are compared, and the 512 side is
restricted to the same seeds, so a stopped lane (Qwen seed 2) is never counted as failures.
Writes sensitivity-maxtok2048/SENSITIVITY.md and sensitivity-table.csv. Offline, deterministic.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w2_analyze as A  # noqa: E402

PRIMARY = A.DEFAULT_OUT
SENS = PRIMARY / "sensitivity-maxtok2048"


def load(out: Path):
    A.OUT = out
    cells, _ = A.dedupe(A.load_cells())
    return cells, A.requested_from_runlog()


def main() -> None:
    p_cells, _ = load(PRIMARY)
    s_cells, s_req = load(SENS)
    complete = defaultdict(set)
    incomplete = defaultdict(set)
    for (m, w, d, arm, seed), ts in s_req.items():
        ok = all((m, w, d, arm, seed, t) in s_cells for t in ts)
        (complete if ok else incomplete)[m].add(seed)
    seeds = {}
    for m in complete:
        seeds[m] = sorted(complete[m] - incomplete[m])
    rows = []
    for (m, w, d, arm, seed), ts in sorted(s_req.items()):
        if seed not in seeds.get(m, []):
            continue
        for t in ts:
            rows.append((m, d, arm, seed, t))
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0])  # n, c512, c2048, trunc512, trunc2048, inv512, inv2048, abst
    for m, d, arm, seed, t in rows:
        a = p_cells.get((m, "research_qa", d, arm, seed, t))
        b = s_cells[(m, "research_qa", d, arm, seed, t)]
        g = agg[(m, d, arm)]
        g[0] += 1
        g[1] += bool(a and a["correct"])
        g[2] += bool(b["correct"])
        g[3] += bool(a and a["status"] == "error")
        g[4] += b["status"] == "error"
        g[5] += bool(a and a["status"] == "invalid")
        g[6] += b["status"] == "invalid"
    out = []
    for (m, d, arm), g in sorted(agg.items()):
        n = g[0]
        out.append({"model": m, "seeds": ",".join(map(str, seeds[m])), "domain": d, "arm": arm, "cells": n,
                    "acc_512": round(g[1] / n, 3), "acc_2048": round(g[2] / n, 3), "delta": round((g[2] - g[1]) / n, 3),
                    "truncated_512": g[3], "truncated_2048": g[4], "invalid_512": g[5], "invalid_2048": g[6]})
    with (SENS / "sensitivity-table.csv").open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    L = ["# D2 sensitivity: max_tokens 512 (preregistered) vs 2048", "",
         "Same tasks, same seeds on both sides. Only (model, seed) pairs fully completed in the 2048 run are compared: "
         + "; ".join(f"`{m}` seeds {s}" for m, s in sorted(seeds.items()))
         + ". Qwen seed 2 was stopped by the operator part-way (452/540 cells written) and is excluded here; "
         "the automatic `REPORT.md`/`results.csv` in this directory count its unwritten cells as failures, so use this file for Qwen.",
         "", "Truncated = cell ended in status `error` (a call hit the token cap). Accuracy = correct / cells.", "",
         "| Model | Seeds | Domain | Arm | Cells | Acc 512 | Acc 2048 | Δ | Trunc 512 | Trunc 2048 | Invalid 512 | Invalid 2048 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in out:
        L.append(f"| {r['model']} | {r['seeds']} | {r['domain']} | {r['arm']} | {r['cells']} | {r['acc_512']:.1%} | "
                 f"{r['acc_2048']:.1%} | {r['delta']:+.1%} | {r['truncated_512']} | {r['truncated_2048']} | "
                 f"{r['invalid_512']} | {r['invalid_2048']} |")
    (SENS / "SENSITIVITY.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
