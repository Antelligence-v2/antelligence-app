"""Domain-agnostic harness core: tasks, artifacts, tools, and the Task/Env adapter protocols.

Nothing here knows about MCQs, games or models. A *curated task* suite implements :class:`TaskAdapter`; an
interactive game implements :class:`EnvAdapter`. Both feed the same graph, scheduler, replay and scorecard.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, runtime_checkable

Observation = Any
Action = Any
FIDELITY_TIERS = ("real_engine", "calibrated_sim", "proxy")


def input_hash(value: Any) -> str:
    """Stable SHA-256 of any JSON-able tool input (unknown types fall back to ``str``)."""
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Task:
    """One unit of work. ``created_at``/``cutoff_at`` (ISO strings) let a suite prove it post-dates a model's training."""

    id: str
    kind: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    cutoff_at: Optional[str] = None


@dataclass(frozen=True)
class Artifact:
    """What one tool produced for one task, with its full honest bill. ``format_ok`` is separate from correctness."""

    task_id: str
    tool: str
    answer: Any = None
    format_ok: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    calls: int = 0
    error: Optional[str] = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Artifact":
        return cls(**dict(data))


Deps = Mapping[str, Artifact]
ToolFn = Callable[[Task, Deps], Awaitable[Artifact]]


@dataclass(frozen=True)
class ToolSpec:
    """A named step. ``model_key`` groups tools served by the same model; ``local=True`` means loading it is costly,
    so the scheduler drains it in batches. ``input_fn`` says what the step reads (it is the replay key)."""

    name: str
    run: ToolFn
    model_key: Optional[str] = None
    local: bool = False
    input_fn: Optional[Callable[[Task, Deps], Any]] = None

    def input_for(self, task: Task, deps: Deps) -> Any:
        if self.input_fn is not None:
            return self.input_fn(task, deps)
        return {"task": dict(task.payload), "deps": {k: deps[k].answer for k in sorted(deps)}}


class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec] = ()) -> None:
        self._specs: Dict[str, ToolSpec] = {}
        for s in specs:
            self.register(s)

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._specs:
            raise ValueError(f"tool already registered: {spec.name}")
        if spec.local and not spec.model_key:
            raise ValueError(f"local tool {spec.name} needs a model_key")
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise KeyError(f"unknown tool: {name}") from None

    def has(self, name: str) -> bool:
        return name in self._specs

    def names(self) -> List[str]:
        return list(self._specs)


@runtime_checkable
class TaskAdapter(Protocol):
    """Curated, bounded real-world tasks (triage, extraction, ops, forecasts...)."""

    def format_input(self, task: Task) -> Any: ...

    def parse_output(self, task: Task, raw: str) -> Artifact: ...  # sets format_ok; never scores

    def score(self, task: Task, artifact: Artifact) -> Optional[float]: ...

    def audit_shortcuts(self, tasks: Sequence[Task]) -> Mapping[str, Any]: ...


# ---------------------------------------------------------------------------------------------- environments

@dataclass(frozen=True)
class RealismContract:
    """Tags every result with how real its world was; proxy wins are never reported as real-world proof."""

    fidelity_tier: str
    units: Mapping[str, str] = field(default_factory=dict)
    invariants: Sequence[str] = ()

    def __post_init__(self) -> None:
        if self.fidelity_tier not in FIDELITY_TIERS:
            raise ValueError(f"fidelity_tier must be one of {FIDELITY_TIERS}, got {self.fidelity_tier!r}")


@dataclass(frozen=True)
class StepResult:
    obs: Observation
    reward: float
    done: bool
    info: Mapping[str, Any]
    state_hash: str


@dataclass(frozen=True)
class EnvSnapshot:
    """Opaque checkpoint. ``blob`` must include RNG state (or the env derives draws from seed/step/action)."""

    state_hash: str
    blob: Any
    step_idx: int = 0
    obs: Observation = None


@dataclass(frozen=True)
class EpisodeOutcome:
    score: float
    cost_usd: float = 0.0
    latency_s: float = 0.0
    steps: int = 0
    info: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class EnvAdapter(Protocol):
    supports_checkpoint: bool
    realism: RealismContract

    def reset(self, seed: int, config: Optional[Mapping[str, Any]] = None) -> Observation: ...

    def step(self, action: Action) -> StepResult: ...

    def legal_actions(self, obs: Observation) -> Optional[Sequence[Action]]: ...

    def snapshot(self) -> EnvSnapshot: ...

    def restore(self, snap: EnvSnapshot) -> None: ...

    def no_model_baseline(self, seed: int) -> EpisodeOutcome: ...


def _rollout(env: EnvAdapter, obs: Observation, policy: Callable[[Observation], Action], max_steps: int) -> List[str]:
    hashes: List[str] = []
    for _ in range(max_steps):
        res = env.step(policy(obs))
        hashes.append(res.state_hash)
        obs = res.obs
        if res.done:
            break
    return hashes


def verify_env_contract(env: EnvAdapter, seed: int = 0, policy: Optional[Callable[[Observation], Action]] = None,
                        max_steps: int = 50) -> List[str]:
    """Return a list of contract violations (empty = OK): baseline exists, resets are deterministic, and when
    ``supports_checkpoint`` a restore replays the identical state-hash trajectory."""
    problems: List[str] = []
    if not isinstance(env.realism, RealismContract):
        problems.append("realism must be a RealismContract")
    if not isinstance(env.no_model_baseline(seed), EpisodeOutcome):
        problems.append("no_model_baseline must return an EpisodeOutcome")
    pick = policy or (lambda o: (env.legal_actions(o) or [None])[0])
    first = _rollout(env, env.reset(seed), pick, max_steps)
    if first != _rollout(env, env.reset(seed), pick, max_steps):
        problems.append("reset(seed) is not deterministic")
    if env.supports_checkpoint:
        obs = env.reset(seed)
        for _ in range(2):
            res = env.step(pick(obs))
            obs = res.obs
        snap = env.snapshot()
        tail = _rollout(env, obs, pick, max_steps)
        env.restore(snap)
        if _rollout(env, obs, pick, max_steps) != tail:
            problems.append("restore() did not reproduce the same trajectory (RNG state captured?)")
    return problems
