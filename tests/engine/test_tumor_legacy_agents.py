"""Legacy tumor brains on the engine: LLM / hybrid nanobots, the Queen, and LLM runs through the API."""

import json
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antelligence.api.app import create_app
from antelligence.kernel import events as ev
from antelligence.kernel.types import LocalView
from antelligence.providers import FakeProvider, litellm
from antelligence.worlds.tumor import build
from antelligence.worlds.tumor.legacy import LegacyNanobot, LegacyQueen, _parse_guidance, nanobot_prompt
from antelligence.worlds.tumor.policies import NanobotPolicy


def responder(request):
    if "Queen" in request.messages[0]["content"]:
        return json.dumps({"guidance": {"0": [3, 4], "1": [0, -2], "99": [1, 0]}, "report": "spread out"})
    return "follow_trail"


def decided(scheduler, agent=None):
    return [e for e in scheduler.log if e.type == ev.DECIDED and (agent is None or e.agent_id == agent)]


def test_defaults_build_the_plain_rule_arm():
    plain = build("pheromone", 2, max_steps=20).run()
    legacy_off = build("pheromone", 2, max_steps=20, agent_type="Rule-Based", queen_mode="off").run()
    assert plain.trace_hash == legacy_off.trace_hash


def test_llm_bots_ask_only_when_nothing_is_sensed():
    fake = FakeProvider(responder)
    s = build("pheromone", 3, max_steps=60, agent_type="LLM-Powered", provider=fake, model="m")
    result = s.run()
    asked = [e for e in decided(s) if e.data["meta"].get("word")]
    assert asked and len(fake.requests) == len(asked)
    assert all(e.data["meta"]["word"] == "follow_trail" for e in asked)
    assert result.policy_failures == 0
    prompt = fake.requests[0].messages[1]["content"]
    assert "LOCAL MICROENVIRONMENT" in prompt and "BLOOD-BRAIN BARRIER" in prompt


def test_hybrid_gives_the_first_half_llm_brains():
    s = build("rule", 1, max_steps=5, n_nanobots=6, agent_type="Hybrid", provider=FakeProvider(responder), model="m")
    brains = [s._policy_for(f"bot-{i:03d}").describe()["brain"] for i in range(6)]
    assert brains == ["llm"] * 3 + ["rule"] * 3


def test_provider_failure_falls_back_to_chemotaxis_and_is_logged():
    def broken(_request):
        from antelligence.providers.base import ProviderError
        raise ProviderError("proxy down")
    s = build("pheromone", 3, max_steps=60, agent_type="LLM-Powered", provider=FakeProvider(broken), model="m")
    result = s.run()
    fallbacks = [e for e in decided(s) if "fallback" in e.data["meta"]]
    assert fallbacks and all(e.data["action"] == "move" for e in fallbacks)
    assert result.policy_failures == 0


def test_llm_queen_guides_bots_by_index_and_ignores_unknown_ids():
    s = build("rule", 4, max_steps=25, queen_mode="llm", provider=FakeProvider(responder), model="m")
    s.run()
    guides = [e for e in s.log if e.type == ev.OUTCOME and e.agent_id == "queen" and e.data["action"] == "guide"]
    assert len(guides) == 2  # ticks 10 and 20
    assert guides[0].data["effects"]["guided"] == ["bot-000", "bot-001"]


def test_heuristic_queen_needs_no_model_and_guides_toward_hypoxic_cells():
    obs = {"bots": {"bot-000": {"pos": [0, 0], "state": "searching", "payload": 20, "max_payload": 20},
                    "bot-001": {"pos": [0, 0], "state": "searching", "payload": 5, "max_payload": 20},
                    "bot-002": {"pos": [0, 0], "state": "returning", "payload": 20, "max_payload": 20}},
           "hypoxic": [[10, 0], [0, 50]], "stem": [], "resistant": [], "immune_active": [], "turn": True}
    view = LocalView("queen", 10, 0, 1, obs)
    import asyncio
    intent = asyncio.run(LegacyQueen().decide(view))
    assert intent.action == "guide" and intent.params["guidance"] == {"bot-000": [1.0, 0.0]}


def test_queen_parse_normalizes_and_drops_garbage():
    obs = {"bots": {"bot-000": {}, "bot-001": {}}}
    assert _parse_guidance({"0": [0, 5], "1": ["x", 1], "7": [1, 1], "a": [1, 0]}, obs) == {"bot-000": [0.0, 1.0]}


def test_queen_modes_are_validated():
    with pytest.raises(ValueError):
        build("hive_queen", 1, queen_mode="heuristic")
    with pytest.raises(ValueError):
        build("rule", 1, agent_type="LLM-Powered")  # no provider


def test_nanobot_prompt_renders_from_the_observation():
    s = build("pheromone", 1, max_steps=1, agent_type="LLM-Powered", provider=FakeProvider(responder), model="m")
    obs = s.world.observe("bot-000", 1).data
    assert "Drug payload: 20.0/20.0 units" in nanobot_prompt(obs)
    assert isinstance(LegacyNanobot(NanobotPolicy()).describe(), dict)


# ------------------------------------------------------------------ API
@pytest.fixture
def fake_litellm(monkeypatch):
    monkeypatch.setenv("IO_SECRET_KEY", "test-key")
    monkeypatch.setattr(litellm, "OpenAICompatProvider", lambda *a, **k: FakeProvider(responder))


def wait(client, job_id, timeout=120.0):
    deadline = time.time() + timeout
    ticks = []
    while time.time() < deadline:
        job = client.get(f"/engine/runs/jobs/{job_id}").json()
        ticks.append(job["tick"])
        if job["status"] in ("done", "failed"):
            return job, ticks
        time.sleep(0.02)
    raise AssertionError("run job did not finish")


TUMOR_LLM = {"world": "tumor", "arm": "pheromone", "case": 3,
             "params": {"max_steps": 30, "agent_type": "LLM-Powered", "queen_mode": "llm", "model": "m"}}


def test_llm_run_job_finishes_and_replays_offline_from_its_cache(fake_litellm, monkeypatch):
    data = Path(tempfile.mkdtemp())
    client = TestClient(create_app(data))
    started = client.post("/engine/runs/jobs", json=TUMOR_LLM)
    assert started.status_code == 202 and started.json()["llm"] is True
    job, ticks = wait(client, started.json()["job_id"])
    assert job["status"] == "done", job["error"]
    assert ticks == sorted(ticks) and job["tick"] == 30
    assert list((data / "llm_cache").glob("*.jsonl")), "responses are cached per run"

    # Replay must not reach the network: a provider that fails proves the cache answered.
    monkeypatch.setattr(litellm, "OpenAICompatProvider", lambda *a, **k: FakeProvider(lambda r: 1 / 0))
    verified = client.post(f"/engine/runs/{job['run_id']}/verify").json()
    assert verified["replay_ok"] is True, verified


def test_every_llm_launch_is_a_fresh_run(fake_litellm):
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    first = client.post("/engine/runs/jobs", json=TUMOR_LLM).json()
    second = client.post("/engine/runs/jobs", json=TUMOR_LLM).json()
    assert first["run_id"] != second["run_id"]
    wait(client, first["job_id"]), wait(client, second["job_id"])


def test_llm_runs_without_a_key_are_refused(monkeypatch):
    monkeypatch.delenv("IO_SECRET_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setattr(litellm, "_env_loaded", True)  # don't pick up a developer's backend/.env
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    response = client.post("/engine/runs/jobs", json=TUMOR_LLM)
    assert response.status_code == 503 and "IO_SECRET_KEY" in response.json()["detail"]


def test_rule_run_jobs_need_no_key_and_bad_options_are_422(monkeypatch):
    monkeypatch.delenv("IO_SECRET_KEY", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setattr(litellm, "_env_loaded", True)  # don't pick up a developer's backend/.env
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    job, _ = wait(client, client.post("/engine/runs/jobs", json={"world": "tumor", "arm": "rule", "case": 1,
                                                                  "params": {"max_steps": 10}}).json()["job_id"])
    assert job["status"] == "done" and job["llm"] is False
    bad = {"world": "tumor", "arm": "rule", "case": 1, "params": {"agent_type": "Psychic"}}
    assert client.post("/engine/runs/jobs", json=bad).status_code == 422
    assert client.post("/engine/runs/jobs", json={**bad, "params": {"model": "m"}}).status_code == 422


def test_catalog_lists_tumor_options_and_llm_status():
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    tumor = next(w for w in client.get("/engine/worlds").json() if w["name"] == "tumor")
    assert tumor["options"]["agent_type"]["allowed"] == ["Rule-Based", "LLM-Powered", "Hybrid"]
    assert tumor["llm"]["default_model"] == litellm.DEFAULT_MODEL
