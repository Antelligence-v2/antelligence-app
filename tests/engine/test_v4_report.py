"""Tests for v4_report.py against the synthetic results.json fixture."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import v4_report  # noqa: E402

FIXTURE = HERE / "fixtures" / "v4_report" / "results_synthetic.json"


@pytest.fixture(scope="module")
def results():
    return json.loads(FIXTURE.read_text())


def json_numbers(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            json_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            json_numbers(v, out)
    return out


def in_json(token: str, pool) -> bool:
    nd = len(token.split(".")[1]) if "." in token else 0
    value = float(token)
    return any(abs(round(p, nd) - value) < 1e-9 for p in pool)


def test_every_number_traces_to_json(results):
    md = v4_report.render(results)
    pool = json_numbers(results)
    bad = []
    for line in md.splitlines():
        if line.startswith("| Comparison"):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")][1:]  # first column is the arm / label
            tokens = [t for c in cells for t in re.findall(r"-?\d+(?:\.\d+)?", c)]
        elif line.startswith("-") or line.startswith("Mean G difference"):
            tokens = re.findall(r"(?<![\w.-])-?\d+\.\d+", line) + re.findall(r"(?<=: )\d+$", line)
        else:
            tokens = []
        bad += [t for t in tokens if not in_json(t, pool)]
    assert not bad, bad
    # all decimals anywhere in the document (outside the prose rule text) are JSON-derived too
    for t in re.findall(r"(?<![\w.])-?\d+\.\d+", md):
        assert in_json(t, pool), t


def test_verdict_line_and_values(results):
    md = v4_report.render(results)
    v = results["go_no_go"]
    assert re.search(rf"\*\*Verdict: {v['verdict'].upper()}\*\*", md)
    assert f"Paired keys (world, seed, condition): {v['paired_keys']}" in md
    assert f"DS-all paired mean G: {v['ds_all']['mean_g']:.3f}" in md
    assert f"DS-all median s/decision: {v['ds_all']['median_s_per_decision']:.2f}" in md
    assert "go_also_holds: " in md
    assert "Pilot estimates" in md and "Preregistration commit: 0000000synthetic" in md


def test_prereg_commit_fallback(results):
    r = {k: v for k, v in results.items() if k != "prereg_commit"}
    assert "see PREREGISTRATION.md" in v4_report.render(r)


def test_comparison_and_world_tables(results):
    md = v4_report.render(results)
    c = results["comparisons_mean_g_diff"]["F-Jev_vs_DS-all"]
    assert f"| {c['pairs']} | {c['seeds']} | {c['mean_diff']:.3f} | [{c['low']:.3f}, {c['high']:.3f}] |" in md
    for world in results["by_world"]:
        assert f"## Per-world results: {world}" in md


def test_deterministic(results, tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    assert v4_report.main([str(FIXTURE), str(a)]) == 0
    assert v4_report.main([str(FIXTURE), str(b)]) == 0
    assert a.read_text() == b.read_text() and a.read_text().endswith("\n")


def test_missing_values_print_dash(results):
    r = copy.deepcopy(results)
    r["arms"]["F-Jev"]["compliance"] = None
    r["arms"]["F-Jev"]["s_per_decision"]["median"] = None
    md = v4_report.render(r)
    row = next(ln for ln in md.splitlines() if ln.startswith("| F-Jev |") and "—" in ln)
    assert "—" in row


def test_planned_counts_complete(results):
    md = v4_report.render(results)
    assert "INCOMPLETE" not in md and "| complete |" in md


def test_incomplete_arm_forces_unclear(results):
    r = copy.deepcopy(results)
    r["planned_cells"]["F-Laya"] = r["arms"]["F-Laya"]["cells"] * 2  # 50% missing
    md = v4_report.render(r)
    assert "INCOMPLETE" in md
    assert "**Verdict: UNCLEAR**" in md and "overridden" in md


def test_incomplete_threshold_is_strictly_over_20_percent(results):
    r = copy.deepcopy(results)
    n = r["arms"]["F-Jev"]["cells"]
    r["planned_cells"]["F-Jev"] = n * 5 // 4  # exactly 20% missing -> still complete
    assert v4_report.completeness(r)["F-Jev"]["incomplete"] is False
    r["planned_cells"]["F-Jev"] = n * 5 // 4 + 1
    assert v4_report.completeness(r)["F-Jev"]["incomplete"] is True


def test_planned_not_provided(results):
    r = {k: v for k, v in results.items() if k != "planned_cells"}
    assert "Planned counts not provided." in v4_report.render(r)


def test_non_decision_arm_incomplete_keeps_verdict(results):
    r = copy.deepcopy(results)
    r["planned_cells"]["F-Jev-noQueen"] = r["arms"]["F-Jev-noQueen"]["cells"] * 3
    md = v4_report.render(r)
    assert "INCOMPLETE" in md and "overridden" not in md
