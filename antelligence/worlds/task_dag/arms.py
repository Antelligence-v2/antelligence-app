"""Wire E15's three arms onto the engine."""

from __future__ import annotations

from typing import Callable, Optional

from antelligence.kernel.field import BoardField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.kernel.types import Policy
from antelligence.worlds.task_dag.policies import ScriptedPlanner
from antelligence.worlds.task_dag.world import ARMS, TaskDAGWorld


def default_policy(arm: str) -> Policy:
    return ScriptedPlanner()


def build(arm: str, seed: int, *, policy_factory: Callable[[str], Policy] = default_policy,
          run_id: Optional[str] = None, composition: Optional[str] = None) -> Scheduler:
    world = TaskDAGWorld(seed, arm, composition=composition)
    config = RunConfig(run_id or f"dag-{seed}", seed=seed, max_ticks=1, arm=arm, max_emits_per_tick=0)
    return Scheduler(world, {}, BoardField(), config, default_policy=policy_factory(arm))


__all__ = ["ARMS", "build", "default_policy"]
