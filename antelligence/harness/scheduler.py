"""Event-driven scheduler.

Ready work is bucketed by ``model_key`` in ``ready_by_model``. Hosted tools launch the moment they are ready
(bounded by ``max_hosted``). A *local* model is expensive to load, so exactly one is loaded at a time and it is drained
question-major (lowest task first) by at most ``workers`` (<= 4) concurrent calls before the next model is swapped in.
Completions are events: each one may unlock more work for the loaded model before any swap happens.
"""

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from antelligence.harness.core import Artifact, Task, ToolRegistry, ToolSpec
from antelligence.harness.graph import ExecutionGraph
from antelligence.providers.base import ProviderError

MAX_LOCAL_WORKERS = 4


class LiveBox:
    """Runs tools for real. :class:`~antelligence.harness.replay.ReplayBox` is the drop-in that replays them."""

    async def run(self, spec: ToolSpec, task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        return await spec.run(task, deps)


@dataclass
class RunStats:
    swaps: int = 0                       # local model loads, including the first
    swap_log: List[str] = field(default_factory=list)
    peak_local: int = 0
    peak_hosted: int = 0


@dataclass
class RunResult:
    artifacts: Dict[str, Dict[str, Artifact]]
    skipped: Dict[str, Set[str]]
    stats: RunStats


async def run_graph(tasks: Sequence[Task], graph: ExecutionGraph, registry: ToolRegistry, *, box: Any = None,
                    workers: int = MAX_LOCAL_WORKERS, max_hosted: int = 32) -> RunResult:
    if not 1 <= workers <= MAX_LOCAL_WORKERS:
        raise ValueError(f"workers must be 1..{MAX_LOCAL_WORKERS}")
    box = box or LiveBox()
    for name in graph.nodes:
        registry.get(name)  # fail early on unknown tools
    by_id = {t.id: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("duplicate task ids")
    index = {t.id: i for i, t in enumerate(tasks)}
    done: Dict[str, Dict[str, Artifact]] = {t.id: {} for t in tasks}
    skipped: Dict[str, Set[str]] = {t.id: set() for t in tasks}
    started: Dict[str, Set[str]] = {t.id: set() for t in tasks}
    ready_by_model: Dict[str, List[Tuple[int, int, str]]] = {}
    stats = RunStats()
    running: Dict["asyncio.Task[Artifact]", Tuple[str, str, bool]] = {}
    sem = asyncio.Semaphore(max_hosted)
    loaded: Optional[str] = None

    def settle(tid: str) -> None:
        ready, new_skips = graph.resolve(done[tid], skipped[tid], started[tid])
        skipped[tid].update(new_skips)
        started[tid].update(new_skips)
        for tool in ready:
            started[tid].add(tool)
            heapq.heappush(ready_by_model.setdefault(registry.get(tool).model_key or "", []),
                           (index[tid], graph.order(tool), tool))

    async def execute(task: Task, spec: ToolSpec, local: bool) -> Artifact:
        deps = {d: done[task.id][d] for d in graph.nodes[spec.name].deps if d in done[task.id]}
        try:
            if local:
                return await box.run(spec, task, deps)
            async with sem:
                return await box.run(spec, task, deps)
        except ProviderError as exc:  # an honest failed step; anything else is a bug and propagates
            return Artifact(task.id, spec.name, answer=None, format_ok=False, calls=1,
                            error=f"{type(exc).__name__}: {exc}")

    def launch(model: str, local: bool) -> None:
        task_idx, _, tool = heapq.heappop(ready_by_model[model])
        tid = tasks[task_idx].id
        fut = asyncio.ensure_future(execute(by_id[tid], registry.get(tool), local))
        running[fut] = (tid, tool, local)
        stats.peak_local = max(stats.peak_local, sum(1 for v in running.values() if v[2]))
        stats.peak_hosted = max(stats.peak_hosted, sum(1 for v in running.values() if not v[2]))

    def dispatch() -> None:
        nonlocal loaded
        for model, heap in ready_by_model.items():  # hosted (or model-less) work never waits
            if heap and not registry.get(heap[0][2]).local:
                while heap:
                    launch(model, False)
        n_local = sum(1 for v in running.values() if v[2])
        if (loaded is None or not ready_by_model.get(loaded)) and n_local == 0:
            cands = [(h[0], m) for m, h in ready_by_model.items() if h]
            if cands:
                nxt = min(cands)[1]
                if nxt != loaded:
                    stats.swaps += 1
                    stats.swap_log.append(nxt)
                loaded = nxt
        while loaded and ready_by_model.get(loaded) and n_local < workers:
            launch(loaded, True)
            n_local += 1

    for t in tasks:
        settle(t.id)
    try:
        while True:
            dispatch()
            if not running:
                break
            finished, _ = await asyncio.wait(list(running), return_when=asyncio.FIRST_COMPLETED)
            for fut in finished:
                tid, tool, _local = running.pop(fut)
                done[tid][tool] = fut.result()
                settle(tid)
    finally:
        for fut in running:
            fut.cancel()
    return RunResult(done, skipped, stats)
