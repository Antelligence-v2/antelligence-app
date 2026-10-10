"""Colony-v2 harness: statistics, planted-colony analysis, preflight gates, offline collection, pod payload."""
import json
import random
import subprocess

import pytest

from scripts import colony_v2_analyze as an
from scripts import colony_v2_collect as co
from scripts import colony_v2_pod as pod
from antelligence.providers import ChatResponse

GOLD = {"medical": "yes", "finance": "10.00"}
WRONG = {"medical": ["no", "maybe"], "finance": ["11.00", "12.00", "13.00"]}


def make_cells(models, accuracy=0.75, copies=False, n=200, samples=3, seed=1):
    """Synthetic cells. Error pattern is fixed per (model, task) so samples of one model are copies of each other;
    across models errors are independent, or identical when ``copies``."""
    rng = random.Random(seed)
    rows = []
    for split in ("development", "evaluation"):
        for d in an.DOMAINS:
            for i in range(n):
                tid = f"{d}:{split}:{i}"
                shared = (rng.random() < accuracy, rng.choice(WRONG[d]))
                for m in models:
                    ok, wrong = shared if copies else (rng.random() < accuracy, rng.choice(WRONG[d]))
                    for s in range(1, samples + 2):
                        ans = GOLD[d] if ok else wrong
                        rows.append({"task_id": tid, "domain": d, "split": split, "model": m, "sample": s, "answer": ans,
                                     "status": "completed", "verification": {"status": "verified", "reason": "x"},
                                     "format_failure": False, "truncated": False, "correct": ok,
                                     "usage": {"calls": 1, "prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.1}})
    return rows


def run(models, **kw):
    return an.analyze(an.Data(make_cells(models, **kw)), [])


# --------------------------------------------------------------- statistics
def test_mcnemar_exact_known_values():
    assert an.mcnemar_exact(10, 2) == pytest.approx(158 / 4096)
    assert an.mcnemar_exact(2, 10) == an.mcnemar_exact(10, 2)
    assert an.mcnemar_exact(0, 0) == 1.0
    assert an.mcnemar_exact(5, 5) == 1.0


def test_wilson_and_holm_known_values():
    lo, hi = an.wilson(5, 10)
    assert (lo, hi) == pytest.approx((0.2366, 0.7634), abs=1e-3)
    assert an.holm([0.01, 0.04]) == pytest.approx([0.02, 0.04])
    assert an.holm([0.03, 0.04]) == pytest.approx([0.06, 0.06])


def test_newcombe_paired_matches_published_example_and_is_antisymmetric():
    # Agresti's 1600-subject approval table (794/150/86/570): difference 0.04; Wald paired CI is (0.0213, 0.0587).
    d, lo, hi = an.newcombe_paired(794, 150, 86, 570)
    assert d == pytest.approx(0.04) and lo == pytest.approx(0.0213, abs=0.002) and hi == pytest.approx(0.0587, abs=0.002)
    d2, lo2, hi2 = an.newcombe_paired(794, 86, 150, 570)
    assert (d2, lo2, hi2) == pytest.approx((-d, -hi, -lo))
    assert an.newcombe_paired(5, 0, 0, 5)[0] == 0


def test_ece_brier():
    out = an.ece_brier([(1.0, True), (1.0, True), (0.0, False)])
    assert out["ece"] == 0 and out["brier"] == 0
    assert an.ece_brier([(0.9, False)])["ece"] == pytest.approx(0.9)


# ------------------------------------------------------------------ analysis
def test_independent_members_beat_copies_of_one_model():
    res = run(["qwen", "phi", "gemma", "haiku"])
    p1 = res["primary"]["P1"]
    assert p1["status"] == "ok" and p1["baseline"].startswith("solo3[")
    for d in an.DOMAINS:  # samples of one model are copies, so solo3 == solo1; the colony votes across models
        row = p1["domains"][d]
        assert row["acc_a"] > row["acc_b"] and row["diff"] > 0.03
    assert p1["any_win"] is True
    assert res["S2_independence"]["colony_local"]["n_eff_rate_adjusted"] > 2.0
    assert res["arms"]["colony_local_cold"]["status"] == "ok" and res["S7_gemma"]["colony_haiku_withG"]["status"] == "ok"
    assert res["S1_ablations"]["colony_local"]["e_single_model"]["accuracy"]["all"]["acc"] < \
        res["arms"]["colony_local"]["accuracy"]["all"]["acc"]


def test_copies_give_no_gain():
    res = run(["qwen", "phi", "gemma", "haiku"], copies=True)
    for key in ("P1", "P2"):
        assert res["primary"][key]["any_win"] is False
        for row in res["primary"][key]["domains"].values():
            assert row["diff"] == 0 and row["statement"] != "colony wins"
    assert res["S2_independence"]["colony_local"]["n_eff_rate_adjusted"] < 1.5
    assert res["explained_null"]["colony_local"]["seats_not_independent"]["flag"] is True


def test_missing_models_are_reported_not_run():
    res = run(["qwen"])
    assert res["arms"]["solo3[qwen]"]["status"] == "ok"
    assert res["arms"]["colony_local"]["status"] == "not run" and res["primary"]["P1"]["status"] == "not run"
    assert res["arms"]["solo3[haiku]"]["status"] == "not run"
    assert "not run" in an.render(json.loads(json.dumps(res, default=str)))
    assert an.analyze(an.Data([]), [])["primary"]["P2"]["status"] == "not run"


def test_format_failures_count_against_arm_and_cold_start_has_zero_weights():
    rows = make_cells(["qwen", "phi", "gemma"], samples=3)
    for r in rows:
        if r["model"] == "qwen" and r["split"] == "evaluation" and r["task_id"].endswith("0"):
            r.update(answer=None, status="invalid", format_failure=True, correct=False)
    res = an.analyze(an.Data(rows), [])
    assert res["format_failures"]["qwen|evaluation|medical"]["format_failures"] > 0
    assert res["arms"]["solo1[qwen]"]["accuracy"]["all"]["no_answer"] > 0
    rel = an.reliability(None, "finance")
    assert rel("anyone", 0.4) == 0.4  # at chance: weight log((K-1)p/(1-p)) = 0 for chance 1/K


def test_end_to_end_writes_results_and_report(tmp_path):
    cells = tmp_path / "cells"
    cells.mkdir()
    by = {}
    for r in make_cells(["qwen", "phi", "gemma", "haiku"], n=60):
        by.setdefault(f"{r['model']}-{r['split']}", []).append(r)
    for name, rows in by.items():
        (cells / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (cells / "run-log.jsonl").write_text('{"event": "start"}\n')  # must be ignored
    w2 = tmp_path / "w2.json"
    w2.write_text(json.dumps({"task_ids": ["medical:evaluation:1", "finance:evaluation:2"]}))
    an.main(["--cells-dir", str(cells), "--out-dir", str(tmp_path / "out"), "--w2-file", str(w2), "--gpu-hours", "1.0", "--gpu-usd", "0.8"])
    results = json.loads((tmp_path / "out/results.json").read_text())
    report = (tmp_path / "out/REPORT.md").read_text()
    assert results["S6_untouched"]["items"] == 118 and "Headline (P1 and P2)" in report and "Explained-null" in report
    assert results["gpu"] == {"hours": 1.0, "usd": 0.8}


# ------------------------------------------------------------------ preflight
def test_disjointness_preflight_refuses_overlap():
    base = [{"task_id": "a", "split": "development", "question": "Is it so?"},
            {"task_id": "b", "split": "evaluation", "question": "Other?"}]
    co.check_disjoint(base)
    with pytest.raises(SystemExit):
        co.check_disjoint(base + [{"task_id": "a", "split": "evaluation", "question": "x"}])
    with pytest.raises(SystemExit):
        co.check_disjoint(base + [{"task_id": "c", "split": "evaluation", "question": "is  it SO?"}])
    real = json.loads(co.TASKS.read_text())["tasks"]
    co.check_disjoint(real)


def test_evaluation_refuses_uncommitted_prereg(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    files = ("PREREG.md", "collect.py")
    for f in files:
        (tmp_path / f).write_text("v1")
    with pytest.raises(SystemExit, match="not committed"):
        co.check_committed(tmp_path, files)
    git("add", ".")
    git("commit", "-m", "x")
    co.check_committed(tmp_path, files)
    (tmp_path / "PREREG.md").write_text("v2")
    with pytest.raises(SystemExit, match="uncommitted"):
        co.check_committed(tmp_path, files)


# ------------------------------------------------------------------- collect
@pytest.fixture
def no_network(monkeypatch):
    import socket

    def deny(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", deny)


def collect(tmp_path, *extra, model="qwen", split="development"):
    return co.main(["--model", model, "--split", split, "--dry-run", "--limit", "3", "--out-dir", str(tmp_path / "cells"),
                    "--ledger", str(tmp_path / "ledger.jsonl"), "--cache-dir", str(tmp_path / "cache"), *extra])


def test_dry_run_collects_offline_and_resumes(tmp_path, no_network):
    out = collect(tmp_path)
    rows = co.read_jsonl(tmp_path / "cells/qwen-development.jsonl")
    assert out["written"] == 9 and len(rows) == 9 and {r["sample"] for r in rows} == {1, 2, 3}
    r = rows[0]
    assert r["served_model"] == "Qwen/Qwen3.8-27B-FP8" and r["verification"]["status"] == "verified"
    assert r["status"] == "completed" and {"trace_hash", "config_hash", "correct", "usage"} <= set(r)
    assert len(co.read_jsonl(tmp_path / "ledger.jsonl")) == 9
    assert collect(tmp_path)["written"] == 0  # resumable: nothing re-run
    assert collect(tmp_path, model="phi")["written"] == 9
    # the cells feed the analysis without the gold label reaching the aggregator
    assert an.Data.load(tmp_path / "cells").tasks["development"]


def test_extra_sample_only_on_evaluation(tmp_path, no_network):
    assert collect(tmp_path, "--extra-sample-for-best")["written"] == 9
    assert collect(tmp_path, "--extra-sample-for-best", split="evaluation")["written"] == 12


def test_truncation_is_format_failure_and_identity_mismatch_is_error(tmp_path, no_network, monkeypatch):
    def reply(model, reason="length"):
        return lambda req: ChatResponse(content='{"answer": "ye', model=model, request_hash=req.request_hash, prompt_tokens=3,
                                        completion_tokens=3, finish_reason=reason)

    monkeypatch.setattr(co, "fake_responder", reply("Qwen/Qwen3.8-27B-FP8"))
    collect(tmp_path)
    rows = co.read_jsonl(tmp_path / "cells/qwen-development.jsonl")
    assert all(r["format_failure"] and r["truncated"] and r["status"] == "invalid" and not r["correct"] for r in rows)
    monkeypatch.setattr(co, "fake_responder", reply("some/other-model", "stop"))
    collect(tmp_path, model="phi")
    rows = co.read_jsonl(tmp_path / "cells/phi-development.jsonl")
    assert all(r["status"] == "error" and not r["correct"] for r in rows)
    assert any(r.get("ok") is False and "identity" in r["error"] for r in co.read_jsonl(tmp_path / "ledger.jsonl"))


def test_haiku_call_cap_persists_via_ledger(tmp_path, no_network):
    ledger = tmp_path / "ledger.jsonl"
    for _ in range(co.HAIKU_MAX_CALLS):
        co.append(ledger, {"model": "haiku", "ok": True})
    out = collect(tmp_path, model="haiku")
    assert out["written"] == 0 and out["budget_stop"] == 9  # no cells written, so they stay resumable
    assert not (tmp_path / "cells/haiku-development.jsonl").exists()


# ----------------------------------------------------------------------- pod
def test_pod_payload_is_pinned_and_secret_free_of_hf_token():
    body = pod.deploy_payload("qwen", "SECRET123", "NVIDIA L40S")
    assert body["imageName"] == pod.VLLM_IMAGE and ":" in body["imageName"] and not body["imageName"].endswith(":latest")
    script = body["dockerStartCmd"][0]
    assert body["dockerEntrypoint"] == ["bash", "-c"] and script.startswith("mkdir -p /logs")
    assert "SECRET123" not in script and body["env"] == {"VLLM_API_KEY": "SECRET123"}  # key never on the command line
    assert "--served-model-name Qwen/Qwen3.8-27B-FP8" in script and "--seed 0" in script and "--max-model-len 8192" in script
    assert "--revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a" in script
    assert "'{\"enable_thinking\":false}'" in script  # shell-quoted once, so vLLM receives valid JSON
    assert 's/$VLLM_API_KEY/[redacted]/g' in script and "--directory /logs" in script
    assert (body["containerDiskInGb"], body["ports"], body["gpuTypeIds"]) == (80, ["8000/http", "8001/http"], ["NVIDIA L40S"])
    assert "HF_TOKEN" not in json.dumps(body) and "HUGGING" not in json.dumps(body).upper()
    assert set(pod.POD_MODELS) == {"qwen", "phi", "gemma"}


def test_start_script_runs_under_bash_and_passes_the_json_flag_intact(tmp_path):
    import subprocess

    fake = tmp_path / "vllm"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n')
    fake.chmod(0o755)
    script = pod.start_script("qwen").replace("/logs", f"{tmp_path}/logs").replace("sleep infinity", "true").replace(
        "(python3 -m http.server", "(true || python3 -m http.server")
    env = {"PATH": f"{tmp_path}:/usr/bin:/bin", "VLLM_API_KEY": "k3y"}
    subprocess.run(["bash", "-c", script], env=env, check=True, timeout=20)
    log = (tmp_path / "logs/vllm.log").read_text()
    assert 'ARG:{"enable_thinking":false}' in log and "ARG:serve" in log and "vllm exited" in log


def test_pod_revision_pin_and_state_file_mode(tmp_path, monkeypatch):
    monkeypatch.setitem(pod.POD_MODELS["phi"], "revision", "abc123")
    assert "--revision" in pod.vllm_args("phi") and "abc123" in pod.vllm_args("phi")
    monkeypatch.setattr(pod, "STATE_PATH", tmp_path / "sub/state.json")
    pod.save_state({"pod_id": "p"})
    assert (tmp_path / "sub/state.json").stat().st_mode & 0o777 == 0o600 and pod.load_state() == {"pod_id": "p"}


def test_up_refuses_while_a_pod_is_running(monkeypatch):
    monkeypatch.setattr(pod, "load_state", lambda: {"pod_id": "p1", "model": "qwen"})
    monkeypatch.setattr(pod, "pod_info", lambda pid: {"desiredStatus": "RUNNING"})
    monkeypatch.setattr(pod, "gql", lambda *a, **k: pytest.fail("must not call the API"))
    with pytest.raises(SystemExit, match="still running"):
        pod.main(["up", "--model", "phi"])
    with pytest.raises(SystemExit, match="not a pod model"):
        pod.main(["up", "--model", "haiku"])
