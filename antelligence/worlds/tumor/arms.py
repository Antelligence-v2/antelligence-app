"""Experimental arms for the tumor world.

* ``no_bots``    — physics only (natural cell loss baseline).
* ``rule``       — legacy rule nanobots, no communication.
* ``pheromone``  — rule nanobots + legacy diffusing chemical pheromones.
* ``signals``    — typed stigmergy: ``found``/``claimed`` signals, claims honored.
* ``hive``       — signals + evidence memory of tumor zones + evidence gate.
* ``hive_queen`` — hive + a body-less Queen that recruits toward reported zones.

Arms share seed, geometry and physics; only coordination differs.
"""

from __future__ import annotations

from typing import Callable, Optional

from antelligence.kernel.admission import AdmissionPolicy
from antelligence.kernel.field import GridField
from antelligence.kernel.memory import EvidenceMemory, EvidenceRecorder, ScopedRecall
from antelligence.kernel.policies import QueenEmitter
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.kernel.types import Policy
from antelligence.kernel.verifier import EvidenceGate
from antelligence.worlds.tumor.policies import NanobotPolicy
from antelligence.worlds.tumor.world import QUEEN, ZONE, TumorWorld, zone_subject

ARMS = ("no_bots", "rule", "pheromone", "signals", "hive", "hive_queen")
HEARING = 150.0
RECALL_RADIUS = 250.0


def _nonneg_int(key: str):
    def check(payload) -> Optional[str]:
        value = payload.get(key)
        return None if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else key
    return check


def _recruit(payload) -> Optional[str]:
    return None if isinstance(payload.get("reports"), int) else "reports"


def default_policy(arm: str) -> Policy:
    coordinated = arm in ("signals", "hive", "hive_queen")
    return NanobotPolicy(announce=coordinated, honor_claims=coordinated,
                         use_signals=coordinated, use_memory=arm in ("hive", "hive_queen"))


def _nearby_zones(agent_id: str, observation) -> list:
    """Recall is local too: only zones within RECALL_RADIUS of the bot."""
    if observation.get("role") != "nanobot":
        return []
    x, y = observation["pos"]
    reach = int(RECALL_RADIUS // ZONE) + 1
    zx, zy = int(x // ZONE), int(y // ZONE)
    return [f"zone:{i},{j}" for i in range(zx - reach, zx + reach + 1) for j in range(zy - reach, zy + reach + 1)
            if ((i + 0.5) * ZONE - x) ** 2 + ((j + 0.5) * ZONE - y) ** 2 <= RECALL_RADIUS ** 2]


def build(
    arm: str,
    seed: int,
    *,
    n_nanobots: int = 10,
    max_steps: int = 100,
    policy_factory: Callable[[str], Policy] = default_policy,
    run_id: Optional[str] = None,
    **world_kwargs,
) -> Scheduler:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    coordinated = arm in ("signals", "hive", "hive_queen")
    world = TumorWorld(
        seed,
        n_nanobots=0 if arm == "no_bots" else n_nanobots,
        max_steps=max_steps,
        chemical_pheromones=arm == "pheromone",
        hearing=HEARING if coordinated else 0.0,
        queen=arm == "hive_queen",
        **world_kwargs,
    )
    config = RunConfig(run_id or f"tumor-{seed}", seed=seed, max_ticks=max_steps, arm=arm)
    kinds = {"found": _nonneg_int("cells"), "claimed": _nonneg_int("cell_id"), "recruit": _recruit}
    components: dict = {}
    if arm in ("hive", "hive_queen"):
        memory = EvidenceMemory()
        components = dict(
            memory=ScopedRecall(memory, _nearby_zones, kinds=("claim",)),
            recorder=EvidenceRecorder(memory, {"found": lambda s: zone_subject(s.pos)}),
            gate=EvidenceGate.for_memory(memory),
            admission=AdmissionPolicy(kinds=kinds, max_ttl=30, cite_resolver=memory.is_usable,
                                      max_per_sender_per_tick=4),
        )
    elif coordinated:
        components = dict(admission=AdmissionPolicy(kinds=kinds, max_ttl=30, max_per_sender_per_tick=4))
    policies = {}
    if arm == "hive_queen":
        policies[QUEEN] = QueenEmitter(report_kind="found", cell_size=ZONE * 2, min_reports=2, every=5, ttl=10)
    return Scheduler(world, policies, GridField(), config, default_policy=policy_factory(arm), **components)
