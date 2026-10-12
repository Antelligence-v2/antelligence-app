"""v4 pilot harness: arms, seeds, run plan, one-cell runner, metrics tap, Phase 0 calibration, dry-run kit.

The harness talks to worlds only through :class:`PilotWorld`, and to model code only through the
callable ``build_policies`` that the integrator supplies, so nothing here imports a world, a provider
or a decision backend. A cell is one (world, arm, seed, condition) episode; cells are append-only.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import gzip
import hashlib
import json
import random
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from antelligence.experiments.pilot_contract import CONDITIONS, PilotWorld, report_is_true
from antelligence.experiments.v4_budget import BudgetExceeded, provider_of, read_jsonl
from antelligence.experiments.v4_metrics import seconds_per_decision
from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.decision import REPORT, Answer, DecisionRequest, DecisionResponse, check_answers
from antelligence.kernel.field import BoardField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.kernel.types import Intent, LocalView, Observation, Outcome, Policy, World
from antelligence.provenance.bundle import build_bundle

DEV_SEEDS = tuple(range(100, 110))
EVAL_SEEDS = (1, 2, 3, 4, 5)
DS_ALL_FORAGING_SEEDS = 3  # budget exception: DS-all on foraging runs the first 3 seeds
WORLDS = ("foraging_sb", "graph_coloring")
FORAGING = "foraging_sb"
NOUS_MODEL = "deepseek/deepseek-v4.1-flash"
GATED_FILES = ("docs/research/v4-pilot-20261011/PREREGISTRATION.md", "scripts/v4_pilot.py",
               "antelligence/experiments/v4_pilot.py", "antelligence/experiments/v4_metrics.py",
               "antelligence/experiments/v4_budget.py")
GATED_TREES = ("antelligence", "scripts")  # every engine, world, policy and backend file is frozen at evaluation


@dataclass(frozen=True)
class ArmSpec:
    """One setup in the comparison (goal section 6)."""

    name: str
    decider: str  # script | script_adapted | every_agent | decision_model
    queen: bool
    escalation: bool
    backend: str  # none | nous | vllm | jev | laya
    model: str
    variants_only: bool = False
    all_actions: bool = False  # workers may pick any action (no queen restriction)
    hardware: str = "local-cpu"


def _q_all(model: str) -> ArmSpec:
    return ArmSpec(f"Q-all-{model.split('/')[-1].lower()}", "every_agent", False, False, "vllm", model,
                   hardware="runpod-L40S-vllm")


ARMS: Dict[str, ArmSpec] = {a.name: a for a in (
    ArmSpec("S", "script", False, False, "none", "script"),
    ArmSpec("S-prime", "script_adapted", False, False, "none", "script", variants_only=True),
    ArmSpec("DS-all", "every_agent", False, False, "nous", NOUS_MODEL, hardware="nous-inference-api"),
    _q_all("Qwen/Qwen3.5-0.8B"), _q_all("Qwen/Qwen3.5-4B"), _q_all("Qwen/Qwen3.5-9B"), _q_all("Qwen/Qwen3.5-27B"),
    _q_all("Qwen/Qwen3.8-27B"),
    ArmSpec("F-Laya", "decision_model", True, True, "laya", "convaiinnovations/laya-typed-decisions",
            hardware="local-mac-laya-serve+runpod-L40S-slm"),
    ArmSpec("F-Jev", "decision_model", True, True, "jev", "jev-1.13.0", hardware="typesafe-api+runpod-L40S-slm"),
    ArmSpec("F-Jev-noQueen", "decision_model", False, True, "jev", "jev-1.13.0", all_actions=True,
            hardware="typesafe-api+runpod-L40S-slm"),
    ArmSpec("F-Jev-noEsc", "decision_model", True, False, "jev", "jev-1.13.0", hardware="typesafe-api"),
)}
SCRIPT_ARMS = ("S", "S-prime")


@dataclass(frozen=True)
class CellSpec:
    """One episode. ``queen_every`` overrides the world's queen cadence (budget cut), else None."""

    world: str
    arm: str
    seed: int
    condition: str
    queen_every: Optional[int] = None

    @property
    def key(self) -> str:
        return f"{self.world}|{self.arm}|{self.seed}|{self.condition}"

    @property
    def run_id(self) -> str:
        return f"{self.world}-{self.arm}-s{self.seed}-{self.condition}"

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def make_plan(worlds: Sequence[str] = WORLDS, arms: Optional[Sequence[str]] = None, seeds: Sequence[int] = EVAL_SEEDS,
              conditions: Sequence[str] = CONDITIONS) -> List[CellSpec]:
    """Every (world, arm, seed, condition) cell; script arms first. S' runs on variants only; DS-all on
    foraging runs the first 3 seeds (goal section 6)."""
    names = list(arms or ARMS)
    unknown = [a for a in names if a not in ARMS]
    if unknown:
        raise ValueError(f"unknown arms: {unknown}")
    plan = []
    for arm in sorted(names, key=lambda a: (ARMS[a].decider not in ("script", "script_adapted"), list(ARMS).index(a))):
        for world in worlds:
            arm_seeds = list(seeds)[:DS_ALL_FORAGING_SEEDS] if arm == "DS-all" and world == FORAGING else list(seeds)
            for condition in conditions:
                if ARMS[arm].variants_only and condition == "base":
                    continue
                plan += [CellSpec(world, arm, s, condition) for s in arm_seeds]
    return plan


def uses_eval_seeds(seeds: Sequence[int]) -> bool:
    return bool(set(seeds) & set(EVAL_SEEDS))


def check_committed(root: Path, files: Sequence[str] = GATED_FILES) -> None:
    """Evaluation gate: preregistration and harness files must be tracked and unmodified."""
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)

    for f in files:
        if git("ls-files", "--error-unmatch", "--", f).returncode != 0:
            raise SystemExit(f"evaluation refused: {f} is not committed")
    dirty = git("status", "--porcelain", "--", *files, *GATED_TREES).stdout.strip()
    if dirty:
        raise SystemExit(f"evaluation refused: uncommitted changes in gated files:\n{dirty}")


def providers_of_arm(arm: str) -> Tuple[str, ...]:
    a = ARMS[arm]
    out = {"nous"} if a.backend == "nous" or a.queen else set()
    out |= {"jev"} if a.backend == "jev" else set()
    out |= {"runpod"} if a.backend == "vllm" or a.escalation else set()
    return tuple(sorted(out))


class SetupError(RuntimeError):
    """Raised by ``build_policies`` before any model call (wrong pod loaded, missing key): the run stops and the
    cell is NOT recorded, so it can be rerun once fixed. Failures after a call has been made are error cells."""


# --- metrics tap --------------------------------------------------------------


class _WorldProxy:
    """Delegates the World protocol (and snapshot/scene for frames) to ``inner``."""

    def __init__(self, inner: World) -> None:
        self.inner = inner

    @property
    def revision(self) -> int:
        return self.inner.revision

    def agents(self) -> List[str]:
        return self.inner.agents()

    def observe(self, agent_id: str, tick: int) -> Observation:
        return self.inner.observe(agent_id, tick)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        return self.inner.apply(agent_id, intent, tick)

    def step_environment(self, tick: int) -> None:
        self.inner.step_environment(tick)

    def metrics(self) -> Dict[str, Any]:
        return self.inner.metrics()

    def done(self, tick: int) -> bool:
        return self.inner.done(tick)

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    def __getattr__(self, name: str) -> Any:  # snapshot / scene for replay frames
        if name == "inner":
            raise AttributeError(name)
        return getattr(self.inner, name)


class MetricsTap(_WorldProxy):
    """Records every worker decision for metrics. Outermost world wrapper; never changes behaviour.

    Per worker decision: the allowed set, the answer, the report flag, and (privileged, metrics only) the
    oracle action from the observation the worker decided on. The allowed set is the intent's own
    ``meta["allowed"]`` if the policy reports it, else the latest queen signal (visible from the tick after
    it was emitted) for the worker's group, else every action. REPORT is always an allowed answer.
    Intent ``meta["escalated"]`` (list of question ids) marks model decisions and escalations.
    """

    def __init__(self, inner: World, pilot_world: PilotWorld, base_world: World) -> None:
        super().__init__(inner)
        self.pilot_world, self.base_world = pilot_world, base_world
        self.records: List[Dict[str, Any]] = []
        self.queen_signals: List[Tuple[int, str, Tuple[str, ...]]] = []
        self._oracle: Dict[Tuple[str, int], Optional[Tuple[str, ...]]] = {}
        self._group_of: Optional[Dict[str, str]] = None

    def observe(self, agent_id: str, tick: int) -> Observation:
        obs = self.inner.observe(agent_id, tick)
        if agent_id != "queen":
            try:
                oracle = getattr(self.pilot_world, "oracle_actions", None)  # every equally good action
                self._oracle[(agent_id, tick)] = (tuple(oracle(self.base_world, agent_id, tick)) if oracle else
                                                  (self.pilot_world.oracle_action(self.base_world, agent_id, tick),))
            except Exception:  # metrics only: a failing oracle must not alter the run
                self._oracle[(agent_id, tick)] = None
        return obs

    def _allowed(self, agent_id: str, tick: int) -> Tuple[str, ...]:
        if self._group_of is None:
            self._group_of = {a: g for g, members in self.pilot_world.groups(self.base_world).items()
                              for a in members}
        group = self._group_of.get(agent_id)
        latest = [al for t, g, al in self.queen_signals if g == group and t < tick]
        return latest[-1] if latest else tuple(self.pilot_world.actions)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if agent_id == "queen":
            for draft in intent.emit:
                if draft.kind == "queen":
                    self.queen_signals.append((tick, str(draft.payload.get("group")),
                                               tuple(draft.payload.get("allowed", ()))))
        else:
            allowed = tuple(intent.meta.get("allowed") or self._allowed(agent_id, tick))
            oracle = self._oracle.pop((agent_id, tick), None)
            # A REPORT answer acts NOOP (DecisionWorker) and says so in meta["answer"]; a policy that could not
            # answer (backend or provider failure) sets meta["reason"]. NOOP itself can be a legal action.
            reported = intent.action == REPORT or intent.meta.get("answer") == REPORT
            self.records.append({
                "tick": tick, "agent": agent_id, "answer": REPORT if reported else intent.action, "allowed": allowed,
                "reported": reported, "failed": "reason" in intent.meta, "oracle": oracle,
                "model": "escalated" in intent.meta, "escalated": bool(intent.meta.get("escalated")),
                "check_failed": bool(intent.meta.get("failed_checks")),
                "report_true": (report_is_true(oracle, allowed) if reported and oracle else None)})
        return self.inner.apply(agent_id, intent, tick)

    def summary(self) -> Dict[str, Any]:
        answers = [r for r in self.records if not r["failed"]]  # a failed policy is a noop, not an answer
        compliant = [r for r in answers if r["answer"] == REPORT or r["answer"] in r["allowed"]]
        reports = [r for r in answers if r["reported"]]
        judged = [r for r in reports if r["report_true"] is not None]
        model = [r for r in answers if r["model"]]
        return {
            "decisions": len(self.records), "answers": len(answers), "noops": len(self.records) - len(answers),
            "compliance": len(compliant) / len(answers) if answers else None,
            "reports": len(reports), "reports_judged": len(judged),
            "reports_true": sum(bool(r["report_true"]) for r in judged),
            "report_precision": sum(bool(r["report_true"]) for r in judged) / len(judged) if judged else None,
            "model_decisions": len(model), "escalations": sum(r["escalated"] for r in model),
            "escalation_rate": sum(r["escalated"] for r in model) / len(model) if model else None,
            "check_reports": sum(r["check_failed"] for r in answers),  # board reports posted by a failed check
            "queen_signals": len(self.queen_signals)}


# --- cell runner --------------------------------------------------------------


@dataclass
class PolicySet:
    """What ``build_policies`` returns. ``wrap_world`` (e.g. HiveWorld around the inner world) is applied
    below the tap; ``policies`` may include "queen"; ``default_policy`` serves every other agent."""

    policies: Mapping[str, Policy] = field(default_factory=dict)
    default_policy: Optional[Policy] = None
    wrap_world: Optional[Callable[[World], World]] = None
    queen_every: Optional[int] = None  # the queen's effective cadence in ticks (None: no queen), for the cell record


# build_policies(spec, pilot_world, world) -> PolicySet
BuildPolicies = Callable[[CellSpec, PilotWorld, World], PolicySet]
# ledger_tags(**tags) -> context manager that tags every ledger row written inside it (B1's ledger_context)
LedgerTags = Callable[..., ContextManager[Any]]
# ledger_rows(run_tag) -> ledger rows of that one execution (its unique run_tag, not the cell key)
LedgerRows = Callable[[str], List[Dict[str, Any]]]
# reconcile(run_id, ledger rows) -> fields merged into the cell (physical calls vs ledger rows)
Reconcile = Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]


def _ledger_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_provider: Dict[str, float] = {}
    by_role: Dict[str, float] = {}
    for r in rows:
        cost = float(r.get("cost_usd") or 0.0)
        by_role[r.get("role", "?")] = by_role.get(r.get("role", "?"), 0.0) + cost
        if provider_of(r):
            by_provider[provider_of(r)] = by_provider.get(provider_of(r), 0.0) + cost
    return {"calls": len(rows), "call_errors": sum(bool(r.get("error")) for r in rows),
            "input_tokens": sum(int(r.get("input_tokens") or 0) for r in rows),
            "output_tokens": sum(int(r.get("output_tokens") or 0) for r in rows),
            "cost_usd": sum(by_role.values()), "cost_by_provider": by_provider, "cost_by_role": by_role,
            "queen_cost_usd": by_role.get("queen", 0.0),
            "latencies_s": [float(r["latency_s"]) for r in rows
                            if r.get("latency_s") is not None and not r.get("error")]}


def _write_bundle(directory: Path, run_id: str, scheduler: Scheduler, result: Any, spec: CellSpec,
                  extra: Mapping[str, Any]) -> str:
    """Run bundle + hash-chained event log + replay frames (same gz layout as EngineStore) for later viewing."""
    (directory / "events").mkdir(parents=True, exist_ok=True)
    bundle = build_bundle(result, spec.to_dict(), world_description=scheduler.world.describe(), extra=extra)
    (directory / f"{run_id}.bundle.json").write_text(canonical_json(bundle))
    scheduler.log.write_jsonl(directory / "events" / f"{run_id}.jsonl")
    if scheduler.frames:
        with gzip.open(directory / f"{run_id}.frames.json.gz", "wt", encoding="utf-8") as handle:
            json.dump({"run_id": run_id, "scene": scheduler.scene, "frames": scheduler.frames}, handle,
                      separators=(",", ":"))
    return bundle["bundle_hash"]


async def arun_cell(spec: CellSpec, pilot_world: PilotWorld, build_policies: BuildPolicies, *,
                    ledger_tags: LedgerTags, ledger_rows: Optional[LedgerRows] = None,
                    reconcile: Optional[Reconcile] = None,
                    refs: Optional[Mapping[str, float]] = None, bundle_dir: Optional[Path] = None,
                    max_ticks: Optional[int] = None) -> Dict[str, Any]:
    """One episode on the kernel Scheduler -> cell dict; ``refs`` {"S", "S-prime"} scores give G (variants)."""
    arm = ARMS[spec.arm]
    world = pilot_world.make_world(spec.seed, spec.condition)
    built = build_policies(spec, pilot_world, world)
    tap = MetricsTap(built.wrap_world(world) if built.wrap_world else world, pilot_world, world)
    config = RunConfig(run_id=spec.run_id, seed=spec.seed, arm=spec.arm,
                       max_ticks=max_ticks or int(pilot_world.describe().get("max_ticks", 100)))
    scheduler = Scheduler(tap, built.policies, BoardField(), config, default_policy=built.default_policy)
    start = time.monotonic()
    # unique per execution: a dev rerun of the same key must not merge its ledger rows with the first run's
    run_tag = f"{spec.key}#{uuid.uuid4().hex[:8]}"
    with ledger_tags(run=run_tag, arm=spec.arm, world=spec.world, seed=spec.seed, condition=spec.condition):
        result = await scheduler.arun()
    wall = time.monotonic() - start
    score = float(pilot_world.score(world))
    g = None
    if refs and spec.condition != "base" and arm.decider not in ("script", "script_adapted") \
            and "S" in refs and "S-prime" in refs and refs["S-prime"] > refs["S"]:
        g = (score - refs["S"]) / (refs["S-prime"] - refs["S"])
    rows = ledger_rows(run_tag) if ledger_rows else []
    led = _ledger_summary(rows)
    tapped = tap.summary()
    cell = {
        **spec.to_dict(), "key": spec.key, "run_tag": run_tag, "split": "eval" if spec.seed in EVAL_SEEDS else "dev",
        "score": score, "g": g, "ticks": result.ticks, "wall_s": wall, "stopped_reason": result.stopped_reason,
        "policy_failures": result.policy_failures, **led,
        # wall-clock per physical model call (ledger rows), never a cache hit or a policy's bookkeeping
        "decision_s": seconds_per_decision(led["latencies_s"]), **tapped, "queen_every": built.queen_every,
        "trace_hash": result.trace_hash, "config_hash": result.config_hash,
        "event_count": result.event_count, "hardware": arm.hardware, "backend": arm.backend, "model": arm.model,
        "pod": arm.backend == "vllm" or arm.escalation}
    if reconcile is not None:
        cell.update(reconcile(spec.run_id, rows))
    if bundle_dir is not None:
        cell["bundle_hash"] = _write_bundle(Path(bundle_dir), spec.run_id, scheduler, result, spec,
                                            {"cell": spec.key, "score": score, "metrics_tap": tapped})
    return cell


def run_cell(spec: CellSpec, pilot_world: PilotWorld, build_policies: BuildPolicies, *, ledger_tags: LedgerTags,
             **kwargs: Any) -> Dict[str, Any]:
    return asyncio.run(arun_cell(spec, pilot_world, build_policies, ledger_tags=ledger_tags, **kwargs))


def load_cells(path: Path) -> List[Dict[str, Any]]:
    return read_jsonl(path)


def append_cell(path: Path, cell: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(cell, sort_keys=True) + "\n")


async def run_plan(plan: Sequence[CellSpec], worlds: Mapping[str, PilotWorld], build_policies: BuildPolicies, *,
                   ledger_tags: LedgerTags, cells_path: Path, ledger_rows: Optional[LedgerRows] = None,
                   concurrency: int = 4, before_cell: Optional[Callable[[CellSpec], None]] = None,
                   bundle_dir: Optional[Path] = None, reconcile: Optional[Reconcile] = None) -> List[Dict[str, Any]]:
    """Run missing cells, S and S' first (so G is known), at most ``concurrency`` episodes at once.

    A cell whose key is already in ``cells_path`` is never rerun, whatever its result. A BudgetExceeded
    from ``before_cell`` or a SetupError from ``build_policies`` stops the run (cell not recorded); any other
    failure is recorded as an error cell.
    """
    done = {c["key"] for c in load_cells(cells_path)}
    new: List[Dict[str, Any]] = []
    sem = asyncio.Semaphore(concurrency)

    def refs_for(spec: CellSpec) -> Dict[str, float]:
        return {c["arm"]: c["score"] for c in load_cells(cells_path)
                if (c["world"], c["seed"], c["condition"]) == (spec.world, spec.seed, spec.condition)
                and c["arm"] in SCRIPT_ARMS and not c.get("error")}

    async def one(spec: CellSpec) -> None:
        async with sem:
            if before_cell:
                before_cell(spec)
            try:
                cell = await arun_cell(spec, worlds[spec.world], build_policies, ledger_tags=ledger_tags,
                                       ledger_rows=ledger_rows, reconcile=reconcile, refs=refs_for(spec),
                                       bundle_dir=bundle_dir)
            except (BudgetExceeded, SetupError):
                raise
            except Exception as exc:
                cell = {**spec.to_dict(), "key": spec.key, "score": None, "g": None,
                        "error": f"{type(exc).__name__}: {exc}"[:300]}
            append_cell(cells_path, cell)
            new.append(cell)

    todo = [s for s in plan if s.key not in done]
    for phase in ([s for s in todo if s.arm in SCRIPT_ARMS], [s for s in todo if s.arm not in SCRIPT_ARMS]):
        results = await asyncio.gather(*(one(s) for s in phase), return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                raise r
    return new


@dataclass
class Hooks:
    """The injection points the integrator wires for live mode (see scripts/v4_pilot.py)."""

    build_policies: BuildPolicies
    ledger_tags: LedgerTags
    ledger_rows: LedgerRows
    make_backend: Callable[[str], Any]  # name ("jev", "laya", "qwen3.5-9b", "deepseek") -> DecisionBackend
    reconcile: Optional[Reconcile] = None  # physical calls vs ledger rows, merged into each cell


def script_score(pilot_world: PilotWorld, seed: int, world_condition: str, script_condition: str,
                 adapted: bool) -> float:
    """Score of a script on a world, with no model: used by the validity check."""
    world = pilot_world.make_world(seed, world_condition)
    config = RunConfig(f"validity-{pilot_world.name}-{seed}", seed=seed, arm="S-prime" if adapted else "S",
                       max_ticks=int(pilot_world.describe().get("max_ticks", 100)))
    Scheduler(world, {}, BoardField(), config, default_policy=pilot_world.script(script_condition, adapted=adapted),
              record_frames=False).run()
    return float(pilot_world.score(world))


def validity_check(pilot_world: PilotWorld, seeds: Sequence[int] = DEV_SEEDS) -> Dict[str, Any]:
    """Goal 4.3: keep a variant only if S' >= 0.9 S on the base task and S <= 0.5 S' on the variant."""
    if uses_eval_seeds(seeds):
        raise ValueError("the validity check uses development seeds only")

    def avg(xs: Sequence[float]) -> float:
        return sum(xs) / len(xs)

    out: Dict[str, Any] = {"world": pilot_world.name, "seeds": list(seeds), "variants": {}}
    for v in [c for c in CONDITIONS if c != "base"]:
        s_base = avg([script_score(pilot_world, s, "base", "base", False) for s in seeds])
        sp_base = avg([script_score(pilot_world, s, "base", v, True) for s in seeds])
        s_var = avg([script_score(pilot_world, s, v, v, False) for s in seeds])
        sp_var = avg([script_score(pilot_world, s, v, v, True) for s in seeds])
        base_ok, var_ok = sp_base >= 0.9 * s_base, s_var <= 0.5 * sp_var
        out["variants"][v] = {"S_base": s_base, "S_prime_base": sp_base, "S_variant": s_var, "S_prime_variant": sp_var,
                              "S_prime_keeps_base": base_ok, "S_fails_variant": var_ok, "valid": base_ok and var_ok}
    return out


# --- dry-run kit (fake policies, backend and ledger; no network, no keys) -----

_DRY_TAGS: contextvars.ContextVar = contextvars.ContextVar("v4_dry_tags", default={})
_PRICE = {"nous": (0.106e-6, 0.513e-6), "jev": (0.042e-6, 0.0)}


class DryKit:
    """Fake ledger, policies and backend with the same shapes as the live wiring."""

    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    @contextlib.contextmanager
    def tags(self, **tags: Any) -> Iterator[None]:
        token = _DRY_TAGS.set(tags)
        try:
            yield
        finally:
            _DRY_TAGS.reset(token)

    def rows_for(self, run_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.rows if r["run"] == run_id]

    def build_policies(self, spec: CellSpec, pilot_world: PilotWorld, world: World) -> PolicySet:
        arm = ARMS[spec.arm]
        if arm.decider in ("script", "script_adapted"):
            return PolicySet(default_policy=pilot_world.script(spec.condition, adapted=arm.decider == "script_adapted"))
        return PolicySet(default_policy=_DryPolicy(self, pilot_world.sensor(), arm))

    def backend(self, name: str) -> "DryBackend":
        return DryBackend(name)


class _DryPolicy:
    def __init__(self, kit: DryKit, sensor: Any, arm: ArmSpec) -> None:
        self.kit, self.sensor, self.arm = kit, sensor, arm

    def describe(self) -> Dict[str, Any]:
        return {"policy": "dry", "arm": self.arm.name}

    def decide(self, view: LocalView) -> Intent:
        rng = random.Random(view.seed)
        sensed = self.sensor.sense(view)
        reports = self.arm.decider == "decision_model" and rng.random() < 0.1
        action = REPORT if reports else rng.choice(sorted(sensed.actions))
        escalated = ["move"] if self.arm.escalation and rng.random() < 0.2 else []
        n_in, n_out = len(sensed.text) // 4, 8
        provider = "nous" if self.arm.backend == "nous" else self.arm.backend
        price = _PRICE.get(provider, (0.0, 0.0))
        role = "every_agent" if self.arm.decider == "every_agent" else "worker"
        self.kit.rows.append({**_DRY_TAGS.get(), "role": role,
                              "backend": provider, "model": self.arm.model, "input_tokens": n_in,
                              "output_tokens": n_out, "latency_s": 0.01 + rng.random() * 0.05,
                              "cost_usd": n_in * price[0] + n_out * price[1]})
        meta = {"escalated": escalated} if self.arm.decider == "decision_model" else {}
        return Intent(action=action, meta=meta)


class DryBackend:
    """Deterministic fake decision backend for calibrate --dry-run."""

    def __init__(self, name: str) -> None:
        self.name = name

    def describe(self) -> Dict[str, Any]:
        return {"backend": "dry", "model": f"dry-{self.name}"}

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        rng = random.Random(int(hashlib.sha256((self.name + request.request_hash).encode()).hexdigest()[:12], 16))
        answers = {}
        for qid, q in request.questions.items():
            if q.type == "noul":
                p = round(rng.random(), 3)
                answers[qid] = Answer("noul", p, {"yes": p, "no": 1 - p})
            else:
                top = rng.choice(q.options)
                c = round(0.5 + rng.random() * 0.5, 3)
                rest = [o for o in q.options if o != top]
                probs = {top: c, **{o: (1 - c) / len(rest) for o in rest}}
                answers[qid] = Answer("choice", top, probs, c)
        check_answers(request, answers)
        return DecisionResponse(answers, f"dry-{self.name}", request.request_hash, 50, 5)
