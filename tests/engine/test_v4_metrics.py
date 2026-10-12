import pytest

from antelligence.experiments import v4_metrics as m


def cell(world, arm, seed, cond, score, **kw):
    return {"world": world, "arm": arm, "seed": seed, "condition": cond, "score": score, **kw}


def test_gap_recovered_hand_computed():
    assert m.gap_recovered(0.6, 0.2, 1.0) == pytest.approx(0.5)
    assert m.gap_recovered(0.2, 0.2, 1.0) == 0.0
    assert m.gap_recovered(1.2, 0.2, 1.0) == pytest.approx(1.25)  # can exceed the ceiling
    assert m.gap_recovered(0.1, 0.2, 1.0) == pytest.approx(-0.125)
    assert m.gap_recovered(0.5, 0.5, 0.5) is None  # no headroom between S and S'


def test_percentiles_and_seconds_per_decision():
    values = [float(i) for i in range(1, 11)]
    assert m.percentile(values, 50) == 5.5
    assert m.percentile(values, 90) == pytest.approx(9.1)
    assert m.percentile([], 50) is None
    assert m.seconds_per_decision([3.0, 1.0, 2.0]) == {"n": 3, "median": 2.0, "p90": pytest.approx(2.8)}


def test_brier_ece_accuracy():
    assert m.brier([0.9, 0.2], [True, False]) == pytest.approx(0.025)
    # bin 9: mean p 0.95 vs accuracy 0.5 -> 0.45; bin 1: 0.15 vs 0 -> 0.15; each weighs half
    assert m.ece([0.95, 0.95, 0.15, 0.15], [True, False, False, False]) == pytest.approx(0.30)
    assert m.ece([1.0, 1.0], [True, True]) == 0.0  # p == 1.0 lands in the top bin
    assert m.ece([], []) is None
    rows = [{"prob": 0.9, "label": True, "correct": True, "latency_s": 1.0},
            {"prob": 0.2, "label": False, "correct": True, "latency_s": 3.0},
            {"error": "boom"}]
    s = m.calibration_summary(rows)
    assert (s["n"], s["scored"], s["errors"], s["accuracy"]) == (3, 2, 1, 1.0)
    assert s["brier"] == pytest.approx(0.025) and s["latency_s"]["median"] == 2.0


def test_paired_bootstrap_is_seeded_paired_and_bounded():
    x = {("w", 1, "v1"): 0.5, ("w", 2, "v1"): 0.7, ("w", 3, "v1"): 0.9}
    y = {("w", 1, "v1"): 0.3, ("w", 2, "v1"): 0.3, ("w", 3, "v1"): 0.3, ("w", 9, "v1"): 5.0}  # seed 9 unpaired
    a = m.paired_bootstrap(x, y, resamples=500)
    assert a == m.paired_bootstrap(x, y, resamples=500)  # same seed, same interval
    assert a["pairs"] == 3 and a["seeds"] == 3
    assert a["mean_diff"] == pytest.approx(0.4)
    assert 0.2 <= a["low"] <= a["mean_diff"] <= a["high"] <= 0.6 + 1e-9
    same = m.paired_bootstrap({("w", 1, "v1"): 0.5, ("w", 2, "v1"): 0.5}, {("w", 1, "v1"): 0.25, ("w", 2, "v1"): 0.25})
    assert same["low"] == same["high"] == 0.25
    assert m.paired_bootstrap(x, {})["pairs"] == 0


def test_bootstrap_resamples_whole_seeds():
    # two conditions per seed move together: with one seed the interval has zero width
    x = {("w", 1, "v1"): 1.0, ("w", 1, "v2"): 0.0}
    y = {("w", 1, "v1"): 0.0, ("w", 1, "v2"): 0.0}
    r = m.paired_bootstrap(x, y, resamples=50)
    assert r["low"] == r["high"] == 0.5


def arms(ds_g, ds_t, jev_g, jev_t, laya_g=0.0, laya_t=9.0):
    return ({"DS-all": ds_g, "F-Jev": jev_g, "F-Laya": laya_g}, {"DS-all": ds_t, "F-Jev": jev_t, "F-Laya": laya_t})


def test_go_when_close_enough_and_faster():
    r = m.go_no_go(*arms(0.6, 2.0, 0.55, 0.5))
    assert r["verdict"] == "go" and r["go_arms"] == ["F-Jev"] and not r["go_also_holds"]


def test_go_boundary_is_inclusive_and_latency_strict():
    assert m.go_no_go(*arms(1.0, 2.0, 0.9, 1.0))["verdict"] == "go"  # exactly DS - 0.10
    assert m.go_no_go(*arms(1.0, 2.0, 0.8999, 1.0))["verdict"] == "unclear"  # just outside the margin
    assert m.go_no_go(*arms(1.0, 2.0, 1.0, 2.0))["verdict"] == "unclear"  # not strictly faster


def test_no_go_needs_both_framework_arms_below_point_one():
    assert m.go_no_go(*arms(0.6, 2.0, 0.05, 0.5, laya_g=0.09))["verdict"] == "no-go"
    assert m.go_no_go(*arms(0.6, 2.0, 0.05, 0.5, laya_g=0.10))["verdict"] == "unclear"  # 0.10 is not below


def test_no_go_takes_precedence_when_both_hold():
    r = m.go_no_go(*arms(-0.5, 2.0, 0.05, 0.5, laya_g=0.01))
    assert r["verdict"] == "no-go" and r["go_also_holds"] and r["go_arms"] == ["F-Jev"]


def test_missing_data_is_unclear():
    assert m.go_no_go({"DS-all": None, "F-Jev": 0.5, "F-Laya": 0.5}, {})["verdict"] == "unclear"


def test_aggregate_g_base_share_and_comparison():
    cells = []
    for seed in (1, 2):
        cells += [cell("w", "S", seed, "base", 0.5), cell("w", "S", seed, "v1", 0.0),
                  cell("w", "S-prime", seed, "v1", 1.0),
                  cell("w", "F-Jev", seed, "base", 0.4, latencies_s=[1.0, 3.0]),
                  cell("w", "F-Jev", seed, "v1", 0.5 + 0.1 * seed, latencies_s=[1.0, 3.0]),
                  cell("w", "DS-all", seed, "base", 0.5, latencies_s=[4.0]),
                  cell("w", "DS-all", seed, "v1", 0.4, latencies_s=[4.0])]
    out = m.aggregate(cells)
    assert out["arms"]["F-Jev"]["mean_g"] == pytest.approx(0.65)  # G = score here, since S=0 and S'=1
    assert out["arms"]["DS-all"]["mean_g"] == pytest.approx(0.4)
    assert out["arms"]["F-Jev"]["base_share_of_S"] == pytest.approx(0.8)
    assert out["arms"]["S"]["mean_g"] is None  # scripts have no G
    assert out["arms"]["F-Jev"]["s_per_decision"]["median"] == 2.0
    assert out["comparisons_mean_g_diff"]["F-Jev_vs_DS-all"]["mean_diff"] == pytest.approx(0.25)
    assert out["go_no_go"]["verdict"] == "go"  # F-Jev: G .65 >= .30 and 2 s < 4 s
    assert out["go_no_go"]["arms"]["F-Laya"]["mean_g"] is None  # absent arm


def test_g_is_undefined_below_the_preregistered_min_gap():
    from antelligence.experiments.v4_metrics import MIN_GAP, gap_recovered
    assert gap_recovered(5.0, 4.0, 5.5, MIN_GAP["foraging_sb"]) is None  # S' - S = 1.5 < 2 deliveries
    assert gap_recovered(6.0, 4.0, 8.0, MIN_GAP["foraging_sb"]) == 0.5
    assert gap_recovered(0.5, 0.48, 0.5, MIN_GAP["graph_coloring"]) is None


def test_go_no_go_uses_only_seed_paired_keys():
    from antelligence.experiments.v4_metrics import aggregate

    def cell(arm, seed, cond, score, lat=1.0):
        return {"world": "graph_coloring", "arm": arm, "seed": seed, "condition": cond, "score": score,
                "latencies_s": [lat]}
    cells = []
    for seed in (1, 2, 3):
        cells += [cell("S", seed, "base", 0.5), cell("S", seed, "v1", 0.2), cell("S-prime", seed, "v1", 0.8)]
    cells += [cell("DS-all", s, "v1", 0.5, 3.0) for s in (1, 2)]  # DS-all has seeds 1-2 only
    cells += [cell("F-Jev", s, "v1", 0.5) for s in (1, 2)] + [cell("F-Jev", 3, "v1", 0.8)]
    cells += [cell("F-Laya", s, "v1", 0.2) for s in (1, 2, 3)]
    out = aggregate(cells)
    verdict = out["go_no_go"]
    assert verdict["paired_keys"] == 2
    assert abs(verdict["arms"]["F-Jev"]["mean_g"] - 0.5) < 1e-9  # seed 3 (G = 1.0) is unpaired, so excluded
    assert verdict["verdict"] == "go" and verdict["go_arms"] == ["F-Jev"]


def test_primary_bootstrap_uses_the_same_paired_keys_and_counts_undefined_g():
    from antelligence.experiments.v4_metrics import aggregate

    def cell(arm, seed, cond, score):
        return {"world": "graph_coloring", "arm": arm, "seed": seed, "condition": cond, "score": score,
                "latencies_s": [1.0]}
    cells = []
    for seed in (1, 2, 3):
        cells += [cell("S", seed, "v1", 0.2), cell("S-prime", seed, "v1", 0.8 if seed != 3 else 0.22)]
    cells += [cell(a, s, "v1", 0.5) for a in ("DS-all", "F-Jev", "F-Laya") for s in (1, 2, 3)]
    out = aggregate(cells)
    assert out["go_no_go"]["paired_keys"] == 2  # seed 3: S' - S = 0.02 < 0.05, G undefined for everyone
    assert out["comparisons_mean_g_diff"]["F-Jev_vs_DS-all"]["pairs"] == 2
    assert out["arms"]["F-Jev"]["g_undefined"] == 1
