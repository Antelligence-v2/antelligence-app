"""Regression tests for the PR #2 review (solmonger, 2026-10-01)."""

import copy
import sys
import threading

import pytest

from antelligence.experiments import RunSpec, execute_run
from antelligence.kernel.canonical import content_hash
from antelligence.provenance import replay
from antelligence.worlds.tumor import build as build_tumor


def _rehash(bundle):
    body = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    return {**body, "bundle_hash": content_hash(body)}


# --- 1. concurrent runs must not corrupt each other ---------------------------------

def test_concurrent_tumor_runs_match_sequential_and_keep_stdout():
    reference = build_tumor("rule", 1, max_steps=60).run().trace_hash
    stdout = sys.stdout
    results, errors = [], []

    def worker():
        try:
            results.append(build_tumor("rule", 1, max_steps=60).run().trace_hash)
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert results == [reference] * 4
    assert sys.stdout is stdout or getattr(sys.stdout, "wrapped", None) is stdout


def test_other_threads_can_still_print_while_a_world_is_quiet(capsys):
    done = threading.Event()

    def run():
        build_tumor("rule", 2, max_steps=20).run()
        done.set()

    thread = threading.Thread(target=run)
    thread.start()
    while not done.is_set():
        print("server log line")
    thread.join()
    assert "server log line" in capsys.readouterr().out


# --- 3. replay must check results, not only hashes -----------------------------------

@pytest.mark.parametrize("mutate", [
    lambda b: b["metrics"].__setitem__("sweep_moves", -999),
    lambda b: b.__setitem__("event_count", 0),
    lambda b: b.__setitem__("ticks", 1),
    lambda b: b["counters"].__setitem__("signals_deposited", 12345),
])
def test_replay_rejects_forged_results_with_a_valid_bundle_hash(mutate):
    bundle = execute_run(RunSpec("foraging", "hive_memory", 101))["bundle"]
    assert replay(bundle)["replay_ok"] is True
    forged = copy.deepcopy(bundle)
    mutate(forged)
    result = replay(_rehash(forged))
    assert result["replay_ok"] is False and result["reason"] == "result_mismatch"


def test_replay_rejects_forged_tumor_public_values():
    bundle = execute_run(RunSpec("tumor", "rule", 1, {"max_steps": 20, "n_nanobots": 4}))["bundle"]
    forged = copy.deepcopy(bundle)
    forged["public_values"]["kill_rate_bps"] = 10_000
    assert replay(_rehash(forged))["reason"] == "result_mismatch"


def test_replay_of_an_unresolvable_spec_is_a_clean_failure():
    bundle = execute_run(RunSpec("foraging", "baseline", 101))["bundle"]
    forged = copy.deepcopy(bundle)
    forged["spec"]["world"] = "mars"
    result = replay(_rehash(forged))
    assert result["replay_ok"] is False and result["reason"] == "spec_unresolvable"


# --- 4. truncated event logs must not be served -------------------------------------

def test_truncated_event_log_is_detected(tmp_path):
    from antelligence.experiments.store import EngineStore
    from antelligence.kernel.events import EventLogError

    store = EngineStore(tmp_path)
    run_id = execute_run(RunSpec("foraging", "baseline", 101), store=store)["run_id"]
    path = tmp_path / "events" / f"{run_id}.jsonl"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")  # drop the tail: the remaining chain is still valid
    with pytest.raises(EventLogError, match="incomplete"):
        store.events(run_id)


# --- API: verify under the lock, clean errors, bounded cases -------------------------

@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient
    from antelligence.api.app import create_app
    return TestClient(create_app(tmp_path)), tmp_path


def test_api_truncated_log_is_a_409_and_unresolvable_verify_is_a_422(client):
    import json
    import sqlite3
    api, data = client
    run = api.post("/engine/runs", json={"world": "foraging", "arm": "baseline", "case": 101}).json()
    path = data / "events" / f"{run['run_id']}.jsonl"
    path.write_text("\n".join(path.read_text().splitlines()[:-2]) + "\n")
    assert api.get(f"/engine/runs/{run['run_id']}/events").status_code == 409

    with sqlite3.connect(data / "engine.sqlite3") as db:
        bundle = json.loads(db.execute("SELECT bundle FROM runs WHERE run_id=?", (run["run_id"],)).fetchone()[0])
        bundle["spec"]["world"] = "mars"
        db.execute("UPDATE runs SET bundle=? WHERE run_id=?", (json.dumps(_rehash(bundle)), run["run_id"]))
    assert api.post(f"/engine/runs/{run['run_id']}/verify").status_code == 422


def test_api_verify_runs_under_the_run_lock(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from antelligence.api import app as app_module

    service = app_module.EngineService(tmp_path)
    app = FastAPI()
    app.include_router(app_module.make_router(service))
    api = TestClient(app)
    run = api.post("/engine/runs", json={"world": "foraging", "arm": "baseline", "case": 101}).json()

    held = []
    real_replay = app_module.replay

    def spying_replay(bundle):
        held.append(service._lock.locked())
        return real_replay(bundle)

    monkeypatch.setattr(app_module, "replay", spying_replay)
    assert api.post(f"/engine/runs/{run['run_id']}/verify").json()["replay_ok"] is True
    assert held == [True], "replay must run while the service lock is held"


@pytest.mark.parametrize("cases", [[-1], [2**31], [2**70]])
def test_api_experiment_cases_are_bounded(client, cases):
    api, _ = client
    assert api.post("/engine/experiments", json={"world": "foraging", "arms": ["baseline"],
                                                  "cases": cases}).status_code == 422


# --- 5. cached experiments refresh when the engine changes ---------------------------

def test_experiment_cache_is_keyed_by_engine_fingerprint(tmp_path, monkeypatch):
    from antelligence.experiments import runner
    from antelligence.experiments.store import EngineStore

    store = EngineStore(tmp_path)
    request = {"world": "foraging", "arms": ["baseline"], "cases": [101]}
    first = runner.run_experiment(request, store=store)
    assert runner.run_experiment(request, store=store) == first, "same code: cached report reused"
    monkeypatch.setattr(runner, "engine_fingerprint", lambda: "changed-engine")
    second = runner.run_experiment(request, store=store)
    assert second["experiment_id"] != first["experiment_id"]
    assert second["engine_fingerprint"] == "changed-engine"


def test_force_reruns_and_fingerprint_tracks_sources():
    from antelligence.experiments.version import engine_fingerprint
    from antelligence.experiments import runner

    assert len(engine_fingerprint()) == 16
    calls = []
    original = runner.execute_run

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    runner.execute_run = counting
    try:
        import tempfile
        from pathlib import Path
        from antelligence.experiments.store import EngineStore
        store = EngineStore(Path(tempfile.mkdtemp()))
        request = {"world": "foraging", "arms": ["baseline"], "cases": [101]}
        runner.run_experiment(request, store=store)
        runner.run_experiment(request, store=store)
        runner.run_experiment(request, store=store, force=True)
    finally:
        runner.execute_run = original
    assert len(calls) == 2, "second call cached, forced call re-ran"


# --- Leads from the second reviewer (each reproduced before fixing) -----------------

def test_l1_sighting_observed_before_a_same_tick_pickup_is_not_admitted():
    from antelligence.kernel import events as ev
    from antelligence.worlds.foraging import build

    sched = build("hive_memory", 101)
    sched.run()
    changed = {}
    for event in sched.log:
        if event.type != ev.MEMORY_CHANGED:
            continue
        data = event.data
        if data["reason"] == "source_replaced":
            changed.setdefault(data["subject"], event.tick)
        if data["to"] == "admitted" and changed.get(data["subject"]) == event.tick and data["reason"] != "source_replaced":
            pytest.fail(f"stale sighting of {data['subject']} admitted at tick {event.tick}")


def test_l1_memory_refuses_observations_older_than_the_source_change():
    from antelligence.kernel import memory as m
    from antelligence.kernel.memory import EvidenceMemory, StaleError

    mem = EvidenceMemory()
    mem.replace_source("r:a", "food:0", tick=5)
    with pytest.raises(StaleError, match="observed"):
        mem.propose(scope="r:a", kind=m.CLAIM, author="a", subject="food:0", body={}, tick=5, observed_at=5)
    assert mem.propose(scope="r:a", kind=m.CLAIM, author="a", subject="food:0", body={}, tick=6,
                       observed_at=6).status == m.ADMITTED


def test_l2_token_budget_holds_under_concurrency():
    import asyncio
    from antelligence.providers import BudgetExceeded, Budgeted, ChatRequest, FakeProvider

    budget = Budgeted(FakeProvider(lambda r: "x" * 160), max_tokens=150)

    async def burst():
        requests = [ChatRequest(model="m", messages=({"role": "user", "content": f"q{i}"},), max_tokens=40)
                    for i in range(5)]
        return await asyncio.gather(*(budget.complete(r) for r in requests), return_exceptions=True)

    results = asyncio.run(burst())
    assert budget.usage.total_tokens <= 150
    assert any(isinstance(r, BudgetExceeded) for r in results)


def test_l3_resolving_one_contradiction_does_not_readmit_a_record_in_another():
    from antelligence.kernel import memory as m
    from antelligence.kernel.memory import EvidenceMemory

    mem = EvidenceMemory()
    a, b, c = (mem.propose(scope="r:a", kind=m.CLAIM, author=x, subject="s", body={"v": i}, tick=1)
               for i, x in enumerate("xyz"))
    first = mem.contradict(a.id, b.id, author="w", tick=2)
    second = mem.contradict(a.id, c.id, author="w", tick=2)
    assert mem.resolve(first, winner=a.id, author=m.WORLD, tick=3).status == m.CONTRADICTED
    assert mem.resolve(second, winner=a.id, author=m.WORLD, tick=4).status == m.ADMITTED


def test_l4_concurrent_policy_failures_do_not_make_the_trace_timing_dependent():
    import asyncio
    from antelligence.kernel import GridField, RunConfig, Scheduler
    from antelligence.kernel import events as ev
    from tests.engine.toy_world import ToyWorld

    class Slow:
        def __init__(self, delay):
            self.delay = delay

        async def decide(self, view):
            await asyncio.sleep(self.delay)
            raise RuntimeError("provider down")

        def describe(self):
            return {"policy": "slow"}

    def run(d0, d1):
        sched = Scheduler(ToyWorld(agents=2), {"a0": Slow(d0), "a1": Slow(d1)}, GridField(), RunConfig("r", max_ticks=1))
        sched.run()
        return [e.agent_id for e in sched.log.of_type(ev.POLICY_FAILED)], sched.log.trace_hash

    assert run(0.01, 0.0) == run(0.0, 0.01)
    assert run(0.0, 0.01)[0] == ["a0", "a1"]


def test_l5_an_earlier_provider_failure_makes_the_cell_an_error():
    from tests.engine.test_research_qa import answer, via_engine, via_swarm_core

    brain = lambda i, r, peers: "RAISE" if (i == 0 and r == 0) else answer("A")
    assert via_engine(brain, "signal_board") == via_swarm_core(brain, "signal_board") == ("error", None)


def test_l5_abstentions_keep_their_citations():
    from antelligence.worlds.research_qa import ScriptedQAPolicy, build
    from tests.engine.test_research_qa import task

    reply = {"answer": None, "evidence_ids": ["e1"], "brief": "insufficient"}
    sched = build(task(), "single", lambda a: ScriptedQAPolicy(lambda v: reply))
    assert sched.run().metrics["status"] == "abstained"
    assert sched.world.answers["worker-1"][0] == reply


def test_l6_malformed_dag_action_is_rejected_not_a_crash():
    from antelligence.kernel import Intent
    from antelligence.worlds.task_dag.world import TaskDAGWorld

    world = TaskDAGWorld(101, "solo_planner")
    bad = {"goal": "n0", "nodes": [{"id": "n0", "parents": [], "resource": "bench", "evidence": [],
                                    "action": {"op": ["reserve"], "sample": "sample-0", "slot": "slot-0",
                                               "revision": 0}}]}
    outcome = world.apply("solo", Intent("propose", {"proposal": bad}), 1)
    assert not outcome.accepted and "malformed" in outcome.reason
    world.step_environment(1)
    assert world.metrics()["parse_errors"] == 1 and not world.metrics()["success"]
