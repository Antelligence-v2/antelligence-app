"""Tests for PR 5 interactive games: EpisodeMemory, GameChecker/L1Gate, Tier B replay, A/B matrix, recovery, and World bridge."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional

import pytest

from antelligence.harness.core import EpisodeOutcome, RealismContract, verify_env_contract
from antelligence.harness.games import (
    ABVariant,
    CityOpsEnv,
    CrossFamilyVerdict,
    EpisodeMemory,
    GameChecker,
    PolicyDecision,
    TierBBranchRunner,
    WorldEnvAdapter,
    load_city_ops_scenarios,
    run_ab_matrix,
    run_episode,
    shortest_path,
    validate_env_adapter,
)
from antelligence.harness.replay import BranchingReplay
from antelligence.kernel.types import Intent, Observation, Outcome as KernelOutcome, World
from antelligence.record import L1Gate, diagnose, recover, validate


def _memory_aware_policy(obs: Mapping[str, Any], mem: Optional[EpisodeMemory]) -> PolicyDecision:
    """Uses EpisodeMemory verified facts; falls back to blind wait if stateless."""
    if mem is None:
        # Stateless agent cannot remember transient pickup/dropoff after step 0.
        act = "accept_job" if not obs["job_accepted"] else "wait"
        return PolicyDecision(action=act, tokens_in=20, tokens_out=5, cost_microusd=10)

    pickup = mem.facts.get("pickup")
    dropoff = mem.facts.get("dropoff")
    if not obs["job_accepted"]:
        act = "accept_job"
    elif obs["fuel"] <= 3 and obs["node"] == "station":
        act = "refuel"
    elif not obs["cargo"] and obs["node"] == pickup:
        act = "pickup"
    elif obs["cargo"] and obs["node"] == dropoff:
        act = "deliver"
    else:
        target = "station" if obs["fuel"] <= 3 else (dropoff if obs["cargo"] else pickup)
        nxt = shortest_path(obs["node"], str(target))[1]
        red = set(obs["local_red_lights"])
        act = "wait" if (obs["node"] in red or nxt in red) else f"move:{nxt}"
    return PolicyDecision(
        action=act,
        tokens_in=30,
        tokens_out=8,
        cost_microusd=15,
        note=f"heading toward {dropoff or pickup}",
    )


def _reckless_stateless_policy(obs: Mapping[str, Any], mem: Optional[EpisodeMemory]) -> PolicyDecision:
    if not obs["job_accepted"]:
        return PolicyDecision(action="accept_job", tokens_in=15, tokens_out=4, cost_microusd=8)
    nxt = obs["neighbors"][0]
    return PolicyDecision(action=f"sprint:{nxt}", tokens_in=15, tokens_out=4, cost_microusd=8)


def test_stateless_vs_memory_smoke_and_fixture():
    scenarios = load_city_ops_scenarios()
    assert len(scenarios) >= 2
    cfg = scenarios[0]

    env = CityOpsEnv()
    assert verify_env_contract(env, seed=7, max_steps=20) == []

    stateless = run_episode(CityOpsEnv(), _memory_aware_policy, seed=7, config=cfg, use_memory=False)
    with_mem = run_episode(CityOpsEnv(), _memory_aware_policy, seed=7, config=cfg, use_memory=True)

    assert not stateless.info.get("delivered")
    assert with_mem.info.get("delivered") is True
    assert with_mem.score > stateless.score

    mem = EpisodeMemory()
    mem.add_unverified_note("guess: turn left", step_idx=1, source="llm")
    d = mem.to_dict()
    assert "verified" in d and "unverified_notes" in d
    assert d["unverified_notes"][0]["tag"] == "unverified_note"


def test_ab_matrix_paired_bootstrap_four_axes(tmp_path):
    variants = [
        ABVariant(
            name="reckless_stateless",
            model_stack="slm-tiny",
            harness_variant="stateless",
            policy=_reckless_stateless_policy,
            use_memory=False,
        ),
        ABVariant(
            name="memory_checked",
            model_stack="slm-tiny+cross-checker",
            harness_variant="memory+l1-checker",
            policy=_memory_aware_policy,
            use_memory=True,
        ),
    ]
    report = run_ab_matrix(
        CityOpsEnv,
        variants,
        seeds=[1, 2, 3, 4, 5],
        scenario_config={"max_steps": 30},
        baseline_name="reckless_stateless",
        l0_dir=tmp_path,
        bootstrap_reps=500,
    )
    assert report["baseline"] == "reckless_stateless"
    for name in ("reckless_stateless", "memory_checked"):
        v = report["variants"][name]
        assert v["fidelity_tier"] == "calibrated_sim"
        assert {"decision_p50_s", "decision_p95_s", "mean_wall_time_s"} <= set(v["latency"])
        assert {"mean_score", "completion_rate", "baseline_S_score", "lift_over_S"} <= set(v["accuracy"])
        assert {"total_violations", "violation_free_rate"} <= set(v["safety"])
        assert {"total_cost_usd", "mean_cost_usd", "total_l1_calls", "checker_fires"} <= set(v["cost"])

    paired = report["paired_vs_baseline"]["memory_checked"]
    assert paired["score_gain"] > 0
    assert paired["score_ci95"][0] > 0
    assert paired["violations_delta"] <= 0


def test_tier_b_snapshot_restore_counterfactual_branching():
    env = CityOpsEnv()
    obs = env.reset(seed=11)
    obs = env.step("accept_job").obs
    snap = env.snapshot()

    brancher = TierBBranchRunner()
    assert isinstance(brancher, BranchingReplay)

    variants = {
        "wait": lambda o: "wait",
        "sprint": lambda o: f"sprint:{o['neighbors'][0]}",
    }
    res1 = brancher.branch(env, snap, variants, max_steps=5)
    res2 = brancher.branch(env, snap, variants, max_steps=5)

    # Identical state_hash + identical RNG draws on replay
    assert res1["wait"].start_hash == snap.state_hash
    assert res1["wait"].end_hash == res2["wait"].end_hash
    assert res1["sprint"].end_hash == res2["sprint"].end_hash
    assert res1["wait"].outcome.score == res2["wait"].outcome.score
    assert res1["sprint"].outcome.score != res1["wait"].outcome.score


def test_missing_s_baseline_or_realism_contract_rejected():
    class NoRealism:
        supports_checkpoint = False

        def no_model_baseline(self, seed: int) -> EpisodeOutcome:
            return EpisodeOutcome(score=0.0)

    class NoBaseline:
        supports_checkpoint = False
        realism = RealismContract(fidelity_tier="proxy")

    with pytest.raises(ValueError, match="RealismContract"):
        validate_env_adapter(NoRealism())
    with pytest.raises(ValueError, match="no_model_baseline"):
        run_episode(NoBaseline(), lambda o, m: "wait")  # type: ignore[arg-type]


def test_game_checker_selective_l1_metering(tmp_path):
    checker_calls = 0

    def cross_family(obs: Mapping[str, Any], action: Any, mem: Optional[EpisodeMemory]) -> CrossFamilyVerdict:
        nonlocal checker_calls
        checker_calls += 1
        return CrossFamilyVerdict(
            approved=False,
            reason="blocked_high_stakes_sprint",
            alternative="wait",
            tokens_in=50,
            tokens_out=12,
            cost_microusd=250,
        )

    checker = GameChecker(
        high_stakes_fn=lambda obs, act, mem: str(act).startswith("sprint:"),
        cross_family_fn=cross_family,
        worst_case_microusd=500,
    )

    # Routine moves: 0 cross-family calls (no per-tick Queen)
    l0_routine = tmp_path / "routine.jsonl"
    res_routine = run_episode(
        CityOpsEnv(),
        _memory_aware_policy,
        seed=3,
        max_steps=6,
        checker=checker,
        l0_path=l0_routine,
    )
    assert checker_calls == 0
    assert res_routine.checker_fires == 0

    # High-stakes sprint: fires GameChecker and meters in L1Gate
    l0_hs = tmp_path / "high_stakes.jsonl"
    res_hs = run_episode(
        CityOpsEnv(),
        _reckless_stateless_policy,
        seed=3,
        max_steps=3,
        checker=checker,
        l0_path=l0_hs,
    )
    assert checker_calls == 2  # step 0 is accept_job (routine), steps 1-2 are sprint (high-stakes)
    assert res_hs.checker_fires == 2
    assert res_hs.l1_spent_microusd >= 500
    assert res_hs.violations == 0  # checker overrode sprint -> wait


def test_mid_episode_sigkill_l0_recovery(tmp_path):
    l0_path = tmp_path / "crashed_ep.jsonl"
    gate = L1Gate(
        str(l0_path),
        "sigkill-ep",
        "game_episode",
        ["env_step"],
        {"spend_microusd": 100_000, "max_steps": 50, "max_depth": 2},
    )
    run_episode(CityOpsEnv(), _memory_aware_policy, seed=5, max_steps=4, gate=gate)
    # Simulate mid-episode SIGKILL: close fd without run_end and append torn tail bytes
    gate.close_file()
    with l0_path.open("ab") as fh:
        fh.write(b'{"seq":99,"kind":"note","torn":')

    diag = diagnose(l0_path.read_bytes())
    assert diag["cls"] == "torn_tail"

    rec = recover(str(l0_path))
    assert rec["cls"] == "torn_tail"
    assert rec["recovered_path"] is not None
    with open(rec["recovered_path"], "rb") as fh:
        assert validate(fh.read())["valid"] is True


def test_world_bridge_with_kernel_world():
    class TinyWorld:
        def __init__(self) -> None:
            self._rev = 0
            self._pos = 0

        @property
        def revision(self) -> int:
            return self._rev

        def agents(self) -> List[str]:
            return ["a1"]

        def observe(self, agent_id: str, tick: int) -> Observation:
            return Observation(data={"pos": self._pos, "tick": tick})

        def apply(self, agent_id: str, intent: Intent, tick: int) -> KernelOutcome:
            if intent.action == "step":
                self._pos += 1
                self._rev += 1
                return KernelOutcome(accepted=True)
            return KernelOutcome(accepted=False, reason="noop")

        def step_environment(self, tick: int) -> None:
            pass

        def metrics(self) -> Dict[str, Any]:
            return {"pos": self._pos}

        def done(self, tick: int) -> bool:
            return self._pos >= 3 or tick >= 10

        def describe(self) -> Dict[str, Any]:
            return {"name": "tiny"}

    world = TinyWorld()
    assert isinstance(world, World)
    adapter = WorldEnvAdapter(
        lambda _seed: TinyWorld(),
        "a1",
        RealismContract(fidelity_tier="proxy", units={"pos": "steps"}),
        baseline_fn=lambda w, aid, s: EpisodeOutcome(score=3.0, steps=3),
        legal_actions_fn=lambda obs: ("step", "noop"),
    )
    assert verify_env_contract(adapter, seed=0, policy=lambda o: "step", max_steps=5) == []
    res = run_episode(adapter, lambda o, m: "step", seed=0, max_steps=5)
    assert res.done is True
    assert res.steps == 3


def test_l1_gate_refusal_aborts_on_budget_cap_and_kill_file(tmp_path):
    class CountingEnv(CityOpsEnv):
        def __init__(self) -> None:
            super().__init__()
            self.step_calls = 0

        def step(self, action: Any):
            self.step_calls += 1
            return super().step(action)

        def no_model_baseline(self, seed: int) -> EpisodeOutcome:
            return CityOpsEnv().no_model_baseline(seed)

    # 1. Budget exhausted on step 0: abort cleanly, never call env.step().
    env0 = CountingEnv()
    l0_cap0 = tmp_path / "cap0.jsonl"
    res0 = run_episode(
        env0,
        _memory_aware_policy,
        seed=7,
        max_steps=5,
        l0_path=l0_cap0,
        l1_caps={"spend_microusd": 10, "max_steps": 10, "max_depth": 2},
    )
    assert res0.aborted is True
    assert res0.status == "aborted"
    assert res0.abort_reason == "l1_gate_refused:spend_cap"
    assert res0.info.get("aborted") is True
    assert res0.info.get("abort_reason") == "l1_gate_refused:spend_cap"
    assert res0.info.get("status") == "aborted"
    assert res0.done is False
    assert res0.steps == 0
    assert env0.step_calls == 0
    assert res0.l1_calls == 0
    assert validate(l0_cap0.read_bytes())["valid"] is True

    # 2. Budget allows 1 call (15 microusd) then refuses step 1: exactly 1 env.step().
    env1 = CountingEnv()
    l0_cap1 = tmp_path / "cap1.jsonl"
    res1 = run_episode(
        env1,
        _memory_aware_policy,
        seed=7,
        max_steps=5,
        l0_path=l0_cap1,
        l1_caps={"spend_microusd": 20, "max_steps": 10, "max_depth": 2},
    )
    assert res1.aborted is True
    assert res1.status == "aborted"
    assert res1.abort_reason == "l1_gate_refused:spend_cap"
    assert res1.done is False
    assert res1.steps == 1
    assert env1.step_calls == 1
    assert res1.l1_calls == 1
    assert res1.l1_spent_microusd == 15
    assert validate(l0_cap1.read_bytes())["valid"] is True

    # 3. Kill file present mid-episode: step 0 completes, step 1 aborts without calling env.step().
    env_kill = CountingEnv()
    l0_kill = tmp_path / "killed.jsonl"
    kill_path = tmp_path / "killed.jsonl.kill"
    calls_seen = 0

    def kill_after_first_step(obs: Mapping[str, Any], mem: Optional[EpisodeMemory]) -> PolicyDecision:
        nonlocal calls_seen
        calls_seen += 1
        if calls_seen == 2:
            kill_path.write_text("stop", encoding="utf-8")
        return _memory_aware_policy(obs, mem)

    res_kill = run_episode(
        env_kill,
        kill_after_first_step,
        seed=7,
        max_steps=5,
        l0_path=l0_kill,
        l1_caps={"spend_microusd": 100_000, "max_steps": 10, "max_depth": 2},
    )
    assert res_kill.aborted is True
    assert res_kill.status == "aborted"
    assert res_kill.abort_reason == "l1_gate_refused:kill_file"
    assert res_kill.info.get("aborted") is True
    assert res_kill.info.get("abort_reason") == "l1_gate_refused:kill_file"
    assert res_kill.done is False
    assert res_kill.steps == 1
    assert env_kill.step_calls == 1
    assert validate(l0_kill.read_bytes())["valid"] is True


def test_custom_env_adapter_populates_memory_facts_generically():
    from antelligence.harness.core import EnvSnapshot, StepResult

    class OrbitalProbeEnv:
        supports_checkpoint = False
        realism = RealismContract(fidelity_tier="proxy", units={"temp": "K"})

        def __init__(self, *, use_hook: bool = False) -> None:
            self._use_hook = use_hook
            self._tick = 0
            self._temp = 290.5

        def reset(self, seed: int, config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
            self._tick = 0
            self._temp = 290.5
            return {
                "sector": f"orbit-{seed}",
                "reactor_temp": self._temp,
                "shields_up": True,
                "beacon_code": "XZ-900",
                "sensors": [1, 2, 3],
                "raw_frame": {"bytes": 128},
                "transient_alert": None,
            }

        def initial_facts(self, obs: Mapping[str, Any]) -> Dict[str, Any]:
            if not self._use_hook:
                return {k: v for k, v in obs.items() if isinstance(v, (bool, int, float, str))}
            return {"custom_seed_tag": f"hook:{obs['sector']}", "beacon_code": obs["beacon_code"]}

        def legal_actions(self, obs: Any):
            return ("stabilize", "coast")

        def step(self, action: Any) -> StepResult:
            self._tick += 1
            self._temp -= 5.0 if action == "stabilize" else 1.0
            obs = {
                "sector": f"orbit-step-{self._tick}",
                "reactor_temp": self._temp,
                "shields_up": True,
                "beacon_code": None,  # transient: must remain remembered from reset
                "sensors": [self._tick],
            }
            return StepResult(
                obs=obs,
                reward=1.0,
                done=self._tick >= 2,
                info={},
                state_hash=f"h-{self._tick}",
            )

        def snapshot(self) -> EnvSnapshot:
            raise NotImplementedError

        def restore(self, snap: EnvSnapshot) -> None:
            raise NotImplementedError

        def no_model_baseline(self, seed: int) -> EpisodeOutcome:
            return EpisodeOutcome(score=2.0, steps=2)

    class PlainOrbitalEnv(OrbitalProbeEnv):
        # Deliberately omit initial_facts hook to test generic scalar fallback.
        initial_facts = None  # type: ignore[assignment]

    seen_facts: List[Dict[str, Any]] = []

    def inspect_policy(obs: Mapping[str, Any], mem: Optional[EpisodeMemory]) -> str:
        assert mem is not None
        seen_facts.append(dict(mem.facts))
        return "stabilize"

    res_plain = run_episode(PlainOrbitalEnv(), inspect_policy, seed=4, max_steps=5, use_memory=True)
    assert res_plain.done is True
    assert res_plain.steps == 2
    assert res_plain.status == "pass"
    # Step 0 seeded from reset obs with arbitrary scalar keys (excluding lists/dicts/None).
    assert seen_facts[0] == {
        "sector": "orbit-4",
        "reactor_temp": 290.5,
        "shields_up": True,
        "beacon_code": "XZ-900",
    }
    # Step 1 keeps remembered transient beacon_code while updating scalar facts.
    assert seen_facts[1]["beacon_code"] == "XZ-900"
    assert seen_facts[1]["sector"] == "orbit-step-1"
    assert seen_facts[1]["reactor_temp"] == 285.5
    assert "sensors" not in seen_facts[1] and "raw_frame" not in seen_facts[1]
    assert not ({"node", "fuel", "cargo", "job_accepted", "pickup", "dropoff", "auth_code"} & set(seen_facts[1]))

    # Optional initial_facts(obs) hook takes precedence on reset.
    hook_facts: List[Dict[str, Any]] = []

    def inspect_hook_policy(obs: Mapping[str, Any], mem: Optional[EpisodeMemory]) -> str:
        assert mem is not None
        hook_facts.append(dict(mem.facts))
        return "coast"

    res_hook = run_episode(OrbitalProbeEnv(use_hook=True), inspect_hook_policy, seed=9, max_steps=5, use_memory=True)
    assert res_hook.done is True
    assert hook_facts[0] == {"custom_seed_tag": "hook:orbit-9", "beacon_code": "XZ-900"}
    assert hook_facts[1]["custom_seed_tag"] == "hook:orbit-9"
    assert hook_facts[1]["beacon_code"] == "XZ-900"
    assert hook_facts[1]["sector"] == "orbit-step-1"
