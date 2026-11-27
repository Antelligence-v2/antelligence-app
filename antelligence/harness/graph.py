"""Execution graph: tools wired by dependencies, with optional ``when=`` conditions for escalation branches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from antelligence.harness.core import Artifact

When = Callable[[Mapping[str, Artifact]], bool]


@dataclass(frozen=True)
class Node:
    tool: str
    deps: Tuple[str, ...] = ()
    when: Optional[When] = None


class ExecutionGraph:
    """A DAG per task. A node runs once all its deps are resolved (done or skipped).

    * ``when(done_deps)`` receives the artifacts of the node's *finished* deps; False skips the node.
    * Without an explicit ``when``, a node whose dep was skipped is skipped too. With a ``when`` it decides alone
      (skipped deps are simply absent), so "escalate if maker bad OR checker fails" is expressible.
    * Deps that become ready together run in parallel.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}

    def add(self, tool: str, deps: Sequence[str] = (), when: Optional[When] = None) -> "ExecutionGraph":
        if tool in self.nodes:
            raise ValueError(f"node already in graph: {tool}")
        missing = [d for d in deps if d not in self.nodes]
        if missing:  # deps must be added first, which also makes cycles impossible
            raise ValueError(f"{tool}: unknown deps {missing} (add dependencies first)")
        self.nodes[tool] = Node(tool, tuple(deps), when)
        return self

    def order(self, tool: str) -> int:
        return list(self.nodes).index(tool)

    def resolve(self, done: Mapping[str, Artifact], skipped: Set[str], started: Set[str]) -> Tuple[List[str], List[str]]:
        """Given a task's state, return ``(ready, newly_skipped)``. ``started`` = queued, running, done or skipped."""
        skips = set(skipped)
        ready: List[str] = []
        new_skips: List[str] = []
        progress = True
        while progress:
            progress = False
            for name, node in self.nodes.items():
                if name in started or name in skips or name in ready:
                    continue
                if any(d not in done and d not in skips for d in node.deps):
                    continue
                finished = {d: done[d] for d in node.deps if d in done}
                cascade = node.when is None and any(d in skips for d in node.deps)
                if cascade or (node.when is not None and not node.when(finished)):
                    skips.add(name)
                    new_skips.append(name)
                    progress = True
                else:
                    ready.append(name)
        return ready, new_skips
