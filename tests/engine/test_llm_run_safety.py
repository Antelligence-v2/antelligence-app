"""LLM runs: failures are counted and stay replayable, limits and up-front checks hold (PR #22 review)."""

import tempfile
from pathlib import Path

import pytest

from antelligence.api.app import EngineService, QueueFull, RunRequest
from antelligence.experiments import RunSpec, execute_run
from antelligence.experiments.runner import experiment_request, recommend
from antelligence.kernel.types import PROVIDER_ERROR
from antelligence.provenance.bundle import replay
from antelligence.providers import FakeProvider, ProviderError, litellm
from antelligence.worlds.ant_colony import build

LLM_ANTS = {"max_steps": 12, "agent_type": "LLM-Powered", "model": "m"}


@pytest.fixture
def proxy(monkeypatch):
    """Points engine LLM runs at a fake proxy; returns a setter for its responder."""
    monkeypatch.setenv("IO_SECRET_KEY", "test-key")
    monkeypatch.delenv("ANTELLIGENCE_OFFLINE", raising=False)
    litellm.configure(Path(tempfile.mkdtemp()))
    state = {"responder": lambda request: "toward", "fake": None}

    def make(*args, **kwargs):
        state["fake"] = FakeProvider(lambda request: state["responder"](request))
        return state["fake"]

    monkeypatch.setattr(litellm, "OpenAICompatProvider", make)
    yield state
    litellm.configure(None)


def _flaky(failures: int):
    count = {"n": 0}

    def respond(request):
        count["n"] += 1
        if count["n"] <= failures:
            raise ProviderError("HTTP 429: slow down (request 7f3a)")
        return "toward"
    return respond


def test_a_run_with_provider_errors_still_verifies(proxy):
    proxy["responder"] = _flaky(3)
    record = execute_run(RunSpec("ant_colony", "no_queen", 42, {**LLM_ANTS, "nonce": "a" * 16}))
    assert record["model"]["failures"] == 3
    assert record["model"]["calls"] > 3
    proxy["responder"] = lambda request: 1 / 0  # replay must answer from the cache only
    assert replay(record["bundle"])["replay_ok"] is True


def test_every_decision_is_its_own_request(proxy):
    execute_run(RunSpec("ant_colony", "no_queen", 42, {**LLM_ANTS, "nonce": "b" * 16}))
    requests = proxy["fake"].requests
    assert requests and all(r.seed is not None for r in requests)
    assert len({r.request_hash for r in requests}) == len(requests)


def test_rule_runs_carry_no_model_counters():
    record = execute_run(RunSpec("ant_colony", "no_queen", 42, {"max_steps": 12}))
    assert "model" not in record
    assert "model_calls" not in record["bundle"]["counters"]


def _summary(calls=0, failures=0):
    return {"unsafe_applied": 0, "policy_failures": 0, "model_calls": calls, "model_failures": failures}


def _comparison(wins=6):
    return {"sign_test_p": 0.03, "wins": wins, "losses": 0, "ties": 0, "pairs": 6, "pct_change": 50.0,
            "mean_delta": 3.0}


def test_recommend_excludes_arms_whose_model_calls_failed():
    result = recommend({"queen": _comparison()}, {"no_queen": _summary(100, 0), "queen": _summary(100, 40)},
                       baseline="no_queen", metric_label="food", lower_is_better=False)
    assert result["best_arm"] is None
    assert result["verdicts"]["queen"]["verdict"] == "excluded"
    assert "40 of 100 model calls failed" in result["verdicts"]["queen"]["reason"]


def test_recommend_refuses_when_the_baselines_model_calls_failed():
    result = recommend({"queen": _comparison()}, {"no_queen": _summary(100, 100), "queen": _summary(100, 0)},
                       baseline="no_queen", metric_label="food", lower_is_better=False)
    assert result["best_arm"] is None
    assert "No recommendation" in result["summary"]


def test_provider_error_text_never_reaches_the_trace(proxy):
    def failing(message):
        def respond(request):
            raise ProviderError(message)
        return respond

    spec = RunSpec("ant_colony", "no_queen", 42, {**LLM_ANTS, "nonce": "c" * 16})
    proxy["responder"] = failing("HTTP 429: slow down")
    first = execute_run(spec)
    litellm.configure(Path(tempfile.mkdtemp()))  # fresh cache, so the second run calls the proxy again
    proxy["responder"] = failing("transport error: timed out after 30s")
    second = execute_run(spec)
    assert first["model"]["failures"] == first["model"]["calls"] > 0
    assert first["trace_hash"] == second["trace_hash"]  # only the fixed PROVIDER_ERROR code is logged
    assert PROVIDER_ERROR == "provider_error"


def test_offline_flag_turns_llm_runs_off(monkeypatch):
    monkeypatch.setenv("IO_SECRET_KEY", "test-key")
    monkeypatch.setenv("ANTELLIGENCE_OFFLINE", "1")
    assert litellm.available() is False


def test_model_allowlist(monkeypatch):
    monkeypatch.setenv("ANTELLIGENCE_LLM_MODELS", "a, b")
    assert litellm.check_model("a") == "a"
    with pytest.raises(ValueError, match="not allowed"):
        litellm.check_model("c")


def test_proxy_endpoint_is_not_part_of_the_run_config(monkeypatch, proxy):
    monkeypatch.setenv("LITELLM_API_BASE", "http://elsewhere:4000/v1")
    assert litellm.provider_for_run("r").describe() == {"provider": "litellm"}


def test_hive_queen_with_a_legacy_queen_is_rejected_before_anything_runs():
    with pytest.raises(ValueError, match="hive_queen already has a Queen"):
        experiment_request("tumor", ["rule", "hive_queen"], [1], params={"queen_mode": "heuristic"})


def test_colony_ends_when_every_ant_is_caught():
    scheduler = build("no_queen", 42, max_steps=50)
    scheduler.world.ants.clear()
    assert scheduler.world.done(1)


def test_run_queue_is_capped_and_keeps_unfinished_jobs():
    service = EngineService(Path(tempfile.mkdtemp()))
    for i in range(service.MAX_ACTIVE_RUNS):
        service._run_jobs[f"busy{i}"] = {"job_id": f"busy{i}", "status": "running"}
    with pytest.raises(QueueFull):
        service.start_run(RunRequest(world="foraging", arm="baseline", case=101, params={}))
