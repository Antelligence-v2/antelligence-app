"""Tumor world: nanobots coordinating against a synthetic 2D glioblastoma.

The world owns physics (:class:`TumorPhysics`) and every nanobot's *body*
(position, payload, mission state). Policies own *decisions*:

* ``target``  — lock onto a living cell the bot can currently sense;
* ``move``    — step in a chosen direction (search/exploration);
* ``advance`` — continue the current mission (approach, deliver, return to a
  vessel, reload), with the legacy mission mechanics unchanged;
* ``noop``.

Observations are local: cells within ``sense_radius``, local concentrations
and gradients, the bot's own body state, and static anatomy (tumor outline
and vessel positions, as imaging would provide). A bot never sees the whole
tumor. An optional ``queen`` agent has no body: it perceives only signals
(reports) within the whole domain and may emit, not act.

Synthetic research model only; not clinical software.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.frames import encode_field
from antelligence.kernel.types import Intent, Observation, Outcome
from antelligence.worlds.tumor.physics import TumorPhysics

SEARCHING, TARGETING, DELIVERING, RETURNING, RELOADING = "searching", "targeting", "delivering", "returning", "reloading"
QUEEN = "queen"
ZONE = 50.0  # µm; evidence about "where tumor cells are" is kept per 50 µm zone


def zone_subject(pos: Tuple[float, float]) -> str:
    return f"zone:{int(pos[0] // ZONE)},{int(pos[1] // ZONE)}"


def zone_center(subject: str) -> Tuple[float, float]:
    x, y = subject.split(":", 1)[1].split(",")
    return (int(x) + 0.5) * ZONE, (int(y) + 0.5) * ZONE


@dataclass
class Body:
    position: np.ndarray
    payload: float = 20.0
    max_payload: float = 20.0
    speed: float = 30.0
    state: str = SEARCHING
    target_cell: Optional[int] = None
    target_vessel: Optional[int] = None
    deliveries: int = 0
    drug_delivered: float = 0.0
    previous_direction: np.ndarray = field(default_factory=lambda: np.zeros(2))


class TumorWorld:
    def __init__(
        self,
        seed: int,
        *,
        n_nanobots: int = 10,
        max_steps: int = 100,
        domain_size: float = 600.0,
        tumor_radius: float = 200.0,
        cell_density: float = 0.001,
        vessel_density: float = 0.01,
        chemical_pheromones: bool = False,
        sense_radius: float = 100.0,
        hearing: float = 0.0,
        queen: bool = False,
        legacy_payload_deadlock: bool = False,
        dimensionality: int = 2,
    ) -> None:
        if dimensionality not in (2, 3):
            raise ValueError("dimensionality must be 2 or 3")
        # 3D keeps the same world size but a coarser voxel grid (31^3) and a
        # per-volume cell density giving a cell count similar to the 2D disk.
        self.dim = dimensionality
        if dimensionality == 3 and cell_density == 0.001:
            cell_density = 4e-6
        # Legacy bots returned to reload only when payload < 2.0 but could only
        # target when payload > 2.0; 20 - 6 x 3 = exactly 2.0, so after one payload
        # every bot searched forever. The engine returns at <= 2.0. Set True only
        # to reproduce legacy numbers.
        self.legacy_payload_deadlock = legacy_payload_deadlock
        self.seed = seed
        self.n_nanobots = n_nanobots
        self.max_steps = max_steps
        self.sense_radius = sense_radius
        self.hearing = hearing
        self.queen = queen
        self.config = dict(domain_size=domain_size, tumor_radius=tumor_radius, cell_density=cell_density,
                           vessel_density=vessel_density, chemical_pheromones=chemical_pheromones)
        self.physics = TumorPhysics(seed=seed, dimensionality=dimensionality,
                                    voxel_size=10.0 if dimensionality == 2 else 20.0, **self.config)
        self.domain = (0.0, domain_size)
        g = self.physics.geometry
        self.center = tuple(float(g.center[i]) for i in range(self.dim))
        self.tumor_radius = float(g.tumor_radius)
        self.vessels = [tuple(float(v.position[i]) for i in range(self.dim)) for v in g.vessels]
        self.bodies: Dict[str, Body] = {}
        with self.physics.rng():
            for i in range(n_nanobots):
                if self.vessels:
                    vessel = random.choice(self.vessels)  # same draws as the legacy NanobotAgent
                    offset = np.random.randn(self.dim) * 20.0
                    pos = np.array([vessel[k] + offset[k] for k in range(self.dim)])
                else:
                    pos = np.random.uniform(0, domain_size, size=self.dim)
                self.bodies[f"bot-{i:03d}"] = Body(position=pos, previous_direction=np.zeros(self.dim))
        self._revision = 0
        self.cleared_at: Optional[int] = None
        self._living_sum = 0
        self._living_ticks = 0
        self.half_cleared_at: Optional[int] = None
        self.counters = {"search_moves": 0, "duplicate_targets": 0, "invalid_actions": 0, "idle": 0}
        self._prepared_tick: Optional[int] = None

    def _ensure_prepared(self, tick: int) -> None:
        """Cells/immune/vessels update once per tick, before any bot acts (legacy order)."""
        if self._prepared_tick != tick:
            self._prepared_tick = tick
            self.physics.prepare()

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self.bodies) + ([QUEEN] if self.queen else [])

    def describe(self) -> Dict[str, Any]:
        return {"world": "tumor", "version": 1, "seed": self.seed, "n_nanobots": self.n_nanobots,
                "max_steps": self.max_steps, "sense_radius": self.sense_radius, "hearing": self.hearing,
                "queen": self.queen, "legacy_payload_deadlock": self.legacy_payload_deadlock, **self.config,
                **({"dimensionality": 3} if self.dim == 3 else {})}

    # ---------------------------------------------------------- visualization
    FRAME_FIELDS = ("drug", "oxygen", "trail_pheromone", "alarm_pheromone", "recruitment_pheromone")
    FRAME_STRIDE = 2  # 61x61 voxel grid -> 31x31 per frame

    def _frame_stride(self) -> int:
        return self.FRAME_STRIDE if self.dim == 2 else 1  # 3D grid is already 31 wide

    def _field_plane(self, name: str) -> np.ndarray:
        values = self.physics.microenv.get_substrate(name).concentration
        return values[:, :, values.shape[2] // 2] if self.dim == 3 else values

    def _frame_fields(self) -> List[str]:
        return [name for name in self.FRAME_FIELDS if self.physics.microenv.get_substrate(name) is not None]

    def scene(self) -> Dict[str, Any]:
        """Static layout for renderers (read-only)."""
        env = self.physics.microenv
        stride = self._frame_stride()
        shape = [len(range(0, env.nx, stride)), len(range(0, env.ny, stride))]
        return {"kind": "tumor", "units": "um", "dimensionality": self.dim, "domain": list(self.domain),
                "center": list(self.center), "tumor_radius": self.tumor_radius,
                "vessels": [[round(c, 1) for c in v] for v in self.vessels],
                # 3D fields are recorded as the horizontal slice through the tumor center.
                "field_slice_z": self.center[2] if self.dim == 3 else None,
                "field_shape": shape, "field_spacing": env.dx * stride, "fields": self._frame_fields(),
                "bot_states": [SEARCHING, TARGETING, DELIVERING, RETURNING, RELOADING],
                "cell_phases": ["viable", "hypoxic", "necrotic", "apoptotic"]}

    def snapshot(self) -> Dict[str, Any]:
        """Dynamic state at the end of a tick (read-only: no RNG, no mutation)."""
        states = {s: i for i, s in enumerate((SEARCHING, TARGETING, DELIVERING, RETURNING, RELOADING))}
        phases = {"viable": 0, "hypoxic": 1, "necrotic": 2, "apoptotic": 3}
        # Row layout is stable for 2D renderers: z (3D only) is appended last.
        z = (lambda p: [round(float(p[2]), 1)]) if self.dim == 3 else (lambda p: [])
        bots = [[round(float(b.position[0]), 1), round(float(b.position[1]), 1), states.get(b.state, 0),
                 round(b.payload, 1), b.target_cell, *z(b.position)] for _, b in sorted(self.bodies.items())]
        cells = [[round(float(c.position[0]), 1), round(float(c.position[1]), 1), phases.get(c.phase.value, 0), c.cell_id,
                  *z(c.position)] for c in self.physics.geometry.tumor_cells]
        fields = {name: encode_field(self._field_plane(name), self._frame_stride()) for name in self._frame_fields()}
        return {"bots": bots, "cells": cells, "fields": fields}

    def observe(self, agent_id: str, tick: int) -> Observation:
        self._ensure_prepared(tick)
        if agent_id == QUEEN:
            return Observation({"role": QUEEN}, SenseQuery(pos=self.center, radius=self.domain[1] * 2))
        body = self.bodies[agent_id]
        pos = tuple(float(body.position[i]) for i in range(self.dim))
        cells = sorted(self.physics.cells_near(pos, self.sense_radius),
                       key=lambda c: (sum((c.position[i] - pos[i]) ** 2 for i in range(self.dim)), c.cell_id))
        target = self.physics.cell(body.target_cell) if body.target_cell is not None else None
        gradients = {"oxygen": _round2(self.physics.gradient("oxygen", pos))}
        if self.config["chemical_pheromones"]:
            for name in ("trail_pheromone", "alarm_pheromone", "recruitment_pheromone"):
                gradients[name] = _round2(self.physics.gradient(name, pos))
        data = {
            "role": "nanobot",
            "pos": [round(p, 3) for p in pos],
            "state": body.state,
            "payload": round(body.payload, 3),
            "max_payload": body.max_payload,
            "target": None if target is None or not target.is_alive else
            {"id": target.cell_id, "pos": [round(target.position[i], 3) for i in range(self.dim)]},
            "previous_direction": _round2(body.previous_direction),
            "cells": [{"id": c.cell_id, "pos": [round(c.position[i], 3) for i in range(self.dim)],
                       "phase": c.phase.value, "type": c.cell_type.value,
                       "resistance": round(float(c.resistance_level), 4)} for c in cells[:24]],
            "gradients": gradients,
            "inside_tumor": self._dist(pos, self.center) <= self.tumor_radius,
            "anatomy": {"tumor_center": list(self.center), "tumor_radius": self.tumor_radius,
                        "vessels": [list(v) for v in self.vessels]},
        }
        sense = SenseQuery(pos=pos, radius=self.hearing) if self.hearing > 0 else SenseQuery(pos=pos, kinds=frozenset())
        return Observation(data, sense)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        self._ensure_prepared(tick)
        if agent_id == QUEEN:
            return Outcome(intent.action == "noop", None if intent.action == "noop" else "queen_cannot_act")
        body = self.bodies[agent_id]
        if body.state == SEARCHING and not self.legacy_payload_deadlock and body.payload <= 2.0:
            # A bot that can no longer target spends its turn heading back to reload
            # (same as the fixed legacy NanobotAgent._search_for_target).
            self._start_return(body)
            return Outcome(True, "reload_required", effects={"state": RETURNING})
        if intent.action == "noop":
            self.counters["idle"] += 1
            return Outcome(True)
        if intent.action == "advance":
            return self._advance(body)
        if intent.action == "target":
            return self._target(agent_id, body, intent.params.get("cell_id"))
        if intent.action == "move":
            return self._move(body, intent.params.get("direction"))
        self.counters["invalid_actions"] += 1
        return Outcome(False, "unknown_action")

    def step_environment(self, tick: int) -> None:
        self._ensure_prepared(tick)
        self.physics.diffuse()
        living = len(self.physics.living_cells())
        self._living_sum += living
        self._living_ticks += 1
        if self.half_cleared_at is None and living <= self.physics.initial_living / 2:
            self.half_cleared_at = tick
        if self.cleared_at is None and living == 0:
            self.cleared_at = tick

    def metrics(self) -> Dict[str, Any]:
        stats = self.physics.statistics()
        total, living = stats["total_cells"], stats["living_cells"]
        initial = self.physics.initial_living
        return {
            "kill_rate": (total - living) / total if total else 0.0,
            "net_reduction_pct": 100.0 * (initial - living) / initial if initial else 0.0,
            "initial_living_cells": initial,
            "cleared": self.cleared_at is not None,
            # Area under the living-cell curve per tick: lower means the tumor shrank faster.
            "mean_living_cells": (round(self._living_sum / self._living_ticks, 6) if self._living_ticks
                                  else float(stats["living_cells"])),
            "cleared_at": self.cleared_at,
            "half_cleared_at": self.half_cleared_at,
            **stats,
            "deliveries": sum(b.deliveries for b in self.bodies.values()),
            "drug_delivered": round(sum(b.drug_delivered for b in self.bodies.values()), 6),
            **self.counters,
        }

    def done(self, tick: int) -> bool:
        return tick >= self.max_steps or not self.physics.living_cells()

    # ------------------------------------------------------------ mechanics
    def _target(self, agent_id: str, body: Body, cell_id: Any) -> Outcome:
        if body.state != SEARCHING:
            return Outcome(False, "busy")
        if not isinstance(cell_id, int) or isinstance(cell_id, bool):
            self.counters["invalid_actions"] += 1
            return Outcome(False, "bad_cell_id")
        cell = self.physics.cell(cell_id)
        pos = tuple(body.position[:self.dim])
        if cell is None or not cell.is_alive:
            return Outcome(False, "no_such_living_cell")
        if self._dist(pos, cell.position) > self.sense_radius:
            return Outcome(False, "cell_not_sensed")
        if body.payload <= 2.0:
            return Outcome(False, "payload_too_low")
        if any(other.target_cell == cell_id and other.state in (TARGETING, DELIVERING)
               for name, other in self.bodies.items() if name != agent_id):
            self.counters["duplicate_targets"] += 1
        body.target_cell = cell_id
        body.state = TARGETING
        return Outcome(True, effects={"targeted": cell_id})

    def _move(self, body: Body, direction: Any) -> Outcome:
        if body.state != SEARCHING:
            return Outcome(False, "busy")
        if not (isinstance(direction, list) and len(direction) == self.dim
                and all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in direction)):
            self.counters["invalid_actions"] += 1
            return Outcome(False, "bad_direction")
        d = np.array(direction, dtype=float)
        norm = np.linalg.norm(d)
        if norm == 0:
            return Outcome(False, "zero_direction")
        d /= norm
        body.position = body.position + d * body.speed
        body.previous_direction = d
        self.counters["search_moves"] += 1
        self._clamp(body)
        return Outcome(True, effects={"pos": _round2(body.position)})

    def _advance(self, body: Body) -> Outcome:
        if body.state == SEARCHING:
            self.counters["idle"] += 1
            return Outcome(True, "nothing_to_advance")
        if body.state == TARGETING:
            return self._approach(body)
        if body.state == DELIVERING:
            return self._deliver(body)
        if body.state == RETURNING:
            return self._return(body)
        return self._reload(body)

    def _approach(self, body: Body) -> Outcome:
        cell = self.physics.cell(body.target_cell) if body.target_cell is not None else None
        if cell is None or not cell.is_alive:
            body.target_cell, body.state = None, SEARCHING
            return Outcome(True, "target_lost")
        direction = np.array(cell.position[:self.dim]) - body.position
        distance = np.linalg.norm(direction)
        if distance < 30.0:
            body.state = DELIVERING
            return Outcome(True, effects={"state": DELIVERING})
        body.position = body.position + direction / distance * body.speed
        self._clamp(body)
        self.physics.deposit("trail_pheromone", tuple(body.position), 1.0)
        return Outcome(True, effects={"pos": _round2(body.position)})

    def _deliver(self, body: Body) -> Outcome:
        cell = self.physics.cell(body.target_cell) if body.target_cell is not None else None
        if cell is None or not cell.is_alive:
            body.target_cell, body.state = None, SEARCHING
            return Outcome(True, "target_lost")
        effects: Dict[str, Any] = {}
        pos = tuple(body.position)
        if body.payload > 0:
            amount = min(body.payload, 3.0)
            self.physics.deposit("drug", pos, amount)
            body.payload -= amount
            body.drug_delivered += amount
            body.deliveries += 1
            with self.physics.rng():
                killed = cell.accumulate_drug(amount)
            self.physics.deposit("trail_pheromone", pos, 3.0)
            effects["delivered"] = amount
            if killed:
                self._revision += 1
                self.physics.deposit("recruitment_pheromone", pos, 5.0)
                effects["killed"] = cell.cell_id
                effects["subjects_changed"] = [zone_subject(cell.position)]
            elif cell.resistance_level > 0.5:
                self.physics.deposit("alarm_pheromone", pos, 5.0)
        if self._needs_reload(body):
            self._start_return(body)
        return Outcome(True, effects=effects)

    def _return(self, body: Body) -> Outcome:
        if body.target_vessel is None:
            body.target_vessel = self._nearest_vessel(body)
        if body.target_vessel is None:
            body.state = SEARCHING
            return Outcome(True, "no_vessels")
        direction = np.array(self.vessels[body.target_vessel]) - body.position
        distance = np.linalg.norm(direction)
        if distance < 10.0:
            body.state = RELOADING
            return Outcome(True, effects={"state": RELOADING})
        # Stop at the vessel rather than overshoot (legacy oscillated around it forever).
        step = body.speed if self.legacy_payload_deadlock else min(body.speed, distance)
        body.position = body.position + direction / distance * step
        self._clamp(body)
        return Outcome(True, effects={"pos": _round2(body.position)})

    def _reload(self, body: Body) -> Outcome:
        body.payload = min(body.payload + 5.0, body.max_payload)
        if body.payload >= body.max_payload * 0.9:
            body.target_vessel, body.state = None, SEARCHING
        return Outcome(True, effects={"payload": body.payload})

    def _needs_reload(self, body: Body) -> bool:
        return body.payload < 2.0 if self.legacy_payload_deadlock else body.payload <= 2.0

    def _start_return(self, body: Body) -> None:
        body.target_cell = None
        body.target_vessel = self._nearest_vessel(body)
        body.state = RETURNING

    def _nearest_vessel(self, body: Body) -> Optional[int]:
        if not self.vessels:
            return None
        distances = [self._dist(body.position, v) for v in self.vessels]
        return int(np.argmin(distances))

    def _clamp(self, body: Body) -> None:
        """Legacy domain clamp + tumor-boundary rule for bots not on a mission."""
        lo, hi = self.domain
        body.position = np.clip(body.position, lo, hi)
        pos = body.position
        away = self._dist(pos, self.center)
        if away <= self.tumor_radius:
            return
        on_mission = body.state in (TARGETING, DELIVERING)
        may_be_outside = body.state in (RETURNING, RELOADING) or body.payload < 10.0
        if on_mission and body.target_cell is not None:
            cell = self.physics.cell(body.target_cell)
            if cell is not None and self._dist(cell.position, self.center) <= self.tumor_radius:
                return
        if not may_be_outside and not on_mission:
            # Legacy computed center + dir_to_center * (r - 5), which lands on the
            # *opposite* edge of the tumor. The evident intent is the nearest edge.
            outward = pos - np.array(self.center)
            outward /= np.linalg.norm(outward)
            body.position = np.array(self.center) + outward * (self.tumor_radius - 5.0)
            if body.target_cell is not None:
                body.target_cell, body.state = None, SEARCHING
        elif body.state == RETURNING:
            nearest = self._nearest_vessel(body)
            if nearest is not None:
                to_vessel = np.array(self.vessels[nearest]) - pos
                distance = np.linalg.norm(to_vessel)
                if distance > 100.0:
                    body.position = pos + to_vessel / distance * body.speed * 0.5


    def _dist(self, a, b) -> float:
        if self.dim == 2:
            return _dist(a, b)
        return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _dist(a, b) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _round2(v) -> List[float]:
    """Round a 2- or 3-component vector (name kept for the 2D-era call sites)."""
    return [round(float(c), 6) for c in v]
