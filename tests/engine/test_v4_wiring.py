"""v4_wiring: every arm assembled per the B4 recipe over fakes, ledger tags, reconciliation, secrets, pod checks."""

import asyncio
import json

import pytest

from antelligence.experiments import v4_pilot as p
from antelligence.experiments import v4_wiring as w
from antelligence.kernel.hive import HiveWorld
from antelligence.kernel.policies.decision_worker import DecisionWorker
from antelligence.kernel.policies.llm_queen import LLMQueen
from antelligence.kernel.policies.state_policy import StateChatPolicy
from antelligence.providers import Cached, EscalatingBackend, LedgerWriter, LedgeredChat
from antelligence.providers.decision_backends import CachedDecision, LedgeredDecision
from antelligence.worlds.foraging_sb import FORAGING_SB
from antelligence.worlds.graph_coloring import GRAPH_COLORING

WORLDS = {"foraging_sb": FORAGING_SB, "graph_coloring": GRAPH_COLORING}
NOUS_SECRET, JEV_SECRET, POD_SECRET = "NOUS-SECRET-aa11", "JEV-SECRET-bb22", "POD-SECRET-cc33"


def wiring(tmp_path, **kw):
    return w.Wiring(w.fake_leaves(), LedgerWriter(tmp_path / "ledger.jsonl"), tmp_path / "cache", **kw)


def build(tmp_path, arm, world="graph_coloring", seed=100, condition="v1", queen_every=None, **kw):
    pw = WORLDS[world]
    spec = p.CellSpec(world, arm, seed, condition, queen_every)
    inner = pw.make_world(seed, condition)
    return spec, pw, inner, w.build_policies(spec, pw, inner, factories=wiring(tmp_path, **kw))


# --- arm assembly -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("world", sorted(WORLDS))
@pytest.mark.parametrize("arm", sorted(p.ARMS))
def test_every_arm_assembles_on_both_worlds(tmp_path, arm, world):
    spec, pw, inner, built = build(tmp_path, arm, world)
    a = p.ARMS[arm]
    if a.decider in ("script", "script_adapted"):
        assert built.default_policy is not None and not built.policies and built.wrap_world is None
    elif a.decider == "every_agent":
        policy = built.default_policy
        assert isinstance(policy, StateChatPolicy) and policy.max_tokens == 64 and not built.policies
        assert built.wrap_world is None
        assert isinstance(policy.provider, Cached) and isinstance(policy.provider.inner, LedgeredChat)
        ledgered = policy.provider.inner
        assert ledgered.role == "every_agent"
        if a.backend == "nous":
            assert policy.model == p.NOUS_MODEL and ledgered.backend == "nous"
        else:
            assert policy.model == a.model and ledgered.backend == "vllm" and ledgered.price == (0.0, 0.0)
    else:
        workers = [i for i in built.policies if i != "queen"]
        assert sorted(workers) == sorted(inner.agents())
        assert all(isinstance(built.policies[i], DecisionWorker) for i in workers)
        assert ("queen" in built.policies) == a.queen
        hive = built.wrap_world(inner)
        assert isinstance(hive, HiveWorld) and hive.queen == a.queen
        assert ("queen" in hive.agents()) == a.queen
        worker = built.policies[workers[0]]
        assert worker.use_queen == a.queen and worker.model == a.model
        backend = worker.backend
        assert isinstance(backend, EscalatingBackend) and (backend.escalation is not None) == a.escalation
        assert isinstance(backend.primary, CachedDecision) and isinstance(backend.primary.inner, LedgeredDecision)
        assert backend.primary.inner.role == "worker"
        assert backend.primary.inner.backend == a.backend
        if a.escalation:
            assert backend.escalation.inner.role == "escalation" and backend.escalation.inner.backend == "slm"
            assert backend.escalation.describe()["model"] == w.SLM_MODEL


def test_queen_recipe_and_group_assignment(tmp_path):
    spec, pw, inner, built = build(tmp_path, "F-Jev", "foraging_sb")
    queen = built.policies["queen"]
    assert isinstance(queen, LLMQueen) and queen.max_tokens == 300 and queen.model == p.NOUS_MODEL
    assert isinstance(queen.provider, Cached) and queen.provider.inner.role == "queen"
    assert queen.provider.inner.backend == "nous"
    groups = pw.groups(inner)
    assert queen.groups == {g: tuple(m) for g, m in groups.items()} and set(queen.actions) == set(pw.actions)
    for g, members in groups.items():
        assert all(built.policies[a].group == g for a in members)


def test_queen_cadence_per_world_and_override(tmp_path):
    assert w.QUEEN_EVERY == {"foraging_sb": 10, "graph_coloring": 1}
    for world, every in (("foraging_sb", 10), ("graph_coloring", 1)):
        _, _, _, built = build(tmp_path, "F-Laya", world)
        queen, worker = built.policies["queen"], next(v for k, v in built.policies.items() if k != "queen")
        assert queen.every == every and worker.report_ttl >= queen.every
    _, _, _, built = build(tmp_path, "F-Jev", "foraging_sb", queen_every=20)  # budget cut: queen every 20 ticks
    assert built.policies["queen"].every == 20 and built.policies["0"].report_ttl >= 20


def test_no_queen_arm_has_no_board_traffic_reader(tmp_path):
    _, _, inner, built = build(tmp_path, "F-Jev-noQueen", "foraging_sb")
    hive = built.wrap_world(inner)
    assert "queen" not in built.policies and not hive.queen and hive.agents() == inner.agents()
    assert all(not v.use_queen for v in built.policies.values())


def test_pod_model_must_match_the_arm(tmp_path):
    state = {"served": "Qwen/Qwen3.5-9B", "hf": "Qwen/Qwen3.5-9B", "base_url": "https://pod-8000.example/v1",
             "api_secret": POD_SECRET}
    ledger = LedgerWriter(tmp_path / "l.jsonl")
    leaves = w.live_leaves(nous_key=NOUS_SECRET, env_value=lambda n: JEV_SECRET, ledger=ledger, pod_state=state,
                           pod_state_path=tmp_path / "none.json", laya_url=w.LAYA_URL)
    spec = p.CellSpec("graph_coloring", "Q-all-qwen3.5-27b", 100, "base")
    with pytest.raises(w.WiringError, match="one model per pod") as err:
        w.build_policies(spec, GRAPH_COLORING, GRAPH_COLORING.make_world(100, "base"),
                         factories=w.Wiring(leaves, ledger, tmp_path / "c"))
    assert isinstance(err.value, p.SetupError) and POD_SECRET not in str(err.value)
    # the right model is accepted, and an FP8 build serves the arm's model under its -FP8 name
    provider, served = leaves.pod("Qwen/Qwen3.5-9B")
    assert served == "Qwen/Qwen3.5-9B" and provider.allowed_models == frozenset({served})
    assert provider.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    fp8 = dict(state, served="Qwen/Qwen3.5-27B-FP8", hf="Qwen/Qwen3.5-27B-FP8")
    assert w._pod_matches(fp8, "Qwen/Qwen3.5-27B")[1] == "Qwen/Qwen3.5-27B-FP8"
    with pytest.raises(w.WiringError, match="no pod is up"):
        w._pod_matches(None, "Qwen/Qwen3.5-9B")


def test_nous_provider_is_pinned_and_non_thinking(tmp_path):
    ledger = LedgerWriter(tmp_path / "l.jsonl")
    leaves = w.live_leaves(nous_key=lambda: NOUS_SECRET, env_value=lambda n: JEV_SECRET, ledger=ledger,
                           pod_state=None, pod_state_path=tmp_path / "none.json", laya_url=w.LAYA_URL)
    provider = leaves.nous()
    assert provider.base_url == "https://inference-api.nousresearch.com/v1"
    assert provider.allowed_models == frozenset({"deepseek/deepseek-v4.1-flash"})
    assert provider.extra_body == {"reasoning": {"enabled": False}}
    assert leaves.jev().describe()["model"] == "jev-1.13.0" and leaves.laya().describe()["base_url"] == w.LAYA_URL


# --- secrets ------------------------------------------------------------------------------------------------


def test_keys_are_read_lazily_and_never_appear_in_describe_or_errors(tmp_path):
    reads = []
    state = {"served": "Qwen/Qwen3.5-9B", "hf": "Qwen/Qwen3.5-9B", "base_url": "https://pod-8000.example/v1",
             "api_secret": POD_SECRET}
    hooks = w.make_hooks(nous_key=lambda: reads.append("nous") or NOUS_SECRET,
                         env_value=lambda n: reads.append(n) or JEV_SECRET, ledger=tmp_path / "ledger.jsonl",
                         cache_dir=tmp_path / "cache", pod_state=state)
    assert reads == []  # making the hooks reads nothing
    pw, texts = FORAGING_SB, []
    for arm in p.ARMS:
        if p.ARMS[arm].model.startswith("Qwen/") and p.ARMS[arm].model != "Qwen/Qwen3.5-9B":
            continue  # the pod holds the 9B model only
        spec = p.CellSpec("foraging_sb", arm, 100, "v1")
        inner = pw.make_world(100, "v1")
        built = hooks.build_policies(spec, pw, inner)
        everyone = [*built.policies.values(), *([built.default_policy] if built.default_policy else [])]
        texts += [json.dumps(x.describe(), default=str) for x in everyone]
        if built.wrap_world:
            texts.append(json.dumps(built.wrap_world(inner).describe(), default=str))
    assert {"nous", "TYPESAFE_API_KEY"} <= set(reads) and len(texts) > 20
    blob = "\n".join(texts)
    assert not any(secret in blob for secret in (NOUS_SECRET, JEV_SECRET, POD_SECRET))


def test_secrets_are_scrubbed_from_ledger_error_rows(tmp_path):
    ledger = LedgerWriter(tmp_path / "l.jsonl")
    leaves = w.live_leaves(nous_key=NOUS_SECRET, env_value=lambda n: JEV_SECRET, ledger=ledger, pod_state=None,
                           pod_state_path=tmp_path / "none.json", laya_url=w.LAYA_URL)
    leaves.nous()
    leaves.jev()  # reading a key registers it for redaction
    ledger.write(role="queen", backend="nous", model="m", served_model=None, request_hash="h",
                 error=f"HTTP 401 {NOUS_SECRET} and {JEV_SECRET}")
    text = (tmp_path / "l.jsonl").read_text()
    assert NOUS_SECRET not in text and JEV_SECRET not in text and "***" in text


# --- running cells: tags, roles, reconciliation, replay ----------------------------------------------------


def run(hooks, world, arm, seed=100, condition="v1", **kw):
    spec = p.CellSpec(world, arm, seed, condition)
    return p.run_cell(spec, WORLDS[world], hooks.build_policies, ledger_tags=hooks.ledger_tags,
                      ledger_rows=hooks.ledger_rows, reconcile=hooks.reconcile, **kw)


def dry(tmp_path, **kw):
    return w.make_dry_hooks(ledger=tmp_path / "ledger.jsonl", cache_dir=tmp_path / "cache", **kw)


@pytest.mark.parametrize("arm", ["DS-all", "Q-all-qwen3.5-9b", "F-Laya", "F-Jev", "F-Jev-noQueen", "F-Jev-noEsc"])
def test_ledger_tags_reach_every_row_and_calls_reconcile(tmp_path, arm):
    hooks = dry(tmp_path)
    cell = run(hooks, "graph_coloring", arm, seed=101, condition="v2")
    rows = LedgerWriter(tmp_path / "ledger.jsonl").rows()
    assert rows and cell["calls_reconciled"] is True and cell["calls_gap"] == 0
    assert cell["calls_physical"] == cell["calls_ledger_rows"] == cell["calls"] == len(rows)
    for r in rows:
        assert (r["run"], r["arm"], r["world"], r["seed"], r["condition"]) == (
            cell["run_tag"], arm, "graph_coloring", 101, "v2")
        assert r["run"].startswith(f"graph_coloring|{arm}|101|v2#")
    roles = {r["role"] for r in rows}
    full = {"worker", "queen", "escalation"}
    expected = {"DS-all": {"every_agent"}, "Q-all-qwen3.5-9b": {"every_agent"}, "F-Laya": full, "F-Jev": full,
                "F-Jev-noQueen": {"worker", "escalation"}, "F-Jev-noEsc": {"worker", "queen"}}[arm]
    assert roles == expected
    assert cell["compliance"] == 1.0 and cell["trace_hash"] and cell["config_hash"]


def test_backends_and_costs_in_rows(tmp_path):
    hooks = dry(tmp_path)
    run(hooks, "graph_coloring", "F-Jev")
    run(hooks, "graph_coloring", "DS-all", condition="base")
    rows = LedgerWriter(tmp_path / "ledger.jsonl").rows()
    by = {(r["arm"], r["role"]): r for r in rows}
    assert by[("F-Jev", "worker")]["backend"] == "jev" and by[("F-Jev", "worker")]["model"] == "jev-1.13.0"
    assert by[("F-Jev", "escalation")]["backend"] == "slm" and by[("F-Jev", "escalation")]["model"] == w.SLM_MODEL
    assert by[("F-Jev", "queen")]["backend"] == "nous" and by[("F-Jev", "queen")]["cost_usd"] > 0
    assert by[("DS-all", "every_agent")]["backend"] == "nous" and by[("DS-all", "every_agent")]["cost_usd"] > 0


def test_escalation_fires_sometimes_and_reports_are_posted(tmp_path):
    cell = run(dry(tmp_path), "graph_coloring", "F-Jev")
    assert 0 < cell["escalation_rate"] < 1 and cell["queen_signals"] > 0 and cell["reports"] > 0
    assert run(dry(tmp_path / "b"), "graph_coloring", "F-Jev-noEsc")["escalation_rate"] == 0


def test_cache_hits_write_no_row_and_offline_replay_is_identical(tmp_path):
    first = run(dry(tmp_path), "graph_coloring", "F-Laya", condition="v2")
    replay_hooks = w.make_dry_hooks(ledger=tmp_path / "replay-ledger.jsonl", cache_dir=tmp_path / "cache", offline=True)
    again = run(replay_hooks, "graph_coloring", "F-Laya", condition="v2")
    assert again["trace_hash"] == first["trace_hash"] and again["config_hash"] == first["config_hash"]
    assert again["score"] == first["score"] and again["g"] is None
    assert again["calls_physical"] == again["calls_ledger_rows"] == 0 and first["calls"] > 0
    assert LedgerWriter(tmp_path / "replay-ledger.jsonl").rows() == []
    # every reply of the replay came from the cache: no physical call, so no seconds-per-decision sample
    assert again["decision_s"]["n"] == 0 and again["cache_hits"] > 0 and first["decision_s"]["n"] == first["calls"]


def test_cache_hits_are_counted_apart_from_physical_calls_and_stay_out_of_decision_s(tmp_path):
    cell = run(dry(tmp_path), "foraging_sb", "F-Jev-noEsc", seed=100, condition="base")
    assert cell["cache_hits"] > 0  # identical requests repeat within a run (a jam shows the same state again)
    assert cell["decision_s"]["n"] == cell["calls"] == len(cell["latencies_s"]) < cell["decisions"]
    assert cell["queen_every"] == 10  # the effective cadence, not the None override
    assert run(dry(tmp_path / "c"), "graph_coloring", "F-Jev")["queen_every"] == 1
    assert run(dry(tmp_path / "d"), "graph_coloring", "F-Jev-noQueen")["queen_every"] is None
    assert run(dry(tmp_path / "e"), "graph_coloring", "DS-all")["queen_every"] is None


def test_caches_are_scoped_to_the_run(tmp_path):
    hooks = dry(tmp_path)
    a, b = run(hooks, "graph_coloring", "F-Jev", condition="v1"), run(hooks, "graph_coloring", "F-Jev-noEsc",
                                                                       condition="v1")
    assert a["calls"] > 0 and b["calls"] > 0  # an arm never rides on another arm's cached replies
    names = {f.parent.name for f in (tmp_path / "cache").rglob("*") if f.is_file()}
    assert {"graph_coloring-F-Jev-s100-v1", "graph_coloring-F-Jev-noEsc-s100-v1"} <= names


def test_reconcile_reports_a_gap(tmp_path):
    wr = wiring(tmp_path)
    wr._counter("r")[0] = 5
    assert wr.reconcile("r", [{}] * 5) == {"calls_physical": 5, "calls_ledger_rows": 5, "calls_gap": 0,
                                          "calls_reconciled": True, "cache_hits": 0}
    gap = wr.reconcile("r", [{}] * 4)
    assert gap["calls_reconciled"] is False and gap["calls_gap"] == 1
    assert wr.reconcile("never-ran", [])["calls_reconciled"] is True


def test_foraging_cell_through_the_hive(tmp_path):
    cell = run(dry(tmp_path), "foraging_sb", "F-Jev", seed=100, condition="base")
    assert cell["calls_reconciled"] and cell["queen_signals"] == 20  # 10 queen turns x 2 groups
    assert cell["ticks"] == 100 and "error" not in cell


def test_setup_error_stops_the_run_and_records_no_cell(tmp_path):
    state = {"served": "Qwen/Qwen3.5-9B", "hf": "Qwen/Qwen3.5-9B", "base_url": "https://pod-8000.example/v1",
             "api_secret": POD_SECRET}
    hooks = w.make_hooks(nous_key="x", env_value=lambda n: "y", ledger=tmp_path / "l.jsonl", cache_dir=tmp_path / "c",
                         pod_state=state)
    plan = [p.CellSpec("graph_coloring", "Q-all-qwen3.5-27b", 100, "base")]
    cells = tmp_path / "cells.jsonl"
    with pytest.raises(w.WiringError):
        asyncio.run(p.run_plan(plan, WORLDS, hooks.build_policies, ledger_tags=hooks.ledger_tags, cells_path=cells))
    assert not cells.exists() or cells.read_text() == ""  # not an error cell: it can be rerun once the pod is right


def test_calibration_backends(tmp_path):
    hooks = dry(tmp_path)
    for name in ("jev", "laya", "qwen3.5-9b", "deepseek"):
        assert hooks.make_backend(name).describe()["model"]
    with pytest.raises(ValueError):
        hooks.make_backend("nope")


@pytest.mark.parametrize("world", sorted(WORLDS))
def test_every_model_arm_is_told_the_worlds_task(tmp_path, world):
    task = WORLDS[world].instructions
    _, _, _, ds = build(tmp_path, "DS-all", world)
    assert ds.default_policy.instructions == task and ds.default_policy.system.startswith(task)
    _, _, _, fw = build(tmp_path, "F-Jev", world)
    assert fw.policies["queen"].instructions == task and task in fw.policies["queen"].system
    workers = [v for k, v in fw.policies.items() if k != "queen"]
    assert workers and all(isinstance(v, DecisionWorker) and v.instructions == task for v in workers)
