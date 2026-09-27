import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from antelligence.kernel import LocalView
from antelligence.kernel import events as ev
from antelligence.providers import Budgeted, FakeProvider
from antelligence.worlds.task_dag import ARMS, SEEDS, LLMPlanner, ScriptedPlanner, TaskDAGWorld, build
from antelligence.worlds.task_dag import planning as ported

E15 = Path(__file__).resolve().parents[2] / "docs/research/desci-paper-20260915/e15-corrected-provisioning"


@pytest.fixture(scope="module")
def original():
    """The paper's own run_e15.py, now importable because the hive modules live in the repo."""
    spec = importlib.util.spec_from_file_location("run_e15_original", E15 / "run_e15.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _proposals(arm, seed):
    sched = build(arm, seed)
    world: TaskDAGWorld = sched.world
    out = []
    for agent in world.agents():
        view = LocalView(agent_id=agent, tick=1, revision=0, seed=0, observation=world.observe(agent, 1).data)
        proposal = ScriptedPlanner().decide(view).params["proposal"]
        out.append({**proposal, "agent": agent})
    return world.task, out


@pytest.mark.parametrize("arm", ARMS)
def test_ported_admission_and_merge_match_the_original_on_every_seed(original, arm):
    for seed in SEEDS:
        task, proposals = _proposals(arm, seed)
        mine = [ported.merge_partitioned(task, proposals)] if arm.endswith("merged") else proposals
        theirs = [original.merge_partitioned(task, proposals)] if arm.endswith("merged") else proposals
        assert ported.admission_bytes(ported.admit(task, mine)) == original.admission_bytes(original.admit(task, theirs))


def test_ported_functions_are_textually_identical_to_the_paper(original):
    import inspect
    for name in ("admit", "merge_partitioned", "_serialize_resource_claims", "delegated_slots", "prompt_for",
                 "parse_proposal", "execute_admitted", "assert_partition_coverage", "record_for_plan"):
        assert inspect.getsource(getattr(ported, name)) == inspect.getsource(getattr(original, name)), name


@pytest.mark.parametrize("arm, published_successes", [("solo_planner", 8), ("swarm_partitioned", 0),
                                                      ("swarm_partitioned_merged", 16)])
def test_published_llm_dags_reexecute_to_the_published_results(arm, published_successes):
    """Real E15 LLM-run admissions, re-executed through the engine's port."""
    published = json.loads((E15 / f"results_{arm}.json").read_text())
    assert len(published["runs"]) == 20
    successes = 0
    for run in published["runs"]:
        task = ported.fixture_task(run["seed"])
        assert task["composition"] == run["composition"]
        executed = ported.execute_admitted(task, run["admission"], False)
        assert executed["success"] == run["execution"]["success"], run["seed"]
        successes += executed["success"]
    assert successes == published_successes


def test_engine_arms_scripted_results():
    totals = {arm: sum(build(arm, s).run().metrics["success"] for s in SEEDS) for arm in ARMS}
    assert totals == {"solo_planner": 16, "swarm_partitioned": 0, "swarm_partitioned_merged": 16}


def test_impossible_fixtures_are_never_successes_and_never_unsafe():
    for seed in SEEDS:
        metrics = build("swarm_partitioned_merged", seed).run().metrics
        if metrics["composition"] == "impossible":
            assert not metrics["success"]
        assert metrics["unsafe_act_count"] == 0 and metrics["deterministic"]


def test_observation_is_the_paper_prompt_and_slice_only(original):
    world = TaskDAGWorld(102, "swarm_partitioned_merged")
    obs = world.observe("agent-2", 1).data
    assert obs["prompt"] == original.prompt_for(world.task, 102, "swarm_partitioned", "agent-2")
    embedded = json.loads(obs["prompt"].rsplit("\n\n", 1)[1])["fixture"]
    assert embedded == obs["fixture"]
    assert set(obs["fixture"]["requirements"]) == {obs["fixture"]["my_sample"]}
    assert "evaluation" not in json.dumps(obs) and "reference_plan" not in json.dumps(obs)


def test_underprovisioning_fails_loudly():
    with pytest.raises(RuntimeError, match="coverage"):
        ported.assert_partition_coverage(ported.fixture_task(101), ["agent-0", "agent-1", "agent-2"])


def test_bad_proposals_are_parse_errors():
    world = TaskDAGWorld(101, "solo_planner")
    from antelligence.kernel import Intent
    assert world.apply("solo", Intent("propose", {"proposal": {"nodes": []}}), 1).accepted is False
    assert world.apply("solo", Intent("noop"), 1).reason == "no_proposal"
    world.step_environment(1)
    assert world.metrics()["parse_errors"] == 2 and not world.metrics()["success"]


def fixture_responder(request):
    """Stand-in LLM: reads the fixture embedded in the paper prompt and answers like the scripted planner."""
    text = request.messages[0]["content"]
    body = json.loads(text.split("\nYour previous output")[0].rsplit("\n\n", 1)[1])
    view = LocalView(agent_id=body["agent"], tick=1, revision=0, seed=0, observation={"fixture": body["fixture"]})
    return json.dumps(ScriptedPlanner().decide(view).params["proposal"])


def test_llm_planner_reproduces_scripted_results():
    for arm in ARMS:
        budget = Budgeted(FakeProvider(fixture_responder))
        result = build(arm, 102, policy_factory=lambda a: LLMPlanner(budget, "stand-in")).run()
        assert result.metrics["success"] == build(arm, 102).run().metrics["success"]
        assert budget.usage.calls == (1 if arm == "solo_planner" else 4)


def test_llm_planner_retries_once_then_gives_up():
    replies = iter(["not json", json.dumps({"goal": "x", "nodes": []}), "still not json", "nope"])
    budget = Budgeted(FakeProvider(lambda r: next(replies)))
    sched = build("solo_planner", 101, policy_factory=lambda a: LLMPlanner(budget, "stand-in"))
    result = sched.run()
    decided = sched.log.of_type(ev.DECIDED)[0].data
    assert decided["action"] == "noop" and decided["meta"]["calls"] == 2 and decided["meta"]["parse_errors"] == 2
    assert result.metrics["parse_errors"] == 1 and not result.metrics["success"]
