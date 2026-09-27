"""The tick loop.

Each tick has two phases:

1. **Decide** — every agent observes the same pre-tick state and its policy
   decides. Decisions run concurrently (``asyncio.gather``), so slow LLM
   policies overlap instead of blocking one another.
2. **Apply** — intents are applied in sorted agent order, emitted signals are
   stamped, admitted and deposited (visible from the next tick).

Because every agent decides from the same snapshot and signals are only visible
from the next tick, the result does not depend on which policy answers first.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from antelligence.kernel import events as ev
from antelligence.kernel.canonical import content_hash
from antelligence.kernel.field import FieldFullError, SignalField
from antelligence.kernel.signal import Signal, SignalError
from antelligence.kernel.types import NOOP, Intent, LocalView, Outcome, Policy, World


class Admission(Protocol):
    """Decides whether a stamped signal may enter the field."""

    def check(self, signal: Signal, tick: int) -> Optional[str]:
        """Return None to admit, or a short rejection reason."""
        ...


class MemoryReader(Protocol):
    """Supplies the admitted memory an agent may use this tick."""

    def recall_for(self, agent_id: str, scope: str, tick: int, observation: Mapping[str, Any]) -> Tuple[Any, ...]: ...


class IntentGate(Protocol):
    """Pre-apply verification; a non-None reason blocks the intent."""

    def check(self, agent_id: str, intent: Intent, tick: int) -> Optional[str]: ...


class Recorder(Protocol):
    """Writes evidence from admitted signals and world outcomes; returns transitions."""

    def on_signal(self, signal: Signal, tick: int) -> List[dict]: ...

    def on_outcome(self, scope: str, agent_id: str, intent: Intent, outcome: Outcome, tick: int) -> List[dict]: ...


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    seed: int = 0
    max_ticks: int = 100
    arm: str = "default"
    max_emits_per_tick: int = 8
    policy_timeout_s: Optional[float] = None
    log_observations: bool = False

    def __post_init__(self) -> None:
        if not self.run_id or ":" in self.run_id:
            raise ValueError("run_id must be non-empty and contain no ':'")
        if not self.arm or ":" in self.arm:
            raise ValueError("arm must be non-empty and contain no ':'")
        if self.max_ticks < 1:
            raise ValueError("max_ticks must be positive")
        if self.max_emits_per_tick < 0:
            raise ValueError("max_emits_per_tick must be nonnegative")

    @property
    def scope(self) -> str:
        return f"{self.run_id}:{self.arm}"


@dataclass
class RunResult:
    run_id: str
    arm: str
    scope: str
    ticks: int
    metrics: Dict[str, Any]
    trace_hash: str
    config_hash: str
    event_count: int
    policy_failures: int
    signals_deposited: int
    signals_rejected: int
    stopped_reason: str = "max_ticks"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _describe(component: Any) -> Any:
    if component is None:
        return None
    describe = getattr(component, "describe", None)
    return describe() if callable(describe) else type(component).__name__


def derive_seed(run_seed: int, agent_id: str, tick: int) -> int:
    digest = hashlib.sha256(f"{run_seed}:{agent_id}:{tick}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


class Scheduler:
    def __init__(
        self,
        world: World,
        policies: Mapping[str, Policy],
        field: SignalField,
        config: RunConfig,
        *,
        default_policy: Optional[Policy] = None,
        admission: Optional[Admission] = None,
        memory: Optional[MemoryReader] = None,
        gate: Optional[IntentGate] = None,
        recorder: Optional[Recorder] = None,
        log: Optional[ev.EventLog] = None,
    ) -> None:
        self.world = world
        self.policies = dict(policies)
        self.default_policy = default_policy
        self.field = field
        self.config = config
        self.admission = admission
        self.memory = memory
        self.gate = gate
        self.recorder = recorder
        self.intents_blocked = 0
        self.log = log if log is not None else ev.EventLog()
        self.tick = 0
        self.policy_failures = 0
        self.signals_deposited = 0
        self.signals_rejected = 0
        self._started = False

    # ------------------------------------------------------------------ config
    def _policy_for(self, agent_id: str) -> Policy:
        policy = self.policies.get(agent_id, self.default_policy)
        if policy is None:
            raise KeyError(f"no policy for agent {agent_id!r}")
        return policy

    def config_hash(self) -> str:
        agents = sorted(self.world.agents())
        return content_hash(
            {
                "world": self.world.describe(),
                "seed": self.config.seed,
                "max_ticks": self.config.max_ticks,
                "arm": self.config.arm,
                "max_emits_per_tick": self.config.max_emits_per_tick,
                "policies": {a: self._policy_for(a).describe() for a in agents},
                "admission": _describe(self.admission),
                "gate": _describe(self.gate),
                "memory": self.memory is not None,
                "recorder": self.recorder is not None,
            }
        )

    # -------------------------------------------------------------------- run
    def run(self) -> RunResult:
        return asyncio.run(self.arun())

    async def arun(self) -> RunResult:
        config_hash = self.config_hash()
        if not self._started:
            self._started = True
            self.log.append(
                ev.RUN_STARTED,
                0,
                {"run_id": self.config.run_id, "arm": self.config.arm, "seed": self.config.seed, "config_hash": config_hash},
            )
        stopped = "max_ticks"
        while self.tick < self.config.max_ticks:
            if self.world.done(self.tick):
                stopped = "world_done"
                break
            await self.step()
        else:
            if self.world.done(self.tick):
                stopped = "world_done"
        metrics = self.world.metrics()
        self.log.append(ev.RUN_FINISHED, self.tick, {"stopped_reason": stopped, "metrics": metrics})
        return RunResult(
            run_id=self.config.run_id,
            arm=self.config.arm,
            scope=self.config.scope,
            ticks=self.tick,
            metrics=metrics,
            trace_hash=self.log.trace_hash,
            config_hash=config_hash,
            event_count=len(self.log),
            policy_failures=self.policy_failures,
            signals_deposited=self.signals_deposited,
            signals_rejected=self.signals_rejected,
            stopped_reason=stopped,
            extra={"intents_blocked": self.intents_blocked},
        )

    async def step(self) -> None:
        self.tick += 1
        tick = self.tick
        scope = self.config.scope
        agents = sorted(self.world.agents())
        revision = self.world.revision

        # Phase 1: observe everything first, from one consistent snapshot.
        views: List[LocalView] = []
        for agent_id in agents:
            observation = self.world.observe(agent_id, tick)
            sensed = tuple(self.field.sense(scope, tick, observation.sense, exclude_sender=agent_id))
            memory = (
                self.memory.recall_for(agent_id, scope, tick, observation.data) if self.memory is not None else ()
            )
            view = LocalView(
                agent_id=agent_id,
                tick=tick,
                revision=revision,
                seed=derive_seed(self.config.seed, agent_id, tick),
                observation=observation.data,
                signals=sensed,
                memory=tuple(memory),
            )
            record = {"observation_hash": content_hash(observation.data), "signal_ids": [s.id for s in sensed]}
            if memory:
                record["memory_ids"] = [getattr(m, "id", None) for m in memory]
            if self.config.log_observations:
                record["observation"] = observation.data
            self.log.append(ev.OBSERVED, tick, record, agent_id)
            views.append(view)

        intents = await asyncio.gather(*(self._decide(view) for view in views))

        # Phase 2: apply in deterministic order.
        for view, intent in zip(views, intents):
            agent_id = view.agent_id
            if intent.action != NOOP or intent.rationale or intent.meta:
                self.log.append(ev.DECIDED, tick, intent.to_dict(), agent_id)
            blocked = self.gate.check(agent_id, intent, tick) if self.gate is not None else None
            if blocked is not None:
                self.intents_blocked += 1
                self.log.append(ev.INTENT_BLOCKED, tick, {"action": intent.action, "reason": blocked,
                                                          "cites": list(intent.cites)}, agent_id)
                outcome = Outcome(False, blocked, effects={"blocked": True})
            else:
                outcome = self.world.apply(agent_id, intent, tick)
            self.log.append(ev.OUTCOME, tick, {"action": intent.action, **outcome.to_dict()}, agent_id)
            if self.recorder is not None:
                self._log_memory(self.recorder.on_outcome(scope, agent_id, intent, outcome, tick), agent_id)
            self._emit(agent_id, intent, view, tick)

        for signal in self.field.expire(tick):
            self.log.append(ev.SIGNAL_EXPIRED, tick, {"signal_id": signal.id})
        self.world.step_environment(tick)
        self.log.append(ev.TICK_ENDED, tick, {"revision": self.world.revision, "metrics": self.world.metrics()})

    async def _decide(self, view: LocalView) -> Intent:
        policy = self._policy_for(view.agent_id)
        try:
            result = policy.decide(view)
            if inspect.isawaitable(result):
                if self.config.policy_timeout_s is not None:
                    result = await asyncio.wait_for(result, self.config.policy_timeout_s)
                else:
                    result = await result
            if not isinstance(result, Intent):
                raise TypeError(f"policy returned {type(result).__name__}, expected Intent")
            return result
        except Exception as exc:  # fail closed: the agent does nothing this tick
            self.policy_failures += 1
            self.log.append(
                ev.POLICY_FAILED, view.tick, {"error": type(exc).__name__, "message": str(exc)[:500]}, view.agent_id
            )
            return Intent(action=NOOP)

    def _emit(self, agent_id: str, intent: Intent, view: LocalView, tick: int) -> None:
        for index, draft in enumerate(intent.emit):
            if index >= self.config.max_emits_per_tick:
                self._reject(agent_id, tick, None, "emit_budget_exceeded", {"kind": draft.kind})
                continue
            try:
                signal = Signal.stamp(draft, sender=agent_id, scope=self.config.scope, tick=tick, revision=view.revision)
            except SignalError as exc:
                self._reject(agent_id, tick, None, "invalid_signal", {"kind": draft.kind, "message": str(exc)})
                continue
            reason = self.admission.check(signal, tick) if self.admission is not None else None
            if reason is not None:
                self._reject(agent_id, tick, signal, reason)
                continue
            try:
                stored = self.field.deposit(signal)
            except FieldFullError:
                self._reject(agent_id, tick, signal, "field_full")
                continue
            if not stored:
                self._reject(agent_id, tick, signal, "duplicate")
                continue
            self.signals_deposited += 1
            self.log.append(ev.SIGNAL_DEPOSITED, tick, signal.to_dict(), agent_id)
            if self.recorder is not None:
                self._log_memory(self.recorder.on_signal(signal, tick), agent_id)

    def _log_memory(self, transitions: List[dict], agent_id: str) -> None:
        for transition in transitions:
            self.log.append(ev.MEMORY_CHANGED, transition.get("tick", self.tick), transition, agent_id)

    def _reject(self, agent_id: str, tick: int, signal: Optional[Signal], reason: str, extra: Optional[dict] = None) -> None:
        self.signals_rejected += 1
        data = {"reason": reason, "signal_id": signal.id if signal else None, **(extra or {})}
        if signal is not None:
            data["kind"] = signal.kind
        self.log.append(ev.SIGNAL_REJECTED, tick, data, agent_id)
