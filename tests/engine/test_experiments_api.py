import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient

from antelligence.api.app import create_app
from antelligence.experiments import RunSpec, catalog, execute_run, run_experiment, sign_test_p, wilson_interval, world
from antelligence.experiments.stats import paired_comparison
from antelligence.experiments.store import EngineStore
from antelligence.kernel.events import EventLogError
from antelligence.provenance import LocalFilePublisher, ProvenanceOutbox, replay, verify_bundle_integrity


# ----------------------------------------------------------------- stats
def test_sign_test_known_values():
    assert sign_test_p(0, 0) is None
    assert sign_test_p(6, 0) == pytest.approx(0.03125)
    assert sign_test_p(17, 2) == pytest.approx(0.000728607177734375)
    assert sign_test_p(5, 5) == 1.0


def test_wilson_interval_bounds():
    assert wilson_interval(0, 0) is None
    w = wilson_interval(20, 20)
    assert 0.83 < w["low"] < 0.84 and w["high"] == 1.0


def test_paired_comparison_drops_missing_pairs_and_respects_direction():
    result = paired_comparison([10, 10, None, 10], [8, 12, 5, 10], lower_is_better=True)
    assert (result["wins"], result["losses"], result["ties"], result["dropped_pairs"]) == (1, 1, 1, 1)
    higher = paired_comparison([1, 1], [2, 2], lower_is_better=False)
    assert higher["wins"] == 2 and higher["pct_change"] == 100.0
    with pytest.raises(ValueError):
        paired_comparison([1], [1, 2], lower_is_better=True)


# -------------------------------------------------------------- registry
def test_catalog_and_param_validation():
    names = {w["name"] for w in catalog()}
    assert names == {"foraging", "tumor", "task_dag"}
    tumor = world("tumor")
    assert tumor.resolve_params({}) == {"max_steps": 150, "n_nanobots": 10}
    for bad in ({"max_steps": 5}, {"n_nanobots": 0}, {"max_steps": True}, {"speed": 2}):
        with pytest.raises(ValueError):
            tumor.resolve_params(bad)
    with pytest.raises(ValueError):
        world("mars")


# ------------------------------------------------------ runner + bundles
def test_run_bundle_is_self_verifying_and_replayable():
    record = execute_run(RunSpec("foraging", "hive_memory", 101))
    bundle = record["bundle"]
    assert verify_bundle_integrity(bundle)
    assert bundle["trust"] == {"trust_tier": "local_replay", "proof_ok": False, "onchain_ok": False,
                               "note": bundle["trust"]["note"]}
    assert replay(bundle)["replay_ok"] is True
    forged = copy.deepcopy(bundle)
    forged["metrics"]["sweep_moves"] = 0
    assert replay(forged) == {"replay_ok": False, "reason": "bundle_hash_mismatch"}


def test_replay_detects_a_consistent_but_false_trace():
    bundle = execute_run(RunSpec("foraging", "baseline", 102))["bundle"]
    forged = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    forged["trace_hash"] = "0" * 64
    from antelligence.kernel.canonical import content_hash
    forged["bundle_hash"] = content_hash(forged)
    result = replay(forged)
    assert result["replay_ok"] is False and result["reason"] == "trace_mismatch"


def test_tumor_bundle_carries_the_five_public_values():
    bundle = execute_run(RunSpec("tumor", "rule", 1, {"max_steps": 20, "n_nanobots": 4}))["bundle"]
    pv = bundle["public_values"]
    assert set(pv) == {"config_hash", "kill_rate_bps", "nanobot_count", "tumor_radius", "steps"}
    assert pv["nanobot_count"] == 4 and pv["steps"] == 20 and pv["tumor_radius"] == 200
    from backend.chain.proof_spec import build_public_values_payload
    assert build_public_values_payload(**pv)["kill_rate_bps"] == pv["kill_rate_bps"]


def test_experiment_report_and_cache(tmp_path):
    store = EngineStore(tmp_path)
    request = {"world": "foraging", "arms": ["baseline", "hive_memory"], "cases": [101, 102, 103]}
    report = run_experiment(request, store=store)
    comp = report["comparisons_vs_baseline"]["hive_memory"]
    assert comp["pairs"] == 3 and report["request"]["baseline"] == "baseline"
    assert report["arms"]["baseline"]["successes"] == 3 and report["caveats"]
    assert run_experiment(request, store=store) == report
    run_id = report["runs"]["hive_memory"][0]["run_id"]
    assert store.get_run(run_id)["trace_hash"] == store.events(run_id)["trace_hash"]


def test_experiment_request_validation():
    for bad in ({"world": "foraging", "arms": ["nope"], "cases": [1]},
                {"world": "foraging", "arms": ["baseline"], "cases": []},
                {"world": "foraging", "arms": ["baseline"], "cases": [1], "baseline": "signals"},
                {"world": "foraging", "arms": ["baseline"], "cases": [-1]}):
        with pytest.raises(ValueError):
            run_experiment(bad)


def test_stored_event_logs_are_verified_on_read(tmp_path):
    store = EngineStore(tmp_path)
    run_id = execute_run(RunSpec("foraging", "baseline", 101), store=store)["run_id"]
    path = tmp_path / "events" / f"{run_id}.jsonl"
    lines = path.read_text().splitlines()
    row = json.loads(lines[3])
    row["tick"] = 999
    lines[3] = json.dumps(row)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(EventLogError):
        store.events(run_id)
    with pytest.raises(ValueError):
        store.events("../etc/passwd")


# ------------------------------------------------------------------ outbox
class Flaky:
    name = "flaky"

    def __init__(self, failures):
        self.failures = failures
        self.published = []

    async def publish(self, bundle):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("node offline")
        self.published.append(bundle["bundle_hash"])
        return {"uri": f"test://{bundle['bundle_hash']}"}


def test_outbox_is_idempotent_and_retries_then_fails():
    bundle = execute_run(RunSpec("foraging", "baseline", 101))["bundle"]
    outbox = ProvenanceOutbox(max_attempts=2)
    assert outbox.enqueue(bundle) is True and outbox.enqueue(bundle) is False
    assert asyncio.run(outbox.drain(Flaky(failures=5))) == {"published": 0, "failed": 0, "retrying": 1}
    assert asyncio.run(outbox.drain(Flaky(failures=5))) == {"published": 0, "failed": 1, "retrying": 0}
    assert outbox.status(bundle["bundle_hash"])["status"] == "failed"
    assert outbox.pending() == []


def test_outbox_publishes_to_local_files(tmp_path):
    bundle = execute_run(RunSpec("foraging", "baseline", 101))["bundle"]
    outbox = ProvenanceOutbox()
    outbox.enqueue(bundle)
    assert asyncio.run(outbox.drain(Flaky(failures=1))) == {"published": 0, "failed": 0, "retrying": 1}
    assert asyncio.run(outbox.drain(LocalFilePublisher(tmp_path))) == {"published": 1, "failed": 0, "retrying": 0}
    status = outbox.status(bundle["bundle_hash"])
    assert status["status"] == "published" and status["attempts"] == 2
    stored = json.loads((tmp_path / f"{bundle['bundle_hash']}.json").read_text())
    assert verify_bundle_integrity(stored)


# --------------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))


def test_api_run_lifecycle(client):
    assert client.get("/engine/health").json()["worlds"] == ["foraging", "task_dag", "tumor"]
    assert {w["name"] for w in client.get("/engine/worlds").json()} == {"foraging", "task_dag", "tumor"}
    created = client.post("/engine/runs", json={"world": "foraging", "arm": "hive_memory", "case": 101})
    assert created.status_code == 201
    run = created.json()
    fetched = client.get(f"/engine/runs/{run['run_id']}").json()
    assert fetched["trace_hash"] == run["trace_hash"] and fetched["outbox"]["status"] == "pending"
    events = client.get(f"/engine/runs/{run['run_id']}/events", params={"limit": 5}).json()
    assert events["total"] == run["event_count"] and len(events["events"]) == 5
    assert client.post(f"/engine/runs/{run['run_id']}/verify").json()["replay_ok"] is True
    assert client.post("/engine/outbox/drain").json()["published"] == 1
    assert client.get(f"/engine/runs/{run['run_id']}").json()["outbox"]["status"] == "published"


def test_api_cross_world_experiments(client):
    forage = client.post("/engine/experiments", json={"world": "foraging", "arms": ["baseline", "signals"],
                                                      "cases": [101, 102]})
    tumor = client.post("/engine/experiments", json={"world": "tumor", "arms": ["rule", "signals"], "cases": [1],
                                                     "params": {"max_steps": 20, "n_nanobots": 4}})
    assert forage.status_code == tumor.status_code == 201
    assert tumor.json()["primary_metric"] == "living_cells"
    listed = {e["experiment_id"] for e in client.get("/engine/experiments").json()}
    assert {forage.json()["experiment_id"], tumor.json()["experiment_id"]} <= listed
    assert client.get(f"/engine/experiments/{forage.json()['experiment_id']}").json() == forage.json()


@pytest.mark.parametrize("body", [
    {"world": "mars", "arm": "x", "case": 1},
    {"world": "foraging", "arm": "nope", "case": 1},
    {"world": "tumor", "arm": "rule", "case": 1, "params": {"max_steps": 100000}},
    {"world": "foraging", "arm": "baseline", "case": -1},
    {"world": "foraging", "arm": "baseline", "case": 1, "extra": True},
])
def test_api_rejects_bad_runs(client, body):
    assert client.post("/engine/runs", json=body).status_code == 422


def test_api_limits_and_missing(client):
    assert client.post("/engine/experiments", json={"world": "foraging", "arms": ["baseline"],
                                                    "cases": list(range(21))}).status_code == 422
    assert client.get("/engine/runs/nope").status_code == 404
    assert client.get("/engine/experiments/nope").status_code == 404


def test_api_is_local_only(tmp_path):
    remote = TestClient(create_app(tmp_path), client=("203.0.113.9", 5000))
    assert remote.get("/engine/health").status_code == 403
    local = TestClient(create_app(tmp_path))
    assert local.get("/engine/health", headers={"origin": "https://evil.example"}).status_code == 403


def test_task_dag_experiment_reproduces_the_merge_result():
    report = run_experiment({"world": "task_dag", "arms": list(world("task_dag").arms), "cases": list(range(101, 121))})
    comps = report["comparisons_vs_baseline"]
    assert report["arms"]["swarm_partitioned_merged"]["successes"] == 16
    assert report["arms"]["swarm_partitioned"]["successes"] == 0
    assert comps["swarm_partitioned"]["losses"] == 16 and comps["swarm_partitioned_merged"]["ties"] == 20
    assert execute_run(RunSpec("task_dag", "swarm_partitioned_merged", 101))["bundle"]["metrics"]["success"] is True
