"""Tests for ExecutionGraph and event-driven scheduler."""

from __future__ import annotations

import asyncio
from typing import Mapping

import pytest

from antelligence.harness.core import Artifact, Task, ToolRegistry, ToolSpec
from antelligence.harness.graph import ExecutionGraph
from antelligence.harness.scheduler import MAX_LOCAL_WORKERS, run_graph
from antelligence.providers.base import ProviderError


def test_at_most_m_local_model_swaps_on_conditional_dag():
    """With M=2 local models (m1, m2) and a conditional `when=` branch, swaps <= 2."""
    tasks = [Task(id=f"q{i}", payload={"need_m2": i % 2 == 0}) for i in range(8)]

    async def run_m1(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        await asyncio.sleep(0.005)
        return Artifact(task_id=task.id, tool="m1_step", answer="draft", calls=1)

    async def run_m2(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        await asyncio.sleep(0.005)
        return Artifact(task_id=task.id, tool="m2_step", answer="checked", calls=1)

    reg = ToolRegistry([
        ToolSpec(name="m1_step", run=run_m1, model_key="local-m1", local=True),
        ToolSpec(name="m2_step", run=run_m2, model_key="local-m2", local=True),
    ])
    graph = ExecutionGraph()
    graph.add("m1_step")
    graph.add("m2_step", deps=("m1_step",), when=lambda deps: deps["m1_step"].task_id in {"q0", "q2", "q4", "q6"})

    res = asyncio.run(run_graph(tasks, graph, reg, workers=4))
    assert res.stats.swaps <= 2
    assert res.stats.swap_log == ["local-m1", "local-m2"]
    assert res.stats.peak_local <= MAX_LOCAL_WORKERS
    for i in range(8):
        tid = f"q{i}"
        assert "m1_step" in res.artifacts[tid]
        if i % 2 == 0:
            assert "m2_step" in res.artifacts[tid]
        else:
            assert "m2_step" in res.skipped[tid]


def test_parallel_deps_execute_concurrently():
    """Two independent deps on a node run in parallel before the join node."""
    tasks = [Task(id="t1")]
    active = 0
    max_active = 0

    async def make_dep(name: str):
        async def _fn(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return Artifact(task_id=task.id, tool=name, answer=name, calls=1)

        return _fn

    async def join(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        return Artifact(
            task_id=task.id,
            tool="join",
            answer=f"{deps['dep_a'].answer}+{deps['dep_b'].answer}",
            calls=0,
        )

    async def _run():
        reg = ToolRegistry([
            ToolSpec(name="dep_a", run=await make_dep("dep_a"), model_key="api-a", local=False),
            ToolSpec(name="dep_b", run=await make_dep("dep_b"), model_key="api-b", local=False),
            ToolSpec(name="join", run=join, model_key=None, local=False),
        ])
        graph = ExecutionGraph()
        graph.add("dep_a").add("dep_b").add("join", deps=("dep_a", "dep_b"))
        return await run_graph(tasks, graph, reg)

    res = asyncio.run(_run())
    assert max_active == 2
    assert res.artifacts["t1"]["join"].answer == "dep_a+dep_b"


def test_provider_error_recorded_honestly_without_crashing():
    tasks = [Task(id="t1")]

    async def fail_fn(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        raise ProviderError("upstream timeout")

    async def downstream(task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        return Artifact(task_id=task.id, tool="fallback", answer="recovered", calls=1)

    reg = ToolRegistry([
        ToolSpec(name="primary", run=fail_fn, model_key="api", local=False),
        ToolSpec(name="fallback", run=downstream, model_key="api", local=False),
    ])
    graph = ExecutionGraph()
    graph.add("primary").add("fallback", deps=("primary",), when=lambda deps: not deps["primary"].format_ok)

    res = asyncio.run(run_graph(tasks, graph, reg))
    err_art = res.artifacts["t1"]["primary"]
    assert err_art.format_ok is False
    assert err_art.calls == 1
    assert "ProviderError" in (err_art.error or "")
    assert res.artifacts["t1"]["fallback"].answer == "recovered"


def test_workers_bounds_checked():
    with pytest.raises(ValueError, match="workers must be"):
        asyncio.run(run_graph([], ExecutionGraph(), ToolRegistry(), workers=5))
