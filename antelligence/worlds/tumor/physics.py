"""Tumor microenvironment physics, independent of any agent.

Wraps the existing ``backend.biofvm`` (diffusion/decay) and
``backend.tumor_environment`` (cells, vessels, immune cells) unchanged. The
per-step cell/immune/vessel updates are ported from
``backend.nanobot_simulation.TumorNanobotModel`` without the global knowledge
graph, blockchain calls, LLM client or environment reads.

Step order matches the legacy model cyclically::

    legacy:  reset -> cells -> immune -> vessels -> bots -> diffuse
    engine:  [prepare: reset -> cells -> immune -> vessels] -> bots (apply) -> diffuse -> [prepare next]

The legacy code draws from the global ``random``/``numpy.random`` streams.
:meth:`TumorPhysics.rng` swaps in this world's private RNG state around every
call while holding a process-wide lock, so worlds running in different threads
cannot interleave on the global streams and a seed fully determines the run.
Legacy ``print`` output is silenced per thread (:class:`_ThreadQuietStdout`),
never by replacing ``sys.stdout`` for the whole process.
"""

from __future__ import annotations

import contextlib
import random
import sys
import threading
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np

from backend.biofvm import Microenvironment, create_drug_substrate, create_oxygen_substrate, create_pheromone_substrate
from backend.tumor_environment import CellPhase, TumorCell, TumorGeometry, create_simple_tumor_environment

CHEMICAL_PHEROMONES = ("trail_pheromone", "alarm_pheromone", "recruitment_pheromone")
DEFAULT_PHEROMONE_PARAMS = {
    "trail_diffusion": 1e-6,
    "alarm_diffusion": 5e-6,
    "recruitment_diffusion": 2e-6,
    "trail_decay": 0.0693,
    "alarm_decay": 0.231,
    "recruitment_decay": 0.099,
}


_GLOBAL_RNG_LOCK = threading.RLock()


class _ThreadQuietStdout:
    """sys.stdout proxy that drops writes only from threads inside a quiet block."""

    def __init__(self, wrapped) -> None:
        self.wrapped = wrapped
        self._local = threading.local()

    @property
    def quiet(self) -> bool:
        return getattr(self._local, "depth", 0) > 0

    def enter(self) -> None:
        self._local.depth = getattr(self._local, "depth", 0) + 1

    def exit(self) -> None:
        self._local.depth -= 1

    def write(self, text: str) -> int:
        return len(text) if self.quiet else self.wrapped.write(text)

    def flush(self) -> None:
        if not self.quiet:
            self.wrapped.flush()

    def __getattr__(self, name: str):
        return getattr(self.wrapped, name)


_STDOUT_INSTALL_LOCK = threading.Lock()


def _quiet_stdout() -> _ThreadQuietStdout:
    """Install the proxy once (idempotent); later redirections by others are respected."""
    with _STDOUT_INSTALL_LOCK:
        if not isinstance(sys.stdout, _ThreadQuietStdout):
            sys.stdout = _ThreadQuietStdout(sys.stdout)
        return sys.stdout


class TumorPhysics:
    def __init__(
        self,
        *,
        seed: int,
        domain_size: float = 600.0,
        voxel_size: float = 10.0,
        tumor_radius: float = 200.0,
        cell_density: float = 0.001,
        vessel_density: float = 0.01,
        chemical_pheromones: bool = False,
        pheromone_params: Optional[Dict[str, float]] = None,
        quiet: bool = True,
    ) -> None:
        self.quiet = quiet
        self.chemical_pheromones = chemical_pheromones
        self.pheromone_params = {**DEFAULT_PHEROMONE_PARAMS, **(pheromone_params or {})}
        self._py_state = random.Random(seed).getstate()
        self._np_state = np.random.RandomState(seed % (2**32)).get_state()
        with self.rng():
            self.microenv = Microenvironment(
                x_range=(0, domain_size), y_range=(0, domain_size), z_range=(0, domain_size),
                dx=voxel_size, dy=voxel_size, dz=voxel_size, dimensionality=2,
            )
            create_oxygen_substrate(self.microenv, boundary_value=38.0)
            create_drug_substrate(self.microenv, diffusion_coeff=1e-7)
            if chemical_pheromones:
                p = self.pheromone_params
                for name, key in (("trail_pheromone", "trail"), ("alarm_pheromone", "alarm"),
                                  ("recruitment_pheromone", "recruitment")):
                    self.microenv.add_substrate(name, diffusion_coefficient=p[f"{key}_diffusion"],
                                                decay_rate=p[f"{key}_decay"], initial_value=0.0,
                                                dirichlet_boundary_value=None)
            create_pheromone_substrate(self.microenv, "chemokine_signal", decay_rate=0.08)
            create_pheromone_substrate(self.microenv, "toxicity_signal", decay_rate=0.2)
            create_pheromone_substrate(self.microenv, "ifn_gamma", decay_rate=0.05)
            create_pheromone_substrate(self.microenv, "tnf_alpha", decay_rate=0.08)
            create_pheromone_substrate(self.microenv, "perforin", decay_rate=0.12)
            self.microenv.add_substrate("drug_a", diffusion_coefficient=1e-6, decay_rate=0.05)
            self.microenv.add_substrate("drug_b", diffusion_coefficient=1e-7, decay_rate=0.05)
            self.geometry: TumorGeometry = create_simple_tumor_environment(
                domain_size=domain_size, tumor_radius=tumor_radius, cell_density=cell_density,
                dimensionality=2, vessel_density=vessel_density,
            )
        self.initial_total = len(self.geometry.tumor_cells)
        self.initial_living = len(self.geometry.get_living_cells())
        self._cells_by_id = {c.cell_id: c for c in self.geometry.tumor_cells}

    # ------------------------------------------------------------------ rng
    @contextlib.contextmanager
    def rng(self) -> Iterator[None]:
        """Run legacy code on this world's private RNG streams (and quietly).

        Holds a process-wide lock for the whole swap so no other thread can use or
        replace the global streams in between.
        """
        with _GLOBAL_RNG_LOCK:
            saved_py, saved_np = random.getstate(), np.random.get_state()
            random.setstate(self._py_state)
            np.random.set_state(self._np_state)
            stdout = _quiet_stdout() if self.quiet else None
            if stdout is not None:
                stdout.enter()
            try:
                yield
            finally:
                if stdout is not None:
                    stdout.exit()
                self._py_state, self._np_state = random.getstate(), np.random.get_state()
                random.setstate(saved_py)
                np.random.set_state(saved_np)

    # --------------------------------------------------------------- queries
    def cell(self, cell_id: int) -> Optional[TumorCell]:
        return self._cells_by_id.get(cell_id)

    def living_cells(self) -> List[TumorCell]:
        return self.geometry.get_living_cells()

    def cells_near(self, pos: Tuple[float, float], radius: float) -> List[TumorCell]:
        x, y = pos
        r2 = radius * radius
        return [c for c in self.geometry.get_living_cells()
                if (c.position[0] - x) ** 2 + (c.position[1] - y) ** 2 <= r2]

    def voxel(self, pos: Tuple[float, float]) -> Tuple[int, ...]:
        return self.microenv.position_to_voxel((pos[0], pos[1], 0.0))

    def deposit(self, substrate: str, pos: Tuple[float, float], amount: float) -> bool:
        field = self.microenv.get_substrate(substrate)
        if field is None:
            return False
        field.add_source(self.voxel(pos), amount)
        return True

    def concentration(self, substrate: str, pos: Tuple[float, float]) -> float:
        if self.microenv.get_substrate(substrate) is None:
            return 0.0
        return float(self.microenv.get_concentration_at(substrate, (pos[0], pos[1], 0.0)))

    def gradient(self, substrate: str, pos: Tuple[float, float]) -> Tuple[float, float]:
        if self.microenv.get_substrate(substrate) is None:
            return (0.0, 0.0)
        g = self.microenv.get_gradient_at(substrate, (pos[0], pos[1], 0.0))
        return (float(g[0]), float(g[1]))

    # ------------------------------------------------------------- stepping
    def prepare(self) -> None:
        """Reset sources, then cells, immune system and vessels add theirs."""
        with self.rng():
            self.microenv.reset_all_sources_sinks()
            self._update_tumor_cells()
            self._update_immune_cells()
            self._apply_vessel_sources()

    def diffuse(self) -> None:
        with self.rng():
            self.microenv.step()

    def statistics(self) -> Dict[str, int]:
        cells = self.geometry.tumor_cells
        living = sum(c.is_alive for c in cells)
        return {
            "total_cells": len(cells),
            "living_cells": living,
            "apoptotic_cells": sum(c.phase == CellPhase.APOPTOTIC for c in cells),
            "necrotic_cells": sum(c.phase == CellPhase.NECROTIC for c in cells),
            "hypoxic_cells": sum(c.phase == CellPhase.HYPOXIC for c in cells),
        }

    # ------------------------------------------ ported legacy physics methods
    def _update_tumor_cells(self) -> None:
        env = self.microenv
        toxicity = env.get_substrate("toxicity_signal")
        oxygen_field = env.get_substrate("oxygen")
        new_cells: List[TumorCell] = []
        next_id = len(self.geometry.tumor_cells)
        for cell in self.geometry.tumor_cells:
            if not cell.is_alive:
                continue
            oxygen = env.get_concentration_at("oxygen", cell.position)
            drug = env.get_concentration_at("drug", cell.position)
            cell.update_oxygen_status(oxygen, env.dt)
            cell.absorb_drug(drug, env.dt)
            if cell.update_growth(env.dt, oxygen):
                daughter = cell.divide(next_id)
                if daughter:
                    new_cells.append(daughter)
                    next_id += 1
            voxel = env.position_to_voxel(cell.position)
            if oxygen_field:
                oxygen_field.add_sink(voxel, cell.get_oxygen_consumption() * env.dt)
            if toxicity:
                amount = 0.0
                if cell.phase == CellPhase.HYPOXIC:
                    amount += 2.0
                if cell.phase == CellPhase.NECROTIC:
                    amount += 5.0
                if drug > 50.0:
                    amount += 3.0
                if amount > 0.0:
                    toxicity.add_source(voxel, amount)
        self.geometry.tumor_cells.extend(new_cells)
        for cell in new_cells:
            self._cells_by_id[cell.cell_id] = cell
        if new_cells:
            self._apply_cell_mechanics()

    def _apply_cell_mechanics(self) -> None:
        cells = self.geometry.tumor_cells
        repulsion_radius, repulsion_force = 25.0, 2.0
        for i, a in enumerate(cells):
            if not a.is_alive:
                continue
            for b in cells[i + 1:]:
                if not b.is_alive:
                    continue
                dx, dy = b.position[0] - a.position[0], b.position[1] - a.position[1]
                distance = (dx * dx + dy * dy) ** 0.5
                if 0.1 < distance < repulsion_radius:
                    nx, ny = dx / distance, dy / distance
                    push = repulsion_force * (repulsion_radius - distance) / repulsion_radius * 0.5
                    a.position = (a.position[0] - nx * push, a.position[1] - ny * push, a.position[2])
                    b.position = (b.position[0] + nx * push, b.position[1] + ny * push, b.position[2])

    def _update_immune_cells(self) -> None:
        for immune in self.geometry.immune_cells:
            if immune.is_active:
                immune.update(self.microenv.dt, self.geometry.tumor_cells)
                immune.secrete_cytokines(self.microenv)

    def _apply_vessel_sources(self) -> None:
        oxygen = self.microenv.get_substrate("oxygen")
        drug = self.microenv.get_substrate("drug")
        for vessel in self.geometry.vessels:
            voxel = self.microenv.position_to_voxel(vessel.position)
            if oxygen:
                oxygen.add_source(voxel, vessel.oxygen_supply * 0.5)
            if drug and vessel.drug_supply > 0:
                drug.add_source(voxel, vessel.drug_supply * vessel.bbb_permeability)
