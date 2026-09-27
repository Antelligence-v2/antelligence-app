import asyncio
import json
from typing import Any, Callable, List, Optional

import pytest

from backend.research_data import select_tasks
from backend.swarm_core import run_task, summarize

from antelligence.kernel import events as ev
from antelligence.providers import Budgeted, FakeProvider
from antelligence.worlds.research_qa import PROTOCOLS, QAPolicy, ResearchQAWorld, ScriptedQAPolicy, build, cell
from antelligence.worlds.research_qa.world import ABSTAIN

SETTINGS = {"temperature": 0.0, "seed": 17, "max_tokens": 128}


def task(expected="A"):
    return {
        "task_id": "task-1", "source_id": "source-1", "dataset": "pubmedqa", "domain": "medical",
        "split": "development", "question": "Which option is supported?",
        "evidence": [{"id": f"e{i}", "text": f"passage {i}"} for i in range(1, 7)],
        "answer_type": "choice", "choices": ["A", "B"], "expected_answer": expected, "tolerance": "0.01",
        "source_url": "https://example.test/source-1",
    }


# A brain decides from (agent index, round, peer answers seen) -> raw content.
Brain = Callable[[int, int, List[Optional[str]]], str]


def answer(value: Optional[str], evidence=("e1",)) -> str:
    return json.dumps({"answer": value, "evidence_ids": list(evidence) if value else [], "brief": "b"})


def via_swarm_core(brain: Brain, protocol: str, t=None):
    t = t or task()
    counts = {}

    def infer(model, messages, **kwargs):
        user = json.loads(messages[-1]["content"])
        index = int(model[1:]) if protocol != "independent_vote" else counts.setdefault(model, 0)
        if protocol == "independent_vote":
            counts[model] += 1
        peers = [s["payload"].get("answer") for s in user.get("signals", [])]
        content = brain(index, user.get("round", 0), peers)
        if content == "RAISE":
            raise RuntimeError("provider down")
        return {"content": content, "response_id": "r", "requested_model": model, "served_model": model,
                "prompt_tokens": 1, "completion_tokens": 1, "elapsed_s": 0.0, "finish_reason": "stop"}

    models = ["m0"] if protocol == "independent_vote" else [f"m{i}" for i in range(PROTOCOLS[protocol].agents)]
    [result] = run_task(t, models, protocol, SETTINGS, infer, lambda e: None, lambda: False)
    return result["status"], result["answer"]


def via_engine(brain: Brain, protocol: str, t=None):
    t = t or task()

    def factory(agent_id):
        index = int(agent_id.rsplit("-", 1)[1]) - 1

        def reply(view):
            peers = [s.payload.get("answer") for s in view.signals]
            content = brain(index, view.observation["round"], peers)
            if content == "RAISE":
                raise RuntimeError("provider down")
            return json.loads(content) if content.startswith("{") else {"broken": content}

        return ScriptedQAPolicy(reply)

    result = build(t, protocol, factory).run()
    return result.metrics["status"], result.metrics["answer"]


BRAINS = {
    "unanimous_A": lambda i, r, peers: answer("A"),
    "split_majority_B": lambda i, r, peers: answer(["A", "B", "B"][i % 3]),
    "no_majority": lambda i, r, peers: answer(["A", "B", None][i % 3]),
    "all_abstain": lambda i, r, peers: answer(None),
    "one_malformed": lambda i, r, peers: "not json" if i == 1 else answer("A"),
    "follow_the_board": lambda i, r, peers: answer(
        ["A", "B", "B"][i % 3] if r == 0 else max(sorted(set(p for p in peers if p)), key=peers.count)),
}


@pytest.mark.parametrize("protocol", ["single", "independent_vote", "signal_board"])
@pytest.mark.parametrize("brain", sorted(BRAINS))
def test_engine_matches_swarm_core_status_and_answer(protocol, brain):
    assert via_engine(BRAINS[brain], protocol) == via_swarm_core(BRAINS[brain], protocol)


def test_provider_error_is_an_error_cell():
    raising = lambda i, r, peers: "RAISE" if i == 0 else answer("A")
    assert via_engine(raising, "independent_vote")[0] == "error"
    assert via_swarm_core(raising, "independent_vote")[0] == "error"


def test_board_claims_are_signals_with_ttl_one_round():
    sched = build(task(), "signal_board", lambda a: ScriptedQAPolicy(lambda v: json.loads(answer("A"))))
    sched.run()
    deposited = sched.log.of_type(ev.SIGNAL_DEPOSITED)
    assert len(deposited) == 9 and all(e.data["ttl"] == 1 and e.data["topic"] == "task-1" for e in deposited)
    observed = [e for e in sched.log.of_type(ev.OBSERVED)]
    assert [len(e.data["signal_ids"]) for e in observed] == [0, 0, 0, 2, 2, 2, 2, 2, 2]


def test_evidence_exchange_shards_then_delivers_only_cited_passages():
    seen = {}

    def reply(view):
        ids = [e["id"] for e in view.observation["task"]["evidence"]]
        seen[(view.agent_id, view.observation["round"])] = ids
        return {"answer": "A", "evidence_ids": ids[:1], "brief": "b"}

    build(task(), "evidence_exchange", lambda a: ScriptedQAPolicy(reply)).run()
    assert seen[("worker-1", 0)] == ["e1", "e4"] and seen[("worker-2", 0)] == ["e2", "e5"]
    assert seen[("worker-1", 1)] == ["e1", "e2", "e3", "e4"], "own shard + each peer's single cited passage"
    assert "e5" not in seen[("worker-1", 1)] and "e6" not in seen[("worker-1", 1)], "uncited passages stay private"


def test_evidence_isolated_never_delivers_peer_passages():
    seen = {}

    def reply(view):
        seen[(view.agent_id, view.observation["round"])] = [e["id"] for e in view.observation["task"]["evidence"]]
        return {"answer": "A", "evidence_ids": [], "brief": "b"}

    build(task(), "evidence_isolated", lambda a: ScriptedQAPolicy(reply)).run()
    assert seen[("worker-1", 1)] == seen[("worker-1", 0)] == ["e1", "e4"]


def test_citing_invisible_evidence_is_invalid():
    reply = lambda v: {"answer": "A", "evidence_ids": ["e6"], "brief": "b"}
    result = build(task(), "evidence_isolated", lambda a: ScriptedQAPolicy(reply)).run()
    assert result.metrics["status"] == "invalid"


def test_labels_never_reach_an_observation():
    sched = build(task(), "signal_board", lambda a: ScriptedQAPolicy(lambda v: json.loads(answer("A"))))
    world: ResearchQAWorld = sched.world
    obs = world.observe("worker-1", 1).data
    assert "expected_answer" not in json.dumps(obs) and "tolerance" not in obs["task"]


def test_llm_qa_policy_and_workbench_summary():
    tasks = select_tasks(["pubmedqa", "finqa"], "development", 2, 1)

    def responder(request):
        view = json.loads(request.messages[1]["content"])
        t = view["task"]
        value = t["choices"][0] if t["answer_type"] == "choice" else "1.00"
        return json.dumps({"answer": value, "evidence_ids": [t["evidence"][0]["id"]], "brief": "stand-in"})

    cells = []
    for t in tasks:
        for protocol in ("single", "independent_vote"):
            budget = Budgeted(FakeProvider(responder))
            result = build(t, protocol, lambda a: QAPolicy(budget, "stand-in")).run()
            cells.append(cell(result, model_keys=["stand-in"], usage=budget.usage.to_dict()))
            assert result.metrics["status"] == "completed"
            assert budget.usage.calls == PROTOCOLS[protocol].agents
    rows = summarize(cells, target_accuracy=0.5)
    assert {(r["domain"], r["variant"]) for r in rows} == {
        ("medical", "single"), ("medical", "independent_vote"), ("finance", "single"), ("finance", "independent_vote")}
    assert all(r["gate"] == "insufficient_evidence" and r["usage_complete"] for r in rows)


def test_llm_malformed_reply_is_invalid_not_dropped():
    policy = QAPolicy(FakeProvider(lambda r: "definitely not json"), "stand-in")
    result = build(task(), "single", lambda a: policy).run()
    assert result.metrics["status"] == "invalid" and result.policy_failures == 0


def test_null_answer_is_an_explicit_abstention():
    sched = build(task(), "single", lambda a: ScriptedQAPolicy(lambda v: json.loads(answer(None))))
    result = sched.run()
    assert result.metrics["status"] == "abstained"
    assert sched.log.of_type(ev.OUTCOME)[0].data["action"] == ABSTAIN
