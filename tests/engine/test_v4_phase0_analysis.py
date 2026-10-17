import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "v4_phase0_analysis", Path(__file__).resolve().parents[2] / "scripts" / "v4_phase0_analysis.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def noul(i, backend, p, label, world="foraging_sb", lat=1.0, error=None):
    if error:
        return {"id": f"n{i}", "backend": backend, "world": world, "kind": "judgement", "type": "noul",
                "error": error, "latency_s": lat}
    return {"id": f"n{i}", "backend": backend, "world": world, "kind": "judgement", "type": "noul", "prob": p,
            "label": label, "correct": (p >= 0.5) == label, "answer": p, "latency_s": lat,
            "probabilities": {"yes": p, "no": 1 - p}}


def choice(i, backend, probs, accept, world="graph_coloring", lat=1.0):
    ans = max(probs, key=probs.get)
    return {"id": f"c{i}", "backend": backend, "world": world, "kind": "move", "type": "choice", "answer": ans,
            "accept": accept, "prob": sum(probs[o] for o in accept), "label": ans in accept,
            "correct": ans in accept, "probabilities": probs, "latency_s": lat}


def synthetic():
    dm = [noul(0, "jev", 0.95, True), noul(1, "jev", 0.5, True), noul(2, "jev", 0.6, False),
          noul(3, "jev", 0.05, False), choice(0, "jev", {"a": 0.9, "b": 0.1}, ["a"]),
          choice(1, "jev", {"a": 0.4, "b": 0.35, "c": 0.25}, ["b"], lat=2.0)]
    slm = [noul(0, "q", 0.9, True, lat=3.0), noul(1, "q", 0.9, True, lat=3.0), noul(2, "q", 0.1, False, lat=3.0),
           noul(3, "q", 0.0, False, error="boom", lat=5.0),
           choice(0, "q", {"a": 1.0, "b": 0.0}, ["a"], lat=3.0), choice(1, "q", {"a": 0.0, "b": 1.0, "c": 0.0}, ["b"])]
    return {"jev": dm, "qwen3.5-9b": slm}


def test_chance_majority_and_option_share():
    rows = [noul(i, "x", 0.9, i < 3) for i in range(4)] + [choice(0, "x", {"a": 0.5, "b": 0.3, "c": 0.2}, ["a"])]
    c = a.chance(rows)
    assert c["judgement"] == 0.75 and c["move"] == pytest.approx(1 / 3)
    assert c["all"] == pytest.approx((0.75 * 4 + 1 / 3) / 5)


def test_cell_stats_counts_errors_and_scores_the_rest():
    rows = [noul(0, "q", 0.9, True), noul(1, "q", 0.2, True), noul(2, "q", 0, False, error="boom")]
    s = a.cell_stats(rows, "judgement")
    assert (s["n"], s["scored"], s["errors"]) == (3, 2, 1)
    assert s["accuracy"] == 0.5 and s["brier"] == pytest.approx((0.01 + 0.64) / 2)


def test_noul_boundaries_are_confident_and_choice_uses_max_probability():
    assert a.uncertain(noul(0, "x", 0.8, True), (0.2, 0.8)) is False
    assert a.uncertain(noul(0, "x", 0.5, True), (0.2, 0.8)) is True
    assert a.uncertain(noul(0, "x", 0.5, True), None) is False
    row = choice(0, "x", {"a": 0.4, "b": 0.6}, ["a"])
    assert a.confidence(row) == 0.6
    assert a.uncertain(row, 0.7) and not a.uncertain(row, 0.6)


def test_combine_uses_slm_when_escalated_and_keeps_dm_on_slm_error():
    d = synthetic()
    slm = {r["id"]: r for r in d["qwen3.5-9b"]}
    dm_noul = [r for r in d["jev"] if r["type"] == "noul"]
    base = a.combine(dm_noul, slm, None)
    assert base["correct"] == 3 and base["escalated"] == 0  # n2 (0.6, false) is wrong
    c = a.combine(dm_noul, slm, (0.1, 0.9))  # n1 and n2 escalate; both Qwen answers are right
    assert (c["escalated"], c["correct"], c["n"]) == (2, 4, 4)
    err = a.combine([noul(3, "jev", 0.5, False)], slm, (0.1, 0.9))  # Qwen errored on n3 -> dm answer kept
    assert err["escalated"] == 1 and err["slm_errors_on_escalated"] == 1 and err["correct"] == 0
    assert err["latency_mean_s"] == pytest.approx(1.0 + 5.0)  # the failed Qwen call still cost time
    assert c["escalated_subset"]["dm_accuracy"] == 0.5 and c["escalated_subset"]["slm_accuracy"] == 1.0


def test_propose_respects_rate_cap_and_tie_breaks_low_rate():
    cells = [{"setting": "a", "correct": 9, "escalation_rate": 0.9, "brier": 0.1, "n": 10, "accuracy": 0.9},
             {"setting": "b", "correct": 8, "escalation_rate": 0.4, "brier": 0.2, "n": 10, "accuracy": 0.8},
             {"setting": "c", "correct": 8, "escalation_rate": 0.2, "brier": 0.3, "n": 10, "accuracy": 0.8},
             {"setting": "none", "correct": 5, "escalation_rate": 0.0, "brier": 0.4, "n": 10, "accuracy": 0.5}]
    p = a.propose(cells, "b")
    assert p["setting"] == "c" and p["best_unconstrained"]["setting"] == "a"
    assert p["items_gained_vs_none"] == 3 and p["items_gained_vs_goal_default"] == 0


def test_end_to_end_is_deterministic_and_has_no_item_rows(tmp_path):
    d = synthetic()
    d["laya"], d["deepseek"] = d["jev"], d["qwen3.5-9b"]
    rows = tmp_path / "rows"
    rows.mkdir()
    for b, r in d.items():
        (rows / f"{b}.jsonl").write_text("\n".join(json.dumps(x) for x in r))
    for out in ("o1", "o2"):
        a.main(["--rows", str(rows), "--out", str(tmp_path / out)])
    for name in ("phase0-summary.json", "phase0-summary.md"):
        assert (tmp_path / "o1" / name).read_text() == (tmp_path / "o2" / name).read_text()
    text = (tmp_path / "o1" / "phase0-summary.json").read_text()
    assert '"n0"' not in text and "c0" not in text
    summary = json.loads(text)
    assert summary["calibration"]["jev"]["both"]["all"]["n"] == 6
