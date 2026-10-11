import json
from datetime import datetime, timezone

import pytest

from antelligence.experiments import v4_budget as b
from antelligence.experiments.v4_pilot import make_plan

T0 = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


def write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_ledger_spend_by_provider():
    rows = [{"backend": "nous", "model": "deepseek/deepseek-v4.1-flash", "cost_usd": 0.25},
            {"backend": "jev", "model": "jev-1.13.0", "cost_usd": 0.5},
            {"backend": "vllm", "model": "Qwen/Qwen3.5-9B", "cost_usd": 0.0},
            {"backend": "nous", "model": "x", "cost_usd": 0.5}]
    assert b.ledger_spend(rows) == {"nous": 0.75, "jev": 0.5}


def test_pod_spend_charges_running_pods_to_now():
    recs = [{"event": "start", "pod_id": "a", "utc": "2026-10-12T08:00:00+00:00", "rate_per_hr": 0.8},
            {"event": "stop", "pod_id": "a", "utc": "2026-10-12T09:30:00+00:00", "rate_per_hr": 0.8},
            {"event": "start", "pod_id": "b", "utc": "2026-10-12T09:00:00+00:00", "rate_per_hr": 1.0}]
    assert b.pod_spend(recs, now=T0) == pytest.approx(1.5 * 0.8 + 1.0 * 1.0)


def test_check_or_raise_stops_at_the_limit(tmp_path):
    ledger, pods = tmp_path / "l.jsonl", tmp_path / "p.jsonl"
    write(ledger, [{"backend": "nous", "cost_usd": 4.49}])
    assert b.check_or_raise("nous", ledger=ledger, pods=pods) == pytest.approx(4.49)
    with pytest.raises(b.BudgetExceeded):
        b.check_or_raise("nous", ledger=ledger, pods=pods, pending_usd=0.02)
    write(ledger, [{"backend": "jev", "cost_usd": 1.5}])
    with pytest.raises(b.BudgetExceeded):
        b.check_or_raise("jev", ledger=ledger, pods=pods)
    write(pods, [{"event": "start", "pod_id": "a", "utc": "2026-10-12T05:00:00+00:00", "rate_per_hr": 1.0}])
    with pytest.raises(b.BudgetExceeded):
        b.check_or_raise("runpod", ledger=ledger, pods=pods, now=T0)  # 5 h * $1 = $5 > $2.75
    assert b.check_or_raise("nous", ledger=tmp_path / "none", pods=None) == 0.0  # missing files are empty


def costs(ds_foraging=0.0, queen=0.0, q_all=0.0):
    out = {}
    for w in ("foraging_sb", "graph_coloring"):
        out[b.cost_key(w, "DS-all")] = {"nous": ds_foraging if w == "foraging_sb" else 0.01}
        for arm in ("F-Laya", "F-Jev", "F-Jev-noEsc"):
            out[b.cost_key(w, arm)] = {"nous": queen, "queen_nous": queen}
        for arm in b.RUNPOD_CUT_ORDER + ("Q-all-qwen3.5-0.8b", "Q-all-qwen3.5-9b", "Q-all-qwen3.8-27b"):
            out[b.cost_key(w, arm)] = {"runpod": q_all}
    return out


def test_nous_cut_order_foraging_seeds_then_queen_cadence():
    plan = make_plan()
    c = costs(ds_foraging=0.5, queen=0.028)
    res = b.project(plan, c)
    assert res["projected_initial"]["nous"] == pytest.approx(9 * 0.5 + 15 * 0.01 + 90 * 0.028)
    assert [d["cut"] for d in res["decisions"]] == ["DS-all foraging to 2 seeds per condition",
                                                    "queen speaks every 20 ticks"]
    ds = [x for x in res["plan"] if x.arm == "DS-all" and x.world == "foraging_sb"]
    assert sorted({x.seed for x in ds}) == [1, 2] and len(ds) == 6
    assert {x.queen_every for x in res["plan"] if x.arm in b.QUEEN_ARMS} == {20}
    assert {x.queen_every for x in res["plan"] if x.arm == "F-Jev-noQueen"} == {None}
    assert res["projected_final"]["nous"] == pytest.approx(6 * 0.5 + 0.15 + 90 * 0.014)
    assert res["over_after_cuts"] == []


def test_no_cut_when_under_budget():
    res = b.project(make_plan(), costs(ds_foraging=0.1, queen=0.01))
    assert res["decisions"] == [] and len(res["plan"]) == len(make_plan())


def test_runpod_drops_27b_first_then_4b():
    one = b.project(make_plan(), costs(q_all=0.02))  # 5 arms * 30 cells * 0.02 = 3.0 > 2.75
    assert [d["cut"] for d in one["decisions"]] == ["drop Q-all-qwen3.5-27b"]
    assert not any(c.arm == "Q-all-qwen3.5-27b" for c in one["plan"])
    two = b.project(make_plan(), costs(q_all=0.03))
    assert [d["cut"] for d in two["decisions"]] == ["drop Q-all-qwen3.5-27b", "drop Q-all-qwen3.5-4b"]
    assert any(c.arm == "Q-all-qwen3.5-9b" for c in two["plan"])
    three = b.project(make_plan(), costs(q_all=0.2))
    assert three["over_after_cuts"] == ["runpod"]  # cuts exhausted, still over: reported, not hidden


def test_costs_from_cells_means_and_pod_share():
    cells = [{"world": "w", "arm": "F-Jev", "cost_by_provider": {"nous": 0.2, "jev": 0.1}, "queen_cost_usd": 0.1,
              "wall_s": 3600.0, "pod": True},
             {"world": "w", "arm": "F-Jev", "cost_by_provider": {"nous": 0.4}, "queen_cost_usd": 0.3,
              "wall_s": 3600.0, "pod": True},
             {"world": "w", "arm": "S", "error": "x"}]
    c = b.costs_from_cells(cells, pod_rate_per_hr=1.0, concurrency=4)["w|F-Jev"]
    assert c["nous"] == pytest.approx(0.3) and c["jev"] == pytest.approx(0.05)
    assert c["queen_nous"] == pytest.approx(0.2) and c["runpod"] == pytest.approx(0.25)
