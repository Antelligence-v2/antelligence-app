"""The legacy ant colony on the engine: parity with backend/simulation.py, legacy brains, API."""

import asyncio
import contextlib
import io
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from antelligence.api.app import create_app
from antelligence.experiments import RunSpec, execute_run, world
from antelligence.kernel import events as ev
from antelligence.kernel.types import LocalView
from antelligence.providers import FakeProvider, litellm
from antelligence.worlds.ant_colony import ColonyAnt, ColonyQueen, build
from antelligence.worlds.ant_colony.policies import ant_prompt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))  # legacy imports litellm_client

PARITY = [(seed, queen) for seed in (42, 7, 11, 3) for queen in (False, True)]


def legacy_model(seed, queen, predators=0):
    with contextlib.redirect_stdout(io.StringIO()):
        from simulation import SimpleForagingModel
        np.random.seed(seed)
        random.seed(seed)
        return SimpleForagingModel(20, 20, 10, 15, agent_type="Rule-Based", with_queen=queen,
                                   N_predators=predators, predator_type="Rule-Based")


@pytest.mark.parametrize("seed,queen", PARITY)
def test_matches_the_legacy_simulator(seed, queen):
    legacy = legacy_model(seed, queen)
    s = build("queen" if queen else "no_queen", seed, max_steps=200)
    w = s.world
    assert legacy.foods == w.foods
    assert [a.pos for a in legacy.ants] == [a.pos for a in w.ants.values()]
    steps = 0
    with contextlib.redirect_stdout(io.StringIO()):
        while legacy.foods and steps < 200:
            legacy.step()
            steps += 1
    result = s.run()
    assert result.metrics["all_food_collected"] and not legacy.foods
    # Legacy drops food at the nest with a global-RNG coin flip; the engine's own RNG differs,
    # so clearing time may differ by a step or two but the foraging itself is the same.
    assert abs(result.ticks - steps) <= 2, (seed, queen, result.ticks, steps)


def test_predator_layout_matches_legacy():
    legacy = legacy_model(42, False, predators=3)
    w = build("no_queen", 42, n_predators=3).world
    assert [p.pos for p in legacy.predators] == [p.pos for p in w.predators.values()]


def test_predators_catch_ants_and_ants_flee():
    s = build("no_queen", 42, n_predators=3, max_steps=150)
    result = s.run()
    assert result.metrics["ants_caught"] > 0 and result.metrics["escapes"] > 0
    assert result.metrics["ants_alive"] == 10 - result.metrics["ants_caught"]


def test_runs_are_deterministic():
    a = build("queen", 5, n_predators=2, max_steps=80).run()
    b = build("queen", 5, n_predators=2, max_steps=80).run()
    assert a.trace_hash == b.trace_hash


def ant_responder(request):
    system = request.messages[0]["content"]
    if "Queen" in system:
        return json.dumps({"guidance": {"0": [0, 0], "1": [99, 99]}, "report": "hold"})
    if "predator" in system:
        return "patrol"
    return "toward"


def test_llm_ants_use_the_legacy_prompt_and_words():
    fake = FakeProvider(ant_responder)
    s = build("no_queen", 42, agent_type="LLM-Powered", provider=fake, model="m", max_steps=40)
    result = s.run()
    words = [e.data["meta"]["word"] for e in s.log if e.type == ev.DECIDED and "word" in e.data["meta"]]
    assert words and set(words) == {"toward"}
    assert result.metrics["food_collected_by_llm"] == result.metrics["food_collected"] > 0
    assert "Ant 0 has collected" in fake.requests[0].messages[1]["content"]


def test_hybrid_ants_split_in_half_and_failed_calls_lay_alarm():
    def down(_request):
        from antelligence.providers.base import ProviderError
        raise ProviderError("proxy down")
    s = build("no_queen", 42, agent_type="Hybrid", provider=FakeProvider(down), model="m", max_steps=5)
    assert [a.is_llm for a in s.world.ants.values()] == [True] * 5 + [False] * 5
    s.run()
    assert s.world.pheromones["alarm"].sum() > 0
    assert any(e.data["meta"].get("fallback") for e in s.log if e.type == ev.DECIDED)


def test_llm_queen_guidance_must_be_a_neighbor_cell():
    obs = {"foods": [[1, 1]], "grid": [20, 20], "nest": [10, 10], "step": 1, "peaks": {},
           "ants": [{"id": "ant-000", "index": 0, "pos": [5, 5], "carrying": False},
                    {"id": "ant-001", "index": 1, "pos": [6, 6], "carrying": False}]}
    from antelligence.worlds.ant_colony.policies import _parse_guidance
    assert _parse_guidance({"0": [5, 6], "1": [9, 9], "x": [1, 1]}, obs) == {"ant-000": [5, 6]}


def test_heuristic_queen_sends_carriers_home_and_others_to_food():
    obs = {"foods": [[1, 1], [8, 8]], "grid": [20, 20], "nest": [10, 10],
           "ants": [{"id": "ant-000", "index": 0, "pos": [2, 2], "carrying": False},
                    {"id": "ant-001", "index": 1, "pos": [2, 2], "carrying": True}]}
    intent = asyncio.run(ColonyQueen().decide(LocalView("queen", 1, 0, 1, obs)))
    assert intent.params["guidance"] == {"ant-000": [1, 1], "ant-001": [10, 10]}


def test_prompt_styles_render():
    s = build("no_queen", 42, max_steps=1)
    obs = s.world.observe("ant-000", 1).data
    assert "Reply with only one word" in ant_prompt(obs, "Structured")
    assert "Survival is priority #1" in ant_prompt(obs, "Autonomous")
    with pytest.raises(ValueError):
        ColonyAnt(prompt_style="Chaotic")


def test_registry_and_frames():
    ws = world("ant_colony")
    assert ws.resolve_params({})["agent_type"] == "Rule-Based"
    record = execute_run(RunSpec("ant_colony", "queen", 42, {"max_steps": 30}))
    assert record["metrics"]["food_collected"] > 0
    s = ws.build(RunSpec("ant_colony", "no_queen", 42, {"max_steps": 10, "n_predators": 2}), "frames-test")
    s.run()
    frame = s.frames[-1]["world"]
    assert set(frame["fields"]) == {"trail", "alarm", "recruitment", "fear", "efficiency"}
    assert len(frame["ants"]) <= 10 and len(frame["predators"]) == 2
    assert s.scene["kind"] == "ant_colony" and s.scene["nest"] == [10, 10]


def test_llm_colony_run_job_through_the_api(monkeypatch):
    monkeypatch.setenv("IO_SECRET_KEY", "test-key")
    monkeypatch.setattr(litellm, "OpenAICompatProvider", lambda *a, **k: FakeProvider(ant_responder))
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    body = {"world": "ant_colony", "arm": "queen", "case": 42,
            "params": {"max_steps": 25, "agent_type": "LLM-Powered", "queen_brain": "llm", "n_predators": 2,
                       "predator_type": "Hybrid", "model": "m"}}
    job = client.post("/engine/runs/jobs", json=body).json()
    deadline = time.time() + 120
    while job["status"] not in ("done", "failed") and time.time() < deadline:
        time.sleep(0.02)
        job = client.get(f"/engine/runs/jobs/{job['job_id']}").json()
    assert job["status"] == "done", job["error"]
    frames = client.get(f"/engine/runs/{job['run_id']}/frames").json()
    assert frames["scene"]["kind"] == "ant_colony"
    monkeypatch.setattr(litellm, "OpenAICompatProvider", lambda *a, **k: FakeProvider(lambda r: 1 / 0))
    assert client.post(f"/engine/runs/{job['run_id']}/verify").json()["replay_ok"] is True
