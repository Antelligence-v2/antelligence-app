"""Stateful EnvAdapter runner with RealismContract, S baseline, L0/L1Gate metering, and Tier B branching."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from antelligence.harness.core import (
    Action,
    EnvAdapter,
    EnvSnapshot,
    EpisodeOutcome,
    Observation,
    RealismContract,
)
from antelligence.harness.games.checker import CheckDecision, GameChecker
from antelligence.harness.games.memory import EpisodeMemory, extract_scalar_facts
from antelligence.harness.replay import BranchResult
from antelligence.record.l1_gate import L1Gate


@dataclass(frozen=True)
class PolicyDecision:
    """Action proposal from a policy/model stack with honest resource accounting."""

    action: Action
    tokens_in: int = 0
    tokens_out: int = 0
    cost_microusd: int = 0
    latency_s: float = 0.0
    model: str = "maker"
    format_ok: bool = True
    note: Optional[str] = None


@dataclass(frozen=True)
class GameEpisodeResult:
    """Full episode outcome with 4-axis telemetry and L1Gate provenance."""

    seed: int
    score: float
    steps: int
    done: bool
    violations: int
    cost_usd: float
    latency_s: float
    decision_latencies_s: List[float]
    state_hash: str
    l1_spent_microusd: int
    l1_calls: int
    checker_fires: int
    baseline_score: float
    fidelity_tier: str
    l0_path: Optional[str] = None
    info: Mapping[str, Any] = field(default_factory=dict)
    status: str = "complete"
    aborted: bool = False
    abort_reason: Optional[str] = None


PolicyFn = Callable[[Observation, Optional[EpisodeMemory]], Union[PolicyDecision, Action]]


def validate_env_adapter(env: Any, seed: int = 0) -> EpisodeOutcome:
    """Enforce mandatory RealismContract and scripted S baseline on an EnvAdapter."""
    if not isinstance(getattr(env, "realism", None), RealismContract):
        raise ValueError("EnvAdapter rejected: missing valid RealismContract")
    baseline_fn = getattr(env, "no_model_baseline", None)
    if not callable(baseline_fn):
        raise ValueError("EnvAdapter rejected: missing mandatory scripted S baseline (no_model_baseline)")
    outcome = baseline_fn(seed)
    if not isinstance(outcome, EpisodeOutcome):
        raise ValueError("EnvAdapter rejected: no_model_baseline must return EpisodeOutcome")
    return outcome


def _coerce_decision(raw: Union[PolicyDecision, Action], elapsed_s: float) -> PolicyDecision:
    if isinstance(raw, PolicyDecision):
        return raw if raw.latency_s > 0 else PolicyDecision(
            action=raw.action,
            tokens_in=raw.tokens_in,
            tokens_out=raw.tokens_out,
            cost_microusd=raw.cost_microusd,
            latency_s=elapsed_s,
            model=raw.model,
            format_ok=raw.format_ok,
            note=raw.note,
        )
    return PolicyDecision(action=raw, latency_s=elapsed_s)


def run_episode(
    env: EnvAdapter,
    policy: PolicyFn,
    *,
    seed: int = 0,
    config: Optional[Mapping[str, Any]] = None,
    max_steps: int = 50,
    use_memory: bool = True,
    checker: Optional[GameChecker] = None,
    gate: Optional[L1Gate] = None,
    l0_path: Optional[Union[str, Path]] = None,
    l1_caps: Optional[Mapping[str, int]] = None,
    run_id: Optional[str] = None,
) -> GameEpisodeResult:
    """Run one stateful EnvAdapter episode with optional EpisodeMemory, GameChecker, and L1Gate."""
    baseline = validate_env_adapter(env, seed=seed)
    owns_gate = False
    if gate is None and l0_path is not None:
        caps = dict(l1_caps or {"spend_microusd": 1_000_000, "max_steps": max_steps * 3 + 10, "max_depth": 2})
        gate = L1Gate(str(l0_path), run_id or f"game-seed-{seed}", "game_episode", ["env_step"], caps)
        owns_gate = True

    memory: Optional[EpisodeMemory] = EpisodeMemory() if use_memory else None
    obs = env.reset(seed, config)
    if memory is not None:
        initial_facts_fn = getattr(env, "initial_facts", None)
        if callable(initial_facts_fn):
            seeded = initial_facts_fn(obs)
            if isinstance(seeded, Mapping):
                memory.update_facts(seeded)
        else:
            memory.update_facts(extract_scalar_facts(obs))

    t0 = time.perf_counter()
    total_score = 0.0
    violations = 0
    checker_fires = 0
    steps = 0
    done = False
    aborted = False
    abort_reason: Optional[str] = None
    last_hash = ""
    last_info: Mapping[str, Any] = {}
    decision_latencies: List[float] = []

    for step_idx in range(max_steps):
        d0 = time.perf_counter()
        decision = _coerce_decision(policy(obs, memory), time.perf_counter() - d0)
        decision_latencies.append(decision.latency_s)

        if gate is not None and (decision.cost_microusd > 0 or decision.tokens_in > 0 or decision.tokens_out > 0):
            reserve = max(decision.cost_microusd, 1)
            prev_refusals = len(gate.refusals)
            if not gate.model_call(decision.model, f"step={step_idx}", reserve):
                aborted = True
                if len(gate.refusals) > prev_refusals:
                    abort_reason = f"l1_gate_refused:{gate.refusals[-1]}"
                elif any(Path(k).exists() for k in gate.kill_paths):
                    abort_reason = "l1_gate_refused:kill_file"
                elif gate.end_status == "aborted":
                    abort_reason = "l1_gate_refused:aborted"
                else:
                    abort_reason = "l1_gate_refused"
                break
            gate.model_result(
                decision.tokens_in,
                decision.tokens_out,
                decision.cost_microusd,
                str(decision.action),
                format_ok=decision.format_ok,
            )

        if memory is not None and decision.note:
            memory.add_unverified_note(decision.note, step_idx=step_idx)

        action = decision.action
        if checker is not None:
            cd: CheckDecision = checker.check(env, obs, action, memory, gate=gate)
            if cd.used_cross_family:
                checker_fires += 1
            if not cd.allowed:
                if cd.override_action is not None:
                    action = cd.override_action
                else:
                    legal = env.legal_actions(obs)
                    action = legal[0] if legal else action

        res = env.step(action)
        steps += 1
        total_score += float(res.reward)
        done = bool(res.done)
        last_hash = res.state_hash
        last_info = res.info
        if res.info.get("violation"):
            violations += int(res.info.get("violation_count", 1))
        if memory is not None:
            memory.record_step(
                step_idx,
                res.obs,
                action,
                reward=res.reward,
                done=done,
                state_hash=res.state_hash,
                info=res.info,
            )
        if gate is not None:
            gate.note(json.dumps({"step": step_idx, "action": action, "reward": res.reward, "hash": res.state_hash}, sort_keys=True))
        obs = res.obs
        if done:
            break

    wall_s = time.perf_counter() - t0
    l1_spent = gate.subtree_spent() if gate is not None else 0
    l1_calls = gate.subtree_calls() if gate is not None else 0
    status = "aborted" if aborted else ("pass" if done else "complete")
    if owns_gate and gate is not None:
        gate.end(status, detail=abort_reason or "")

    info_out = dict(last_info)
    info_out["status"] = status
    if aborted:
        info_out["aborted"] = True
        info_out["abort_reason"] = abort_reason

    return GameEpisodeResult(
        seed=seed,
        score=total_score,
        steps=steps,
        done=done,
        violations=violations,
        cost_usd=l1_spent / 1_000_000.0,
        latency_s=wall_s,
        decision_latencies_s=decision_latencies,
        state_hash=last_hash,
        l1_spent_microusd=l1_spent,
        l1_calls=l1_calls,
        checker_fires=checker_fires,
        baseline_score=baseline.score,
        fidelity_tier=env.realism.fidelity_tier,
        l0_path=str(l0_path) if l0_path is not None else None,
        info=info_out,
        status=status,
        aborted=aborted,
        abort_reason=abort_reason,
    )


class TierBBranchRunner:
    """Tier B ``BranchingReplay`` implementation restoring EnvSnapshot + RNG state."""

    def branch(
        self,
        env: EnvAdapter,
        snapshot: EnvSnapshot,
        variants: Mapping[str, Callable[[Any], Action]],
        *,
        max_steps: int = 100,
    ) -> Dict[str, BranchResult]:
        validate_env_adapter(env)
        if not env.supports_checkpoint:
            raise ValueError("EnvAdapter does not support Tier B checkpoints (supports_checkpoint=False)")
        out: Dict[str, BranchResult] = {}
        for name, policy in variants.items():
            env.restore(snapshot)
            restored = env.snapshot()
            if restored.state_hash != snapshot.state_hash:
                raise ValueError(
                    f"Tier B restore mismatch for {name!r}: {restored.state_hash} != {snapshot.state_hash}"
                )
            obs = snapshot.obs
            total = 0.0
            steps = 0
            end_hash = snapshot.state_hash
            for _ in range(max_steps):
                res = env.step(policy(obs))
                total += float(res.reward)
                steps += 1
                end_hash = res.state_hash
                obs = res.obs
                if res.done:
                    break
            out[name] = BranchResult(
                variant=name,
                start_hash=snapshot.state_hash,
                end_hash=end_hash,
                outcome=EpisodeOutcome(score=total, steps=steps, info={"end_hash": end_hash}),
            )
        return out
