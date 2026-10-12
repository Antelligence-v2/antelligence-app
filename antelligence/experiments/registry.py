"""Registry of runnable worlds: how to rebuild any run from a small spec.

A ``RunSpec`` (world, arm, case, params) is all that is needed to rebuild a
run's Scheduler, which is what makes a stored bundle independently
replayable. Worlds may also take string ``options`` (e.g. the legacy agent
type) and a ``model``; a spec whose options call for LLM agents is built with
the LiteLLM provider for that run (``antelligence.providers.litellm``), whose
response cache makes the run replayable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from antelligence.kernel.canonical import content_hash, plain
from antelligence.kernel.scheduler import Scheduler
from antelligence.providers import litellm

NONCE = re.compile(r"^[0-9a-f]{8,32}$")


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
    arm_descriptions: Mapping[str, str] = field(default_factory=dict)
    metric_label: str = ""
    # name -> (default, allowed values, label); string choices such as the legacy agent type
    options: Mapping[str, Tuple[str, Tuple[str, ...], str]] = field(default_factory=dict)
    # resolved params -> whether the run needs a model (adds the "model" param)
    needs_llm: Optional[Callable[[Mapping[str, Any]], bool]] = None
    param_labels: Mapping[str, str] = field(default_factory=dict)

    def resolve_params(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        known = set(self.params) | set(self.options)
        if self.needs_llm is not None:
            known |= {"model", "nonce"}
        unknown = set(params) - known
        if unknown:
            raise ValueError(f"unknown params for {self.name}: {sorted(unknown)}")
        resolved: Dict[str, Any] = {}
        for name, (default, low, high) in self.params.items():
            value = params.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
            resolved[name] = value
        for name, (default, allowed, _label) in self.options.items():
            value = params.get(name, default)
            if value not in allowed:
                raise ValueError(f"{name} must be one of {list(allowed)}")
            resolved[name] = value
        if not self.uses_llm(resolved) and ("model" in params or "nonce" in params):
            raise ValueError("model applies only when the options select LLM agents")
        if self.uses_llm(resolved):
            resolved["model"] = litellm.check_model(params.get("model", litellm.DEFAULT_MODEL))
            if "nonce" in params:
                if not isinstance(params["nonce"], str) or not NONCE.match(params["nonce"]):
                    raise ValueError("nonce must be 8-32 lowercase hex characters")
                resolved["nonce"] = params["nonce"]
        return resolved

    def uses_llm(self, resolved: Mapping[str, Any]) -> bool:
        return self.needs_llm is not None and self.needs_llm(resolved)

    def build(self, spec: RunSpec, run_id: str) -> Scheduler:
        if spec.arm not in self.arms:
            raise ValueError(f"unknown arm {spec.arm!r} for {self.name}")
        params = self.resolve_params(spec.params)
        params.pop("nonce", None)  # only makes the run id unique
        if self.uses_llm(params):
            params["provider"] = litellm.provider_for_run(run_id)
        return self.builder(spec.arm, spec.case, run_id=run_id, **params)

    def catalog(self) -> Dict[str, Any]:
        return {"name": self.name, "arms": list(self.arms), "default_cases": list(self.default_cases),
                "baseline": self.baseline, "primary_metric": self.primary_metric,
                "lower_is_better": self.lower_is_better, "success_metric": self.success_metric,
                "params": {k: {"default": d, "min": lo, "max": hi} for k, (d, lo, hi) in self.params.items()},
                "description": self.description, "metric_label": self.metric_label or self.primary_metric,
                "arm_descriptions": {arm: self.arm_descriptions.get(arm, "") for arm in self.arms},
                "param_labels": dict(self.param_labels),
                "options": {k: {"default": d, "allowed": list(a), "label": label}
                            for k, (d, a, label) in self.options.items()},
                "llm": None if self.needs_llm is None else {"default_model": litellm.DEFAULT_MODEL,
                                                            "available": litellm.available()}}


def _foraging(arm: str, case: int, *, run_id: str, max_steps: int) -> Scheduler:
    from antelligence.worlds.foraging import build
    return build(arm, case, run_id=run_id, max_steps=max_steps)


def _tumor(arm: str, case: int, *, run_id: str, max_steps: int, n_nanobots: int, agent_type: str = "Rule-Based",
           queen_mode: str = "off", provider=None, model: Optional[str] = None) -> Scheduler:
    from antelligence.worlds.tumor import build
    return build(arm, case, run_id=run_id, max_steps=max_steps, n_nanobots=n_nanobots, agent_type=agent_type,
                 queen_mode=queen_mode, provider=provider, model=model)


def _tumor_needs_llm(params: Mapping[str, Any]) -> bool:
    return params.get("agent_type", "Rule-Based") != "Rule-Based" or params.get("queen_mode") == "llm"


def _task_dag(arm: str, case: int, *, run_id: str) -> Scheduler:
    from antelligence.worlds.task_dag import build
    return build(arm, case, run_id=run_id)


def _registry() -> Dict[str, WorldSpec]:
    from antelligence.worlds.foraging import ARMS as FORAGING_ARMS, SEEDS
    from antelligence.worlds.task_dag import ARMS as DAG_ARMS, SEEDS as DAG_SEEDS
    from antelligence.worlds.tumor import ARMS as TUMOR_ARMS
    from antelligence.worlds.tumor.arms import AGENT_TYPES as TUMOR_AGENT_TYPES, QUEEN_MODES as TUMOR_QUEEN_MODES

    return {
        "foraging": WorldSpec(
            name="foraging", arms=tuple(FORAGING_ARMS), default_cases=tuple(SEEDS), baseline="baseline",
            primary_metric="sweep_moves", lower_is_better=True, success_metric="success",
            params={"max_steps": (120, 10, 400)}, builder=_foraging,
            description="E13 chain-prioritized foraging (10x10, 3 agents, 3 foods in order).",
            metric_label="blind-search (sweep) moves",
            arm_descriptions={
                "baseline": "Agents search alone; nothing is shared.",
                "hive_memory": "Sightings become shared evidence; agents follow remembered food and cite it; stale facts are blocked.",
                "signals": "Sightings are local, expiring signals other agents can hear; no lasting memory.",
                "hive_memory_signals": "Shared evidence memory plus local signals.",
            },
        ),
        "tumor": WorldSpec(
            name="tumor", arms=tuple(TUMOR_ARMS), default_cases=tuple(range(1, 11)), baseline="rule",
            primary_metric="mean_living_cells", lower_is_better=True, success_metric="cleared",
            params={"max_steps": (150, 10, 400), "n_nanobots": (10, 1, 40)}, builder=_tumor,
            description="Synthetic 2D glioblastoma: nanobots deliver drug to tumor cells. Rule-based, LLM-powered "
                        "or hybrid nanobots, optional Queen (research model, not clinical).",
            options={"agent_type": ("Rule-Based", TUMOR_AGENT_TYPES, "Nanobot brains"),
                     "queen_mode": ("off", TUMOR_QUEEN_MODES, "Queen")},
            needs_llm=_tumor_needs_llm,
            param_labels={"max_steps": "Steps", "n_nanobots": "Nanobots"},
            metric_label="average living tumor cells (lower = faster kill)",
            arm_descriptions={
                "no_bots": "No nanobots: natural cell loss only.",
                "rule": "Nanobots act alone: target the nearest sensed cell, otherwise follow chemical gradients.",
                "pheromone": "Adds diffusing chemical pheromones (trail, alarm, recruitment).",
                "signals": "Bots post 'found' and 'claimed' signals and avoid cells another bot has claimed.",
                "hive": "Signals plus shared memory of tumor zones; stale zone facts are blocked.",
                "hive_queen": "Hive plus a Queen that only hears reports and recruits bots toward busy zones.",
            },
        ),
        "task_dag": WorldSpec(
            name="task_dag", arms=tuple(DAG_ARMS), default_cases=tuple(DAG_SEEDS), baseline="solo_planner",
            primary_metric="success", lower_is_better=False, success_metric="success",
            params={}, builder=_task_dag,
            description="E15 partial-view planners + deterministic merge + model-free admission (scripted planners).",
            metric_label="plans that execute successfully",
            arm_descriptions={
                "solo_planner": "One planner sees the whole task and proposes the full plan.",
                "swarm_partitioned": "Each agent sees only its own sample and proposes its piece; pieces are simply combined.",
                "swarm_partitioned_merged": "Same partial views, then a deterministic merge repairs ordering and resource conflicts.",
            },
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
