"""Tests for Tier A ReplayBox and Tier B/C replay interfaces."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Mapping, Sequence

import pytest

from antelligence.harness.core import Artifact, EnvAdapter, EnvSnapshot, EpisodeOutcome, Task, ToolRegistry, ToolSpec
from antelligence.harness.graph import ExecutionGraph
from antelligence.harness.replay import (
    BranchingReplay,
    BranchResult,
    EpisodeRecord,
    EpisodeReplay,
    RecordingBox,
    ReplayBox,
    ReplayMissError,
)
from antelligence.harness.scheduler import LiveBox, run_graph


def test_replay_box_synthetic_fixture_roundtrip_and_miss(tmp_path):
    calls = 0

    async def step_a(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        nonlocal calls
        calls += 1
        return Artifact(task_id=task.id, tool="a", answer=task.payload["x"] * 2, tokens_in=10, tokens_out=5, calls=1)

    async def step_b(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        nonlocal calls
        calls += 1
        return Artifact(task_id=task.id, tool="b", answer=deps["a"].answer + 1, tokens_in=12, tokens_out=3, calls=1)

    reg = ToolRegistry([ToolSpec(name="a", run=step_a), ToolSpec(name="b", run=step_b)])
    graph = ExecutionGraph().add("a").add("b", deps=("a",))
    tasks = [Task(id="t1", payload={"x": 5}), Task(id="t2", payload={"x": 10})]

    rec_box = RecordingBox(LiveBox())
    res_live = asyncio.run(run_graph(tasks, graph, reg, box=rec_box))
    assert calls == 4
    assert res_live.artifacts["t1"]["b"].answer == 11
    assert res_live.artifacts["t2"]["b"].answer == 21

    jsonl = tmp_path / "replay.jsonl"
    rec_box.to_replay_box().to_jsonl(jsonl)

    replay_box = ReplayBox.from_jsonl(jsonl)
    assert len(replay_box) == 4
    calls_before = calls
    res_replay = asyncio.run(run_graph(tasks, graph, reg, box=replay_box))
    assert calls == calls_before  # $0 recomposition: zero live calls
    assert res_replay.artifacts["t1"]["b"].answer == 11
    assert res_replay.artifacts["t2"]["b"].answer == 21

    # Changing task input changes input_hash -> ReplayMissError
    changed = [Task(id="t1", payload={"x": 99})]
    with pytest.raises(ReplayMissError):
        asyncio.run(run_graph(changed, graph, reg, box=replay_box))


def test_tier_b_and_tier_c_protocols():
    class ToyBrancher:
        def branch(
            self,
            env: EnvAdapter,
            snapshot: EnvSnapshot,
            variants: Mapping[str, Callable[[Any], Any]],
            *,
            max_steps: int = 100,
        ) -> Dict[str, BranchResult]:
            out: Dict[str, BranchResult] = {}
            for name, policy in variants.items():
                env.restore(snapshot)
                res = env.step(policy(snapshot.obs))
                out[name] = BranchResult(
                    variant=name,
                    start_hash=snapshot.state_hash,
                    end_hash=res.state_hash,
                    outcome=EpisodeOutcome(score=res.reward, steps=1),
                )
            return out

    class ToyEpisodeReplayer:
        def evaluate_policy(
            self,
            episodes: Sequence[EpisodeRecord],
            policy: Callable[[EpisodeRecord], str],
        ) -> Sequence[EpisodeOutcome]:
            return [ep.outcomes[policy(ep)] for ep in episodes]

    assert isinstance(ToyBrancher(), BranchingReplay)
    replayer = ToyEpisodeReplayer()
    assert isinstance(replayer, EpisodeReplay)
    eps = [
        EpisodeRecord(
            episode_id="ep1",
            seed=1,
            outcomes={"maker": EpisodeOutcome(score=0.5), "frontier": EpisodeOutcome(score=1.0)},
        )
    ]
    assert replayer.evaluate_policy(eps, lambda ep: "frontier")[0].score == 1.0
