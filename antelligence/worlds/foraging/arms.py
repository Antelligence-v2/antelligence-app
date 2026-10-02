"""Experimental arms for chain foraging, each a fully wired Scheduler.

* ``baseline``            — no sharing at all.
* ``hive_memory``         — sightings become evidence claims; agents recall
                            admitted claims and cite them; evidence gate on.
* ``signals``             — pure stigmergy: sightings are expiring local
                            signals (hearing radius), no durable memory.
* ``hive_memory_signals`` — both.

All arms share the world, fixture, seed and default policy logic; only the
coordination components differ, which is what makes the comparison clean.
"""

from __future__ import annotations

from typing import Callable, Optional

from antelligence.kernel.admission import AdmissionPolicy
from antelligence.kernel.field import GridField
from antelligence.kernel.memory import EvidenceMemory, EvidenceRecorder, ScopedRecall
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.kernel.types import Policy
from antelligence.kernel.verifier import EvidenceGate
from antelligence.worlds.foraging.fixtures import STEPS
from antelligence.worlds.foraging.policies import ChainForager
from antelligence.worlds.foraging.world import ChainForagingWorld, food_subject

ARMS = ("baseline", "hive_memory", "signals", "hive_memory_signals")
HEARING = 4.0


def _found_payload(payload) -> Optional[str]:
    food = payload.get("food")
    return None if isinstance(food, int) and not isinstance(food, bool) and food >= 0 else "food_index"


def default_policy(arm: str) -> Policy:
    return ChainForager(
        announce=arm != "baseline",
        use_memory=arm in ("hive_memory", "hive_memory_signals"),
        use_signals=arm in ("signals", "hive_memory_signals"),
    )


def build(
    arm: str,
    seed: int,
    *,
    policy_factory: Callable[[str], Policy] = default_policy,
    run_id: Optional[str] = None,
    max_steps: int = STEPS,
) -> Scheduler:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    uses_memory = arm in ("hive_memory", "hive_memory_signals")
    uses_signals = arm in ("signals", "hive_memory_signals")
    world = ChainForagingWorld(seed, max_steps=max_steps, hearing=HEARING if uses_signals else 0.0)
    config = RunConfig(run_id or f"forage-{seed}", seed=seed, max_ticks=max_steps, arm=arm)
    components = {}
    if uses_memory:
        memory = EvidenceMemory()
        components = dict(
            memory=ScopedRecall(memory, kinds=("claim",)),
            recorder=EvidenceRecorder(memory, {"found": lambda s: food_subject(s.payload["food"])}),
            gate=EvidenceGate.for_memory(memory),
            admission=AdmissionPolicy(kinds={"found": _found_payload}, max_ttl=60, cite_resolver=memory.is_usable),
        )
    elif uses_signals:
        components = dict(admission=AdmissionPolicy(kinds={"found": _found_payload}, max_ttl=60))
    return Scheduler(world, {}, GridField(), config, default_policy=policy_factory(arm), **components)
