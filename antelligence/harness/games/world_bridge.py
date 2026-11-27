"""Bridge between antelligence.kernel.types.World and harness EnvAdapter without modifying kernel/."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence, Union

from antelligence.harness.core import (
    Action,
    EnvSnapshot,
    EpisodeOutcome,
    Observation,
    RealismContract,
    StepResult,
    input_hash,
)
from antelligence.kernel.types import Intent, NOOP, World


class WorldEnvAdapter:
    """~40 LOC adapter wrapping ``kernel.types.World`` as a harness ``EnvAdapter``."""

    def __init__(
        self,
        world: Union[World, Callable[[int], World]],
        agent_id: str,
        realism: RealismContract,
        baseline_fn: Callable[[World, str, int], EpisodeOutcome],
        legal_actions_fn: Optional[Callable[[Observation], Sequence[Action]]] = None,
    ) -> None:
        self._world_factory = world if callable(world) else None
        self.world: World = world(0) if callable(world) else world
        self.agent_id = agent_id
        self.realism = realism
        self._baseline_fn = baseline_fn
        self._legal_actions_fn = legal_actions_fn
        self.supports_checkpoint = hasattr(self.world, "snapshot") and hasattr(self.world, "restore")
        self._tick = 0

    def reset(self, seed: int, config: Optional[Mapping[str, Any]] = None) -> Observation:
        if self._world_factory is not None:
            self.world = self._world_factory(seed)
        elif hasattr(self.world, "reset"):
            self.world.reset(seed)  # type: ignore[attr-defined]
        self._tick = 0
        obs = self.world.observe(self.agent_id, self._tick)
        return {"tick": self._tick, "seed": seed, "data": dict(obs.data)}

    def legal_actions(self, obs: Observation) -> Optional[Sequence[Action]]:
        return self._legal_actions_fn(obs) if self._legal_actions_fn else None

    def step(self, action: Action) -> StepResult:
        if isinstance(action, Intent):
            intent = action
        elif isinstance(action, Mapping):
            intent = Intent(action=str(action.get("action", NOOP)), params=action.get("params", {}))
        else:
            intent = Intent(action=str(action) if action is not None else NOOP)
        outcome = self.world.apply(self.agent_id, intent, self._tick)
        self.world.step_environment(self._tick)
        self._tick += 1
        next_obs = self.world.observe(self.agent_id, self._tick)
        payload = {"tick": self._tick, "data": dict(next_obs.data), "accepted": outcome.accepted}
        return StepResult(
            obs=payload,
            reward=1.0 if outcome.accepted else -0.5,
            done=self.world.done(self._tick),
            info={"outcome": outcome.to_dict(), "metrics": self.world.metrics()},
            state_hash=input_hash({"tick": self._tick, "rev": self.world.revision, "obs": payload}),
        )

    def snapshot(self) -> EnvSnapshot:
        if not self.supports_checkpoint:
            raise NotImplementedError("wrapped World does not support snapshot()")
        return self.world.snapshot()  # type: ignore[attr-defined]

    def restore(self, snap: EnvSnapshot) -> None:
        if not self.supports_checkpoint:
            raise NotImplementedError("wrapped World does not support restore()")
        self.world.restore(snap)  # type: ignore[attr-defined]

    def no_model_baseline(self, seed: int) -> EpisodeOutcome:
        return self._baseline_fn(self.world, self.agent_id, seed)
