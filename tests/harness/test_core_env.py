"""Tests for core protocols, ToolRegistry, RealismContract, and EnvAdapter contract."""

from __future__ import annotations

import hashlib
import random
from typing import Any, Mapping, Optional, Sequence

import pytest

from antelligence.harness.core import (
    Action,
    Artifact,
    EnvSnapshot,
    EpisodeOutcome,
    Observation,
    RealismContract,
    StepResult,
    Task,
    TaskAdapter,
    ToolRegistry,
    ToolSpec,
    input_hash,
    verify_env_contract,
)


class ToyStochasticEnv:
    """Tiny stateful stochastic env with RNG state captured in EnvSnapshot."""

    supports_checkpoint = True
    realism = RealismContract(
        fidelity_tier="calibrated_sim",
        units={"score": "points", "step": "tick"},
        invariants=("0 <= pos <= 10",),
    )

    def __init__(self, *, capture_rng: bool = True, deterministic_reset: bool = True) -> None:
        self._capture_rng = capture_rng
        self._deterministic_reset = deterministic_reset
        self._rng = random.Random(0)
        self._pos = 0
        self._step_idx = 0

    def _state_hash(self) -> str:
        raw = f"{self._pos}:{self._step_idx}:{self._rng.getstate()[1][0]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def reset(self, seed: int, config: Optional[Mapping[str, Any]] = None) -> Observation:
        actual_seed = seed if self._deterministic_reset else seed + random.randrange(1, 10000)
        self._rng = random.Random(actual_seed)
        self._pos = 0
        self._step_idx = 0
        return {"pos": self._pos, "step": self._step_idx}

    def legal_actions(self, obs: Observation) -> Optional[Sequence[Action]]:
        return ("stay", "move")

    def step(self, action: Action) -> StepResult:
        delta = self._rng.randint(1, 3) if action == "move" else 0
        self._pos = min(10, self._pos + delta)
        self._step_idx += 1
        done = self._pos >= 10 or self._step_idx >= 10
        obs = {"pos": self._pos, "step": self._step_idx}
        return StepResult(
            obs=obs,
            reward=float(delta),
            done=done,
            info={"delta": delta},
            state_hash=self._state_hash(),
        )

    def snapshot(self) -> EnvSnapshot:
        blob = {
            "pos": self._pos,
            "step_idx": self._step_idx,
            "rng": self._rng.getstate() if self._capture_rng else None,
        }
        return EnvSnapshot(
            state_hash=self._state_hash(),
            blob=blob,
            step_idx=self._step_idx,
            obs={"pos": self._pos, "step": self._step_idx},
        )

    def restore(self, snap: EnvSnapshot) -> None:
        self._pos = snap.blob["pos"]
        self._step_idx = snap.blob["step_idx"]
        if snap.blob["rng"] is not None:
            self._rng.setstate(snap.blob["rng"])

    def no_model_baseline(self, seed: int) -> EpisodeOutcome:
        obs = self.reset(seed)
        total = 0.0
        steps = 0
        while True:
            res = self.step("move")
            total += res.reward
            steps += 1
            obs = res.obs
            if res.done:
                break
        return EpisodeOutcome(score=total, steps=steps, info={"final_pos": obs["pos"]})


class ToyTaskAdapter:
    def format_input(self, task: Task) -> Any:
        return f"triage: {task.payload['text']}"

    def parse_output(self, task: Task, raw: str) -> Artifact:
        ok = raw.strip() in {"low", "high"}
        return Artifact(task_id=task.id, tool="triage", answer=raw.strip() if ok else None, format_ok=ok)

    def score(self, task: Task, artifact: Artifact) -> Optional[float]:
        if not artifact.format_ok:
            return 0.0
        return float(artifact.answer == task.payload.get("label"))

    def audit_shortcuts(self, tasks: Sequence[Task]) -> Mapping[str, Any]:
        return {"n": len(tasks), "ok": True}


def test_env_adapter_contract_passes_on_toy_env():
    env = ToyStochasticEnv()
    problems = verify_env_contract(env, seed=42, policy=lambda o: "move", max_steps=15)
    assert problems == []
    baseline = env.no_model_baseline(42)
    assert baseline.score >= 10.0
    assert env.realism.fidelity_tier == "calibrated_sim"


def test_env_adapter_contract_catches_missing_rng_and_nondeterminism():
    bad_rng = ToyStochasticEnv(capture_rng=False)
    problems = verify_env_contract(bad_rng, seed=7, policy=lambda o: "move", max_steps=10)
    assert any("restore()" in p for p in problems)

    bad_reset = ToyStochasticEnv(deterministic_reset=False)
    problems2 = verify_env_contract(bad_reset, seed=7, policy=lambda o: "move", max_steps=10)
    assert any("reset(seed)" in p for p in problems2)


def test_realism_contract_validates_fidelity_tier():
    with pytest.raises(ValueError, match="fidelity_tier"):
        RealismContract(fidelity_tier="magic")


def test_task_adapter_and_tool_registry():
    adapter = ToyTaskAdapter()
    assert isinstance(adapter, TaskAdapter)
    task = Task(id="t1", kind="triage", payload={"text": "server down", "label": "high"}, created_at="2026-11-01")
    art = adapter.parse_output(task, "high")
    assert art.format_ok is True
    assert adapter.score(task, art) == 1.0

    async def dummy(t: Task, deps: Mapping[str, Artifact]) -> Artifact:
        return Artifact(task_id=t.id, tool="x", answer="ok")

    reg = ToolRegistry([ToolSpec(name="x", run=dummy)])
    assert reg.has("x")
    assert reg.names() == ["x"]
    with pytest.raises(ValueError, match="already registered"):
        reg.register(ToolSpec(name="x", run=dummy))
    with pytest.raises(ValueError, match="model_key"):
        reg.register(ToolSpec(name="y", run=dummy, local=True))
    assert input_hash({"a": 1, "b": 2}) == input_hash({"b": 2, "a": 1})
