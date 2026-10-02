"""Registry of runnable worlds: how to rebuild any run from a small spec.

A ``RunSpec`` (world, arm, case, params) is all that is needed to rebuild a
run's Scheduler, which is what makes a stored bundle independently
replayable. Only rule-policy worlds are registered: LLM-driven runs need a
provider configuration and are built directly in Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Tuple

from antelligence.kernel.canonical import content_hash, plain
from antelligence.kernel.scheduler import Scheduler


@dataclass(frozen=True)
class RunSpec:
    world: str
    arm: str
    case: int
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", plain(dict(self.params)))

    def to_dict(self) -> Dict[str, Any]:
        return {"world": self.world, "arm": self.arm, "case": self.case, "params": dict(self.params)}

    @property
    def key(self) -> str:
        return content_hash(self.to_dict())[:16]


@dataclass(frozen=True)
class WorldSpec:
    name: str
    arms: Tuple[str, ...]
    default_cases: Tuple[int, ...]
    baseline: str
    primary_metric: str
    lower_is_better: bool
    success_metric: str
    params: Mapping[str, Tuple[int, int, int]]  # name -> (default, min, max)
    builder: Callable[..., Scheduler]
    description: str

    def resolve_params(self, params: Mapping[str, Any]) -> Dict[str, int]:
        unknown = set(params) - set(self.params)
        if unknown:
            raise ValueError(f"unknown params for {self.name}: {sorted(unknown)}")
        resolved = {}
        for name, (default, low, high) in self.params.items():
            value = params.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
            resolved[name] = value
        return resolved

    def build(self, spec: RunSpec, run_id: str) -> Scheduler:
        if spec.arm not in self.arms:
            raise ValueError(f"unknown arm {spec.arm!r} for {self.name}")
        return self.builder(spec.arm, spec.case, run_id=run_id, **self.resolve_params(spec.params))

    def catalog(self) -> Dict[str, Any]:
        return {"name": self.name, "arms": list(self.arms), "default_cases": list(self.default_cases),
                "baseline": self.baseline, "primary_metric": self.primary_metric,
                "lower_is_better": self.lower_is_better, "success_metric": self.success_metric,
                "params": {k: {"default": d, "min": lo, "max": hi} for k, (d, lo, hi) in self.params.items()},
                "description": self.description}


def _foraging(arm: str, case: int, *, run_id: str, max_steps: int) -> Scheduler:
    from antelligence.worlds.foraging import build
    return build(arm, case, run_id=run_id, max_steps=max_steps)


def _tumor(arm: str, case: int, *, run_id: str, max_steps: int, n_nanobots: int) -> Scheduler:
    from antelligence.worlds.tumor import build
    return build(arm, case, run_id=run_id, max_steps=max_steps, n_nanobots=n_nanobots)


def _task_dag(arm: str, case: int, *, run_id: str) -> Scheduler:
    from antelligence.worlds.task_dag import build
    return build(arm, case, run_id=run_id)


def _registry() -> Dict[str, WorldSpec]:
    from antelligence.worlds.foraging import ARMS as FORAGING_ARMS, SEEDS
    from antelligence.worlds.task_dag import ARMS as DAG_ARMS, SEEDS as DAG_SEEDS
    from antelligence.worlds.tumor import ARMS as TUMOR_ARMS

    return {
        "foraging": WorldSpec(
            name="foraging", arms=tuple(FORAGING_ARMS), default_cases=tuple(SEEDS), baseline="baseline",
            primary_metric="sweep_moves", lower_is_better=True, success_metric="success",
            params={"max_steps": (120, 10, 400)}, builder=_foraging,
            description="E13 chain-prioritized foraging (10x10, 3 agents, 3 foods in order).",
        ),
        "tumor": WorldSpec(
            name="tumor", arms=tuple(TUMOR_ARMS), default_cases=tuple(range(1, 11)), baseline="rule",
            primary_metric="living_cells", lower_is_better=True, success_metric="cleared",
            params={"max_steps": (150, 10, 400), "n_nanobots": (10, 1, 40)}, builder=_tumor,
            description="Synthetic 2D glioblastoma with rule nanobots (research model, not clinical).",
        ),
        "task_dag": WorldSpec(
            name="task_dag", arms=tuple(DAG_ARMS), default_cases=tuple(DAG_SEEDS), baseline="solo_planner",
            primary_metric="success", lower_is_better=False, success_metric="success",
            params={}, builder=_task_dag,
            description="E15 partial-view planners + deterministic merge + model-free admission (scripted planners).",
        ),
    }


WORLDS: Dict[str, WorldSpec] = _registry()


def world(name: str) -> WorldSpec:
    try:
        return WORLDS[name]
    except KeyError:
        raise ValueError(f"unknown world {name!r}; available: {sorted(WORLDS)}") from None


def catalog() -> List[Dict[str, Any]]:
    return [spec.catalog() for spec in WORLDS.values()]
