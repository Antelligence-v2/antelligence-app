import subprocess

import pytest

from antelligence.experiments import v4_pilot as p
from antelligence.kernel.decision import REPORT
from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import NOOP, Intent
from tests.engine.fake_pilot_world import FakePilotWorld

WORLDS = {"fake_world": FakePilotWorld("fake_world")}


def spec(arm, seed=100, cond="v1", world="fake_world", **kw):
    return p.CellSpec(world, arm, seed, cond, **kw)


def test_seed_sets_are_disjoint_and_arms_match_goal_table():
    assert p.DEV_SEEDS == tuple(range(100, 110)) and p.EVAL_SEEDS == (1, 2, 3, 4, 5)
    assert not set(p.DEV_SEEDS) & set(p.EVAL_SEEDS)
    assert list(p.ARMS) == ["S", "S-prime", "DS-all", "Q-all-qwen3.5-0.8b", "Q-all-qwen3.5-4b", "Q-all-qwen3.5-9b",
                            "Q-all-qwen3.5-27b", "Q-all-qwen3.8-27b", "F-Laya", "F-Jev", "F-Jev-noQueen", "F-Jev-noEsc"]
    a = p.ARMS
    assert a["S-prime"].variants_only and not a["S"].variants_only
    assert (a["F-Jev"].queen, a["F-Jev"].escalation) == (True, True)
    assert (a["F-Jev-noQueen"].queen, a["F-Jev-noQueen"].all_actions) == (False, True)
    assert (a["F-Jev-noEsc"].queen, a["F-Jev-noEsc"].escalation) == (True, False)
    assert a["DS-all"].model == "deepseek/deepseek-v4.1-flash" and a["F-Laya"].backend == "laya"
    assert a["F-Jev"].model == "jev-1.13.0"


def test_eval_plan_honours_the_exceptions():
    plan = p.make_plan()
    count = lambda w, arm: sum(c.world == w and c.arm == arm for c in plan)  # noqa: E731
    assert count("foraging_sb", "S") == 15 and count("graph_coloring", "S") == 15
    assert count("foraging_sb", "S-prime") == 10 and not any(c.arm == "S-prime" and c.condition == "base" for c in plan)
    assert count("foraging_sb", "DS-all") == 9 and count("graph_coloring", "DS-all") == 15
    ds = [c for c in plan if c.arm == "DS-all" and c.world == "foraging_sb"]
    assert sorted({c.seed for c in ds}) == [1, 2, 3]
    assert len(plan) == 344 and len({c.key for c in plan}) == 344
    assert {c.seed for c in plan} == set(p.EVAL_SEEDS)
    assert [c.arm for c in plan[:5]] == ["S"] * 5  # scripts first, so G references exist
    with pytest.raises(ValueError):
        p.make_plan(arms=["nope"])


def run(cell_spec, refs=None, kit=None, **kw):
    kit = kit or p.DryKit()
    return p.run_cell(cell_spec, WORLDS["fake_world"], kit.build_policies, ledger_tags=kit.tags,
                      ledger_rows=kit.rows_for, refs=refs, **kw)


def test_script_cells_have_no_calls_and_scores_match_the_world():
    assert run(spec("S", cond="base"))["score"] == 1.0
    s_v1, sp_v1 = run(spec("S")), run(spec("S-prime"))
    assert (s_v1["score"], sp_v1["score"]) == (0.0, 1.0)
    assert s_v1["calls"] == 0 and s_v1["latencies_s"] == [] and s_v1["g"] is None and s_v1["ticks"] == 6
    assert s_v1["trace_hash"] and s_v1["config_hash"] and s_v1["split"] == "dev"


def test_model_cell_metrics_and_g():
    cell = run(spec("DS-all"), refs={"S": 0.0, "S-prime": 1.0})
    assert cell["calls"] == 18 == len(cell["latencies_s"]) and cell["input_tokens"] > 0 and cell["cost_usd"] > 0
    assert cell["cost_by_provider"].keys() == {"nous"} and cell["hardware"] == "nous-inference-api"
    assert cell["g"] == pytest.approx(cell["score"])  # S=0, S'=1
    assert cell["compliance"] == 1.0 and cell["answers"] == 18
    assert cell["wall_s"] >= 0 and cell["decision_s"]["n"] == 18
    # base runs and unknown references never produce a G
    assert run(spec("DS-all", cond="base"), refs={"S": 0.0, "S-prime": 1.0})["g"] is None
    assert run(spec("DS-all"), refs={"S": 0.5, "S-prime": 0.5})["g"] is None
    assert run(spec("DS-all"))["g"] is None


def test_framework_cell_reports_and_escalations_are_counted():
    cells = [run(spec("F-Jev", seed=sd)) for sd in range(100, 110)]
    cell = next(c for c in cells if c["reports"])  # the dry policy reports ~10% of the time
    assert cell["model_decisions"] == 18 and 0 <= cell["escalation_rate"] <= 1
    assert cell["escalations"] == round(cell["escalation_rate"] * 18)
    assert cell["reports_judged"] == cell["reports"]
    # the dry policy reports when the best action is allowed: never a true report
    assert cell["report_precision"] == 0.0 and cell["reports_true"] == 0
    assert run(spec("F-Jev", seed=cell["seed"]))["trace_hash"] == cell["trace_hash"]  # deterministic


class QueenWorld(p._WorldProxy):
    """Stand-in for HiveWorld: adds the queen agent."""

    def agents(self):
        return self.inner.agents() + ["queen"]

    def observe(self, agent_id, tick):
        if agent_id == "queen":
            from antelligence.kernel.field import SenseQuery
            from antelligence.kernel.types import Observation
            return Observation({"tick": tick}, SenseQuery(topic="board", kinds=frozenset({"report"})))
        return self.inner.observe(agent_id, tick)

    def apply(self, agent_id, intent, tick):
        from antelligence.kernel.types import Outcome
        return Outcome(True) if agent_id == "queen" else self.inner.apply(agent_id, intent, tick)


class Queen:
    def decide(self, view):
        draft = SignalDraft("queen", topic="board", payload={"group": "g", "goal": "go up", "allowed": ["up"]}, ttl=50)
        return Intent(NOOP, emit=(draft,)) if view.tick == 1 else Intent(NOOP)

    def describe(self):
        return {"policy": "queen"}


class Worker:
    CHOICE = {"w0": "up", "w1": "down", "w2": REPORT}

    def decide(self, view):
        return Intent(self.CHOICE[view.agent_id])

    def describe(self):
        return {"policy": "worker"}


def test_tap_tracks_queen_allowed_set_compliance_and_report_truth():
    kit = p.DryKit()
    build = lambda s, pw, w: p.PolicySet({"queen": Queen()}, Worker(), QueenWorld)  # noqa: E731
    cell = p.run_cell(spec("F-Jev"), WORLDS["fake_world"], build, ledger_tags=kit.tags)
    # queen signal at tick 1 is visible from tick 2: w1 breaks the allowed set on ticks 2..6
    assert cell["decisions"] == 18 and cell["compliance"] == pytest.approx(13 / 18)
    # w2 reports every tick; v1's best action is "down", outside {"up"}, so true from tick 2; tick 1 had all allowed
    assert cell["reports"] == 6 and cell["reports_true"] == 5 and cell["report_precision"] == pytest.approx(5 / 6)
    assert cell["queen_signals"] == 1


def test_tap_prefers_policy_reported_allowed_set_and_ignores_failed_policies():
    world = WORLDS["fake_world"]
    base = world.make_world(1, "v1")
    tap = p.MetricsTap(base, world, base)
    tap.observe("w0", 1)
    tap.apply("w0", Intent("down", meta={"allowed": ["up"], "escalated": ["q"]}), 1)
    tap.observe("w1", 1)
    tap.apply("w1", Intent(NOOP, meta={"reason": "backend_error:X"}), 1)  # failed policy: not an answer
    tap.observe("w2", 1)
    tap.apply("w2", Intent(NOOP, meta={"allowed": ["up"], "answer": "report"}), 1)  # DecisionWorker's REPORT acts NOOP
    s = tap.summary()
    assert (s["answers"], s["noops"], s["compliance"], s["escalation_rate"]) == (2, 1, 0.5, 1.0)
    assert s["reports"] == 1  # the report is seen through meta["answer"], not the NOOP action


def test_tap_report_truth_uses_every_good_action():
    class TwoGood(FakePilotWorld):
        def oracle_actions(self, world, agent_id, tick):
            return ("down", "up")

    world = TwoGood("two")
    base = world.make_world(1, "v1")
    tap = p.MetricsTap(base, world, base)
    for agent, allowed in (("w0", ["up"]), ("w1", ["left"])):
        tap.observe(agent, 1)
        tap.apply(agent, Intent(NOOP, meta={"allowed": allowed, "answer": REPORT}), 1)
    assert [r["report_true"] for r in tap.records] == [False, True]  # an allowed good action makes a report false


def test_cells_are_append_only_and_never_rerun(tmp_path):
    kit = p.DryKit()
    path = tmp_path / "cells.jsonl"
    plan = p.make_plan(["fake_world"], ["S", "S-prime", "DS-all"], seeds=[100, 101])
    go = lambda: p.asyncio.run(p.run_plan(plan, WORLDS, kit.build_policies, ledger_tags=kit.tags, cells_path=path,  # noqa: E731
                                          ledger_rows=kit.rows_for, concurrency=3, bundle_dir=tmp_path / "b"))
    first = go()
    assert len(first) == len(plan) == 2 * 3 + 2 * 2 + 2 * 3
    text = path.read_text()
    assert go() == [] and path.read_text() == text
    cells = p.load_cells(path)
    ds = [c for c in cells if c["arm"] == "DS-all" and c["condition"] != "base"]
    assert all(c["g"] is not None for c in ds)  # S and S' were run first
    assert (tmp_path / "b" / "fake_world-DS-all-s100-v1.bundle.json").exists()
    assert (tmp_path / "b" / "fake_world-DS-all-s100-v1.frames.json.gz").exists()
    assert (tmp_path / "b" / "events" / "fake_world-DS-all-s100-v1.jsonl").exists()


def test_crash_becomes_an_error_cell_and_budget_stop_propagates(tmp_path):
    kit = p.DryKit()

    def broken(s, pw, w):
        raise RuntimeError("boom")

    path = tmp_path / "c.jsonl"
    new = p.asyncio.run(p.run_plan([spec("DS-all")], WORLDS, broken, ledger_tags=kit.tags, cells_path=path))
    assert new[0]["error"].startswith("RuntimeError") and new[0]["score"] is None
    assert p.asyncio.run(p.run_plan([spec("DS-all")], WORLDS, broken, ledger_tags=kit.tags, cells_path=path)) == []

    def stop(s):
        raise p.BudgetExceeded("hard stop")

    with pytest.raises(p.BudgetExceeded):
        p.asyncio.run(p.run_plan([spec("DS-all", seed=5)], WORLDS, kit.build_policies, ledger_tags=kit.tags,
                                 cells_path=tmp_path / "d.jsonl", before_cell=stop))
    assert not (tmp_path / "d.jsonl").exists()


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


def test_prereg_gate(tmp_path):
    git(tmp_path, "init", "-q")
    files = ("PREREG.md",)
    with pytest.raises(SystemExit, match="not committed"):
        p.check_committed(tmp_path, files)
    (tmp_path / "PREREG.md").write_text("v1")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "prereg")
    p.check_committed(tmp_path, files)
    (tmp_path / "PREREG.md").write_text("v2")
    with pytest.raises(SystemExit, match="uncommitted changes"):
        p.check_committed(tmp_path, files)
    assert p.uses_eval_seeds([100, 3]) and not p.uses_eval_seeds(p.DEV_SEEDS)


def test_validity_check():
    ok = p.validity_check(FakePilotWorld(), seeds=[100, 101])
    assert all(v["valid"] for v in ok["variants"].values())
    assert ok["variants"]["v1"]["S_variant"] == 0.0 and ok["variants"]["v1"]["S_prime_variant"] == 1.0
    bad = p.validity_check(FakePilotWorld(harmless=("v2",)), seeds=[100])
    assert bad["variants"]["v1"]["valid"] and not bad["variants"]["v2"]["valid"]
    with pytest.raises(ValueError):
        p.validity_check(FakePilotWorld(), seeds=[1])


def test_check_failures_are_counted_as_board_reports_apart_from_report_answers():
    class Checker(Worker):
        def decide(self, view):
            meta = {"failed_checks": ["food_still_there"]} if view.agent_id == "w0" else {}
            return Intent("up", meta=meta)

    build = lambda s, pw, w: p.PolicySet(default_policy=Checker())  # noqa: E731
    cell = p.run_cell(spec("DS-all"), WORLDS["fake_world"], build, ledger_tags=p.DryKit().tags)
    assert cell["reports"] == 0 and cell["check_reports"] == 6  # one failing worker over 6 ticks


def test_cell_records_the_policy_sets_queen_cadence_and_decision_s_follows_the_ledger():
    kit = p.DryKit()
    build = lambda s, pw, w: p.PolicySet({"queen": Queen()}, Worker(), QueenWorld, queen_every=7)  # noqa: E731
    cell = p.run_cell(spec("F-Jev"), WORLDS["fake_world"], build, ledger_tags=kit.tags, ledger_rows=kit.rows_for)
    assert cell["queen_every"] == 7 and cell["decision_s"]["n"] == cell["calls"] == 0  # no ledger rows, no samples
