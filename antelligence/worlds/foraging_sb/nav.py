"""Navigation and per-agent map memory shared by the world, the sensor and the scripts.

Coordinates are ``(x, y)``: x grows east, y grows south ("north" is up, as in SwarmBench's UP).
Map characters: ``#`` wall, ``.`` free ground, ``F`` food, ``N`` nest, ``?`` never seen.

The memory is what one agent has *perceived*: cells are written where the agent believes they are
(its true position plus the offset it saw). When the sensor is flipped (variant v2) those beliefs are
wrong, which is exactly how a script that trusts its memory fails.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

Cell = Tuple[int, int]

DIRS: Dict[str, Cell] = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
ORDER = ("north", "east", "south", "west")
VIEW = 5  # egocentric view is VIEW x VIEW cells, the agent in the middle
RADIUS = VIEW // 2


def compass(dx: int, dy: int) -> str:
    """Eight-way direction word for an offset (south is +y)."""
    ns = "north" if dy < 0 else "south" if dy > 0 else ""
    ew = "east" if dx > 0 else "west" if dx < 0 else ""
    return f"{ns}-{ew}" if ns and ew else ns or ew or "here"


def relative(dx: int, dy: int) -> str:
    """Words for an offset: '3 north, 2 east'; 'here' for zero."""
    parts = []
    if dy:
        parts.append(f"{abs(dy)} {'north' if dy < 0 else 'south'}")
    if dx:
        parts.append(f"{abs(dx)} {'east' if dx > 0 else 'west'}")
    return ", ".join(parts) or "here"


class MapMemory:
    """What one agent has seen: a sticky map plus the food and nest cell it remembers.

    ``sticky`` memory (the world's) keeps the food and nest cell the agent was briefed on (or first saw) and only
    moves it when the agent actually picks up or drops there (``refresh``); seeing the spot empty never clears it.
    Non-sticky memory (a script's own) follows the latest sighting.
    """

    def __init__(self, width: int, height: int, sticky: bool = True) -> None:
        self.width, self.height, self.sticky = width, height, sticky
        self.rows: List[List[str]] = [["?"] * width for _ in range(height)]
        self.food_at: Optional[Cell] = None
        self.nest_at: Optional[Cell] = None

    def update(self, pos: Cell, view: Sequence[str]) -> Tuple[Optional[Cell], Optional[Cell]]:
        """Write one perceived view; returns the food and nest cells seen in it (nearest first)."""
        foods: List[Tuple[int, int, int, Cell]] = []
        nests: List[Tuple[int, int, int, Cell]] = []
        for r, row in enumerate(view):
            for c, ch in enumerate(row):
                cell = (pos[0] + c - RADIUS, pos[1] + r - RADIUS)
                if ch == "*" or not (0 <= cell[0] < self.width and 0 <= cell[1] < self.height):
                    continue
                dist = abs(c - RADIUS) + abs(r - RADIUS)
                if ch == "W":
                    self.rows[cell[1]][cell[0]] = "#"
                elif ch in "FN":
                    self.rows[cell[1]][cell[0]] = ch
                    (foods if ch == "F" else nests).append((dist, cell[1], cell[0], cell))
                elif self.rows[cell[1]][cell[0]] not in "FN":  # food/nest cells stay remembered if later seen empty
                    self.rows[cell[1]][cell[0]] = "."
        seen_food = min(foods)[3] if foods else None
        seen_nest = min(nests)[3] if nests else None
        if seen_food and (not self.sticky or self.food_at is None):
            self.food_at = seen_food
        if seen_nest and (not self.sticky or self.nest_at is None):
            self.nest_at = seen_nest
        return seen_food, seen_nest

    def refresh(self, food: Optional[Cell] = None, nest: Optional[Cell] = None) -> None:
        """Use confirms a spot: the agent just picked up at ``food`` or dropped at ``nest``."""
        self.food_at = food or self.food_at
        self.nest_at = nest or self.nest_at

    def as_rows(self) -> List[str]:
        return ["".join(r) for r in self.rows]


def _step(order: Sequence[str], rot: int) -> List[str]:
    return [order[(i + rot) % 4] for i in range(4)]


def first_step(rows: Sequence[str], start: Cell, is_goal: Callable[[Cell, str], bool], *, rot: int = 0,
               blocked: Optional[Set[Cell]] = None, unknown_ok: bool = True) -> Optional[str]:
    """Shortest path first move to the nearest goal cell, or None. ``rot`` rotates the tie-break order.

    Walls, food and nest cells block; unknown cells are passable when ``unknown_ok`` (optimistic exploration).
    A goal cell is tested when it is dequeued; the start itself is never a goal.
    """
    height, width = len(rows), len(rows[0])
    walkable = ".?" if unknown_ok else "."
    seen = {start}
    queue = deque([(start, None)])
    order = _step(ORDER, rot)
    while queue:
        cell, first = queue.popleft()
        if cell != start and is_goal(cell, rows[cell[1]][cell[0]]):
            return first
        for name in order:
            dx, dy = DIRS[name]
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt in seen or not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            ch = rows[nxt[1]][nxt[0]]
            if ch not in walkable or (blocked and nxt in blocked):
                continue
            seen.add(nxt)
            queue.append((nxt, first or name))
    return None


def next_to(cell: Cell) -> Set[Cell]:
    return {(cell[0] + dx, cell[1] + dy) for dx, dy in DIRS.values()}


def distances(rows: Sequence[str], goals: Set[Cell]) -> Dict[Cell, int]:
    """Steps from every walkable (free or unseen) cell to the nearest goal, walking around walls, food and nest."""
    height, width = len(rows), len(rows[0])
    dist = {g: 0 for g in goals}
    queue = deque(goals)
    while queue:
        cell = queue.popleft()
        for dx, dy in DIRS.values():
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt in dist or not (0 <= nxt[0] < width and 0 <= nxt[1] < height) or rows[nxt[1]][nxt[0]] not in ".?":
                continue
            dist[nxt] = dist[cell] + 1
            queue.append(nxt)
    return dist


def _descend(dist: Dict[Cell, int], pos: Cell, occupied: Set[Cell], rot: int) -> Optional[str]:
    """A move that gets closer; the first one onto an empty cell, else the first one at all (a push)."""
    here = dist.get(pos)
    options = []
    for name in _step(ORDER, rot):
        nxt = (pos[0] + DIRS[name][0], pos[1] + DIRS[name][1])
        if nxt in dist and (here is None or dist[nxt] < here):
            options.append((nxt in occupied, len(options), name))
    return min(options)[2] if options else None


def ring_of(view: Sequence[str]) -> Dict[str, str]:
    """What is in the four cells next to the agent, from a perceived view."""
    return {name: view[RADIUS + dy][RADIUS + dx] for name, (dx, dy) in DIRS.items()}


def unstick(route: str, stuck: int, view: Sequence[str], seed: int) -> str:
    """Break traffic jams: step aside (to a free neighbour picked by ``seed``) after two failed moves, or half
    the time when another agent is in the way; otherwise keep ``route``. Deterministic given ``seed``."""
    if route not in DIRS:
        return route
    ring = ring_of(view)
    free = [n for n, ch in ring.items() if ch == "." and n != route]
    yield_now = stuck >= 2 or (ring[route].isdigit() and (seed >> 3) % 2 == 0)
    return free[seed % len(free)] if yield_now and free else route


def plan_route(rows: Sequence[str], pos: Cell, carrying: bool, food_at: Optional[Cell], nest_at: Optional[Cell],
               occupied: Sequence[Cell] = (), rot: int = 0) -> Tuple[str, str]:
    """(action, mode) for the shortest-path script. mode: to_nest | to_food | explore | at_target
    (next to the target: ``drop`` when carrying, else ``pick_up``).

    Heads for the remembered nest when carrying, else the remembered food; explores toward the nearest
    never-seen cell when the target is unknown or unreachable. The path ignores other agents (a fixed
    distance map, so plans do not flip-flop); among equally good moves it prefers an empty cell.
    """
    target = nest_at if carrying else food_at
    mode = "to_nest" if carrying else "to_food"
    busy = set(occupied)
    if target is not None:
        near = next_to(target)
        if pos in near:
            return ("drop" if carrying else "pick_up"), "at_target"
        dist = distances(rows, {c for c in near if 0 <= c[0] < len(rows[0]) and 0 <= c[1] < len(rows)
                                 and rows[c[1]][c[0]] in ".?"})
        step = _descend(dist, pos, busy, rot) if pos in dist else None
        if step:
            return step, mode
    unseen = {(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "?"}
    dist = distances(rows, unseen)
    step = _descend(dist, pos, busy, rot) if pos in dist else None
    return (step, "explore") if step else ("stay", "explore")
