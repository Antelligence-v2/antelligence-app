"""E13 chain-prioritized foraging fixtures, ported verbatim.

Source: ``docs/research/desci-paper-20260915/e13-chain/run_pilot.py``
(``env_for``, ``sweep_path``, ``step_toward``, ``oracle_check``). The random
call sequence is unchanged, so seed N here generates exactly the E13 fixture
for seed N; ``oracle_check`` reproduces ``e13-chain/oracle.json``.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

Pos = Tuple[int, int]

WIDTH = HEIGHT = 10
VIEW_K = 5
STEPS = 120
N_FOOD = 3
AGENTS = 3
SEEDS = tuple(range(101, 121))
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def env_for(seed: int, *, width: int = WIDTH, height: int = HEIGHT, agents: int = AGENTS,
            n_food: int = N_FOOD) -> Tuple[List[Pos], Pos, List[Pos], Dict[Pos, int]]:
    rng = random.Random(seed)
    starts = [(rng.randrange(width), rng.randrange(height)) for _ in range(agents)]
    nest = (rng.randrange(width), rng.randrange(height))
    foods: List[Pos] = []
    while len(foods) < n_food:
        f = (rng.randrange(width), rng.randrange(height))
        if f != nest and f not in foods and f not in starts and \
           all(max(abs(f[0] - s[0]), abs(f[1] - s[1])) > 2 for s in starts):
            foods.append(f)
    return starts, nest, foods, {f: i for i, f in enumerate(foods)}


def sweep_path(start: Pos, *, width: int = WIDTH, height: int = HEIGHT) -> List[Pos]:
    rows = sorted(range(height), key=lambda y: (abs(y - start[1]), y))
    path: List[Pos] = []
    for i, y in enumerate(rows):
        row = list(range(width))
        if i % 2:
            row.reverse()
        path.extend((x, y) for x in row)
    return path


def step_toward(pos: Pos, target: Pos) -> Optional[str]:
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    if dx == 0 and dy == 0:
        return None
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "S" if dy > 0 else "N"


def oracle_check(seed: int, steps: int = STEPS) -> Tuple[bool, Optional[int]]:
    """Perfect-knowledge solvability oracle (sequential agents, as in E13)."""
    starts, nest, foods, food_index = env_for(seed)
    by_index = {i: f for f, i in food_index.items()}
    positions = {a: starts[a] for a in range(AGENTS)}
    carrying: Dict[int, set] = {a: set() for a in range(AGENTS)}
    remaining = list(foods)
    delivered = next_needed = 0
    for step in range(steps):
        for a in range(AGENTS):
            pos = positions[a]
            carries_next = any(food_index[c] == next_needed for c in carrying[a])
            wanted = by_index[next_needed]
            target = nest if carries_next or wanted not in remaining else wanted
            move = step_toward(pos, target)
            positions[a] = (pos[0] + DIRS[move][0], pos[1] + DIRS[move][1]) if move else target
            if positions[a] in remaining:
                remaining.remove(positions[a])
                carrying[a].add(positions[a])
            if positions[a] == nest and carrying[a]:
                while True:
                    drop = next((c for c in carrying[a] if food_index[c] == next_needed), None)
                    if drop is None:
                        break
                    carrying[a].remove(drop)
                    delivered += 1
                    next_needed += 1
                    if delivered == N_FOOD:
                        return True, step + 1
                    if any(food_index[c] == next_needed for c in carrying[a]):
                        continue
                    break
    return False, None
