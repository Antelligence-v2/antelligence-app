"""The experiment recommendation: pick the arm that works, or say none did."""

from antelligence.experiments.runner import recommend


def comp(wins, losses, ties, p, delta, pct):
    return {"pairs": wins + losses + ties, "dropped_pairs": 0, "wins": wins, "losses": losses, "ties": ties,
            "baseline_total": 0, "treatment_total": 0, "mean_delta": delta, "pct_change": pct,
            "sign_test_p": p, "lower_is_better": True}


def summary(unsafe=0, failures=0):
    return {"unsafe_applied": unsafe, "policy_failures": failures}


def test_best_significant_improvement_wins():
    rec = recommend({"a": comp(17, 2, 1, 0.0007, -40.0, -32.0), "b": comp(14, 5, 1, 0.03, -10.0, -8.0)},
                    {"base": summary(), "a": summary(), "b": summary()},
                    baseline="base", metric_label="moves", lower_is_better=True)
    assert rec["best_arm"] == "a"
    assert rec["verdicts"]["a"]["verdict"] == "better"
    assert "0 unsafe acts" in rec["summary"]


def test_unsafe_arm_is_excluded_even_if_it_scores_best():
    rec = recommend({"a": comp(19, 0, 1, 0.00001, -60.0, -50.0), "b": comp(15, 3, 2, 0.008, -12.0, -9.0)},
                    {"base": summary(), "a": summary(unsafe=1), "b": summary()},
                    baseline="base", metric_label="moves", lower_is_better=True)
    assert rec["verdicts"]["a"]["verdict"] == "excluded"
    assert rec["best_arm"] == "b"


def test_worse_and_unclear_arms_are_not_recommended():
    rec = recommend({"worse": comp(2, 16, 2, 0.001, 20.0, 15.0), "flat": comp(5, 5, 10, 1.0, 0.0, 0.0)},
                    {"base": summary(), "worse": summary(), "flat": summary()},
                    baseline="base", metric_label="moves", lower_is_better=True)
    assert rec["best_arm"] is None
    assert rec["verdicts"]["worse"]["verdict"] == "worse"
    assert rec["verdicts"]["flat"]["verdict"] == "no_clear_difference"
    assert not rec["underpowered"]


def test_too_few_seeds_is_reported_as_underpowered():
    rec = recommend({"a": comp(3, 0, 0, 0.25, -5.0, -10.0)}, {"base": summary(), "a": summary()},
                    baseline="base", metric_label="moves", lower_is_better=True)
    assert rec["best_arm"] is None
    assert rec["underpowered"] is True
    assert "Too few seeds" in rec["summary"]
