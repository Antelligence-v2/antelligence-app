import json

import pytest

from scripts import v4_pilot as cli
from tests.engine.test_v4_pilot_harness import git

W = ["--world", "fake_a=tests.engine.fake_pilot_world:FAKE_A", "--world", "fake_b=tests.engine.fake_pilot_world:FAKE_B"]


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("dry-run must not read keys")

    monkeypatch.setattr(cli, "nous_key", refuse)
    monkeypatch.setattr(cli, "env_value", refuse)


def call(capsys, *argv):
    code = cli.main([*argv])
    return code, capsys.readouterr().out


def test_run_report_data_and_rerun(tmp_path, capsys):
    out = tmp_path / "out"
    base = ["--dry-run", "--root", str(tmp_path), "--out-dir", str(out), *W]
    arms = "S,S-prime,DS-all,F-Jev,F-Laya"
    code, text = call(capsys, "run", *base, "--seeds", "100,101", "--arms", arms, "--bundles")
    first = json.loads(text)
    assert code == 0 and first["ran"] == first["planned"] == 2 * (6 + 4 + 6 + 6 + 6) and first["errors"] == 0
    code, text = call(capsys, "run", *base, "--seeds", "100,101", "--arms", arms)
    assert json.loads(text)["ran"] == 0
    code, text = call(capsys, "report-data", *base)
    results = json.loads((out / "results.json").read_text())
    assert code == 0 and results["cells"] == first["planned"]
    assert set(results["arms"]) == set(arms.split(","))
    assert results["arms"]["F-Jev"]["mean_g"] is not None and results["arms"]["S"]["mean_g"] is None
    assert results["go_no_go"]["verdict"] in ("go", "no-go", "unclear")
    assert "F-Jev_vs_DS-all" in results["comparisons_mean_g_diff"] and results["limits_usd"]["nous"] == 4.5


def test_validity_calibrate_plan_dry_runs(tmp_path, capsys):
    base = ["--dry-run", "--root", str(tmp_path), "--out-dir", str(tmp_path), *W]
    code, text = call(capsys, "validity", *base)
    assert code == 0 and json.loads((tmp_path / "validity.json").read_text())["fake_a"]["variants"]["v1"]["valid"]
    bad = ["--dry-run", "--root", str(tmp_path), "--out-dir", str(tmp_path), "--world",
           "bad=tests.engine.fake_pilot_world:FAKE_BAD"]
    code, text = call(capsys, "validity", *bad)
    assert code == 1 and json.loads(text)["invalid_variants"] == ["bad/v2"]
    code, text = call(capsys, "calibrate", *base, "--backend", "jev,laya", "--n", "30")
    summary = json.loads((tmp_path / "calibration-summary.json").read_text())
    assert code == 0 and summary["jev"]["all"]["n"] == 30 and summary["laya"]["judgement"]["n"] > 0
    code, _ = call(capsys, "calibrate", *base, "--backend", "jev", "--n", "30")  # resumes: nothing re-asked
    assert len((tmp_path / "calibration" / "jev.jsonl").read_text().splitlines()) == 30
    code, text = call(capsys, "plan", *base)
    proj = json.loads(text)
    assert code == 0 and proj["cells"]["planned"] == proj["cells"]["after_cuts"] > 0
    assert (tmp_path / "plan.json").exists() and proj["unpriced_arms"]


def test_plan_applies_cuts_from_measured_costs(tmp_path, capsys):
    cells = tmp_path / "plumbing.jsonl"
    rows = [{"world": w, "arm": "DS-all", "cost_by_provider": {"nous": 0.7}, "wall_s": 1.0}
            for w in ("fake_a", "fake_b")]
    cells.write_text("\n".join(json.dumps(r) for r in rows))
    code, text = call(capsys, "plan", "--dry-run", "--root", str(tmp_path), "--out-dir", str(tmp_path), *W,
                      "--arms", "DS-all", "--costs-from", str(cells))
    proj = json.loads(text)
    # 2 worlds x 5 seeds x 3 conditions at 0.7 each is over $4.50; fake worlds are not "foraging_sb", so no seed cut
    assert code == 1 and proj["over_after_cuts"] == ["nous"] and proj["cells"]["planned"] == 30
    assert [d["cut"] for d in proj["decisions"]] == ["DS-all foraging to 2 seeds per condition",
                                                    "queen speaks every 20 ticks"]
    assert proj["projected_final"]["nous"] == proj["projected_initial"]["nous"]  # neither cut applies here


def test_eval_seeds_are_refused_until_prereg_is_committed(tmp_path, capsys):
    git(tmp_path, "init", "-q")
    argv = ["run", "--dry-run", "--root", str(tmp_path), "--out-dir", str(tmp_path / "o"), *W, "--seeds", "eval",
            "--arms", "S", "--conditions", "base"]
    with pytest.raises(SystemExit, match="evaluation refused"):
        cli.main(argv)
    assert not (tmp_path / "o").exists()
    for f in cli.pilot.GATED_FILES:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("x")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "gate")
    code, text = call(capsys, *argv)
    assert code == 0 and json.loads(text)["ran"] == 10  # 2 worlds x 5 eval seeds
    for cell in (tmp_path / "o" / "cells.jsonl").read_text().splitlines():
        assert json.loads(cell)["split"] == "eval"


def test_live_mode_reads_keys_only_at_the_cli_boundary(tmp_path):
    # no --dry-run: the wiring is live, so building the Jev backend asks the CLI's env_value for its key
    # (the autouse fixture makes that raise, which also proves nothing else reads the environment or files)
    with pytest.raises(AssertionError, match="dry-run must not read keys"):
        cli.main(["calibrate", "--root", str(tmp_path), *W, "--n", "5", "--backend", "jev"])
