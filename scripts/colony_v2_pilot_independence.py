"""Colony v2 pilot: how independent were Sprint 1's agents? (offline, no model calls)

Reads the stored W2 cells (docs/research/slm-vs-frontier-20261008/cells, PR #9)
and measures error independence with ``antelligence.kernel.independence``:

* within one model: the 3 voters of ``independent_vote`` (temperature 0.7);
* across models: one ``single`` answer per model on the same (task, seed).

An error is a wrong or abstained final answer under W2's strict scorer; cells
that were invalid or errored are left out of the within-model view (their
per-agent answers are unreliable) and count as errors in the cross-model view
(as in W2's strict accuracy). Writes ``pilot-independence.json``.

    uv run python scripts/colony_v2_pilot_independence.py [--cells DIR] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.kernel.independence import independence  # noqa: E402
from backend.swarm_core import _score_answer  # noqa: E402

DEFAULT_CELLS = ROOT / "docs/research/slm-vs-frontier-20261008/cells"
DEFAULT_OUT = ROOT / "docs/research/colony-v2-20261010/pilot-independence.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", default=str(DEFAULT_CELLS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    tasks = {t["task_id"]: t for t in json.loads((ROOT / "backend/research_fixtures/tasks.json").read_text())["tasks"]}

    def err(task_id: str, answer) -> int:
        return 1 if answer is None or not _score_answer(tasks[task_id], answer) else 0

    cells = {}
    for path in sorted(Path(args.cells).glob("*.jsonl")):
        if path.name.startswith("smoke"):
            continue
        for line in path.read_text().splitlines():
            cell = json.loads(line)
            if cell.get("world") == "research_qa":
                cells.setdefault(cell["model_key"], []).append(cell)

    out = {"source": "docs/research/slm-vs-frontier-20261008/cells (W2 benchmark data)",
           "error_definition": "wrong or abstained final answer, W2 strict scorer", "within_model": {},
           "cross_model": None}
    for model, rows in sorted(cells.items()):
        votes = [c for c in rows if c["arm"] == "independent_vote" and c["status"] in ("completed", "abstained")
                 and len(c["final_answers"]) == 3]
        errors = {f"voter{j + 1}": {f'{c["task_id"]}#s{c["seed"]}': err(c["task_id"], c["final_answers"][j])
                                    for c in votes} for j in range(3)}
        out["within_model"][model] = independence(errors, bootstrap=1000, seed=0).to_dict()

    single = {m: {f'{c["task_id"]}#s{c["seed"]}': (err(c["task_id"], c["answer"])
                                                  if c["status"] in ("completed", "abstained") else 1)
                  for c in rows if c["arm"] == "single"} for m, rows in cells.items()}
    shared = set.intersection(*(set(v) for v in single.values()))
    cross = {m: {k: v for k, v in row.items() if k in shared} for m, row in single.items()}
    out["cross_model"] = independence(cross, bootstrap=1000, seed=0).to_dict()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    for model, rep in out["within_model"].items():
        print(f"within {model:20s} items={rep['items']:4d} n_eff={rep['n_eff']} ci={rep['n_eff_ci']} "
              f"rate_adjusted={rep['n_eff_rate_adjusted']}")
    rep = out["cross_model"]
    print(f"cross-model items={rep['items']} n_eff={rep['n_eff']} ci={rep['n_eff_ci']} "
          f"rate_adjusted={rep['n_eff_rate_adjusted']} ci={rep['n_eff_rate_adjusted_ci']}")


if __name__ == "__main__":
    main()
