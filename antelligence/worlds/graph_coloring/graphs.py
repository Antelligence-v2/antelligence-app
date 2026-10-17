"""Seeded graph generators for the coloring world (no networkx dependency).

The three families follow AgentsNet (https://github.com/floriangroetschla/AgentsNet, MIT, utils.py):
connected Watts-Strogatz (k=4, p=0.4), Barabasi-Albert (m=2) and a Delaunay triangulation of uniform
points. Same parameters, but our own deterministic implementations: ``random.Random(seed)`` for WS/BA and
``numpy.random.default_rng(seed)`` + ``scipy.spatial.Delaunay`` for the triangulation, so a seed gives
one graph on every machine. Nodes are ``0..n-1``; every graph also gets 2-D positions for replay frames.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

FAMILIES = ("ws", "ba", "dt")  # Watts-Strogatz, Barabasi-Albert, Delaunay triangulation
Edge = Tuple[int, int]


@dataclass(frozen=True)
class Graph:
    family: str
    n: int
    edges: Tuple[Edge, ...]  # sorted, u < v
    positions: Tuple[Tuple[float, float], ...]

    def neighbours(self) -> Dict[int, List[int]]:
        adj: Dict[int, Set[int]] = {i: set() for i in range(self.n)}
        for u, v in self.edges:
            adj[u].add(v)
            adj[v].add(u)
        return {i: sorted(s) for i, s in adj.items()}

    @property
    def max_degree(self) -> int:
        return max(len(v) for v in self.neighbours().values())


def _edge(u: int, v: int) -> Edge:
    return (u, v) if u < v else (v, u)


def _circle(n: int) -> Tuple[Tuple[float, float], ...]:
    return tuple((round(0.5 + 0.45 * math.cos(2 * math.pi * i / n), 4),
                  round(0.5 + 0.45 * math.sin(2 * math.pi * i / n), 4)) for i in range(n))


def _connected(n: int, edges: Set[Edge]) -> bool:
    adj: Dict[int, List[int]] = {i: [] for i in range(n)}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    seen, stack = {0}, [0]
    while stack:
        for w in adj[stack.pop()]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return len(seen) == n


def watts_strogatz(n: int, seed: int, k: int = 4, p: float = 0.4) -> Graph:
    """Ring lattice (k nearest neighbours), each clockwise edge rewired with probability p; retried until connected."""
    rng = random.Random(seed)
    for _ in range(100):
        edges: Set[Edge] = {_edge(i, (i + j) % n) for i in range(n) for j in range(1, k // 2 + 1)}
        for j in range(1, k // 2 + 1):
            for u in range(n):
                v = (u + j) % n
                if rng.random() < p and _edge(u, v) in edges:
                    free = [w for w in range(n) if w != u and _edge(u, w) not in edges]
                    if free:
                        edges.discard(_edge(u, v))
                        edges.add(_edge(u, rng.choice(free)))
        if _connected(n, edges):
            return Graph("ws", n, tuple(sorted(edges)), _circle(n))
    raise RuntimeError("no connected Watts-Strogatz graph found")


def barabasi_albert(n: int, seed: int, m: int = 2) -> Graph:
    """Preferential attachment: each new node attaches to m distinct existing nodes, degree-proportionally."""
    rng = random.Random(seed)
    edges: Set[Edge] = set()
    targets = list(range(m))
    repeated: List[int] = []
    for new in range(m, n):
        for t in targets:
            edges.add(_edge(new, t))
        repeated.extend(targets)
        repeated.extend([new] * m)
        chosen: Set[int] = set()
        while len(chosen) < m:
            chosen.add(rng.choice(repeated))
        targets = sorted(chosen)
    return Graph("ba", n, tuple(sorted(edges)), _circle(n))


def delaunay(n: int, seed: int) -> Graph:
    """Delaunay triangulation of n uniform random points in the unit square."""
    import numpy as np
    from scipy.spatial import Delaunay

    points = np.random.default_rng(seed).random((n, 2))
    edges: Set[Edge] = set()
    for simplex in Delaunay(points).simplices:
        for i in range(3):
            edges.add(_edge(int(simplex[i]), int(simplex[(i + 1) % 3])))
    return Graph("dt", n, tuple(sorted(edges)), tuple((round(float(x), 4), round(float(y), 4)) for x, y in points))


def make_graph(family: str, n: int, seed: int) -> Graph:
    if family == "ws":
        return watts_strogatz(n, seed)
    if family == "ba":
        return barabasi_albert(n, seed)
    if family == "dt":
        return delaunay(n, seed)
    raise ValueError(f"unknown graph family {family!r}")


def family_for_seed(seed: int) -> str:
    """Round-robin by seed: seed % 3 -> ws, ba, dt."""
    return FAMILIES[seed % len(FAMILIES)]
