import math
import random

import pytest

from antelligence.kernel import GridField, RunConfig, Scheduler
from antelligence.kernel import events as ev
from antelligence.kernel.independence import (
    default_judge,
    errors_from_runs,
    herding,
    independence,
    n_eff,
    phi,
    phi_max,
)
from tests.engine.toy_world import ForagerPolicy, ToyWorld


def _independent(k, n, p, seed):
    rng = random.Random(seed)
    return {f"a{j}": {f"i{i}": int(rng.random() < p) for i in range(n)} for j in range(k)}


def test_copies_of_one_agent_count_as_one():
    base = _independent(1, 200, 0.3, seed=1)["a0"]
    errors = {f"copy{j}": dict(base) for j in range(5)}
    report = independence(errors, bootstrap=0)
    assert report.n_eff == pytest.approx(1.0)
    assert all(report.rho[a][b] == pytest.approx(1.0) for a in report.agents for b in report.agents)


def test_independent_agents_count_close_to_k():
    report = independence(_independent(4, 4000, 0.3, seed=2), bootstrap=0)
    assert report.n_eff == pytest.approx(4.0, abs=0.25)


def test_equicorrelated_formula_matches_k_over_one_plus_k_minus_one_rho():
    agents = ["a", "b", "c"]
    rho = {(x, y): 0.5 for x in agents for y in agents if x != y}
    assert n_eff(rho, agents) == pytest.approx(3 / (1 + 2 * 0.5))
    ten = [str(i) for i in range(10)]
    rho10 = {(x, y): 0.21 for x in ten for y in ten if x != y}
    assert n_eff(rho10, ten) == pytest.approx(3.46, abs=0.01)  # "ten judges ~ 3.5"


def test_anticorrelated_errors_exceed_k_and_are_reported():
    a = {f"i{i}": i % 2 for i in range(100)}
    b = {f"i{i}": 1 - (i % 2) for i in range(100)}
    c = {f"i{i}": int(i % 4 == 0) for i in range(100)}
    report = independence({"a": a, "b": b, "c": c}, bootstrap=0)
    assert report.rho["a"]["b"] == pytest.approx(-1.0)
    assert report.n_eff > 3


def test_phi_and_phi_max_basics():
    assert phi([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    assert phi([1, 1, 1], [0, 1, 0]) is None  # constant vector: undefined, never silently zero
    assert phi_max(0.1, 0.1) == pytest.approx(1.0)
    assert phi_max(0.1, 0.5) == pytest.approx(math.sqrt(0.1 * 0.5 / (0.5 * 0.9)))
    assert phi_max(0.0, 0.5) is None


def test_rate_adjustment_exposes_a_weak_agent_that_fails_everywhere_the_strong_one_does():
    # Strong agent errs on 10% of items; the weak one errs on those same items plus 40% more.
    strong = {f"i{i}": int(i < 10) for i in range(100)}
    weak = {f"i{i}": int(i < 50) for i in range(100)}
    report = independence({"strong": strong, "weak": weak}, bootstrap=0)
    assert report.rho["strong"]["weak"] < 0.5  # raw phi says "fairly independent"
    assert report.rho_adjusted["strong"]["weak"] == pytest.approx(1.0)  # every strong error is shared
    assert report.n_eff > 1.3
    assert report.n_eff_rate_adjusted == pytest.approx(1.0)


def test_double_fault_and_overlap_are_reported():
    errors = {"a": {"x": 1, "y": 0, "z": 1}, "b": {"x": 1, "y": 1}}
    report = independence(errors, bootstrap=0, min_overlap=1)
    assert report.overlap["a"]["b"] == 2
    assert report.double_fault["a"]["b"] == pytest.approx(0.5)
    assert report.n == {"a": 3, "b": 2}


def test_low_overlap_pairs_fall_back_to_prior_and_are_flagged():
    errors = {"a": {"x": 1, "y": 0}, "b": {"x": 1, "y": 1}}
    report = independence(errors, bootstrap=0, prior=0.4)
    assert report.rho["a"]["b"] is None
    assert any(f.startswith("low_overlap") for f in report.flags)
    assert report.n_eff == pytest.approx(4 / (2 + 2 * 0.4))


def test_bootstrap_interval_is_seeded_and_brackets_the_estimate():
    errors = _independent(3, 300, 0.3, seed=3)
    a = independence(errors, bootstrap=200, seed=11)
    b = independence(errors, bootstrap=200, seed=11)
    assert a.n_eff_ci == b.n_eff_ci
    lo, hi = a.n_eff_ci
    assert lo <= a.n_eff <= hi


def test_report_serialises_to_plain_json():
    import json

    report = independence(_independent(3, 100, 0.3, seed=4), bootstrap=20)
    json.dumps(report.to_dict())


def test_herding_measures_independence_lost_to_communication():
    round0 = _independent(3, 2000, 0.3, seed=5)
    final = {a: dict(round0["a0"]) for a in round0}  # everyone converged on agent 0
    h = herding(round0, final, bootstrap=0)
    assert h["n_eff_round0"] == pytest.approx(3.0, abs=0.3)
    assert h["n_eff_final"] == pytest.approx(1.0)
    assert h["delta"] < -1.5


def test_errors_from_event_logs_use_world_outcomes_not_agent_text():
    world = ToyWorld()
    sched = Scheduler(world, {a: ForagerPolicy() for a in world.agents()}, GridField(),
                      RunConfig("r1", seed=3, max_ticks=20))
    sched.run()
    errors = errors_from_runs([("r1", sched.log)], seat_of=lambda run, agent: f"forager/{agent}")
    assert set(errors) == {f"forager/{a}" for a in world.agents()}
    outcomes = [e for e in sched.log if e.type == ev.OUTCOME and e.data.get("action") != "noop"]
    judged = sum(len(row) for row in errors.values())
    assert judged == len({(e.agent_id, e.tick) for e in outcomes})
    for event in outcomes:
        assert errors[f"forager/{event.agent_id}"][f"r1:{event.tick}"] == (0 if event.data["accepted"] else 1)


def test_default_judge_counts_policy_failures_and_ignores_rationale():
    log = ev.EventLog()
    log.append(ev.DECIDED, 1, {"action": "move", "rationale": "I am certainly right"}, "a")
    log.append(ev.POLICY_FAILED, 1, {"error": "Boom"}, "b")
    log.append(ev.OUTCOME, 1, {"action": "move", "accepted": False}, "a")
    verdicts = [default_judge("r", e) for e in log]
    assert verdicts == [None, ("b", "r:1", 1), ("a", "r:1", 1)]


def test_judge_must_return_binary_errors():
    log = ev.EventLog()
    log.append(ev.OUTCOME, 1, {"action": "x", "accepted": True}, "a")
    with pytest.raises(ValueError):
        errors_from_runs([("r", log)], judge=lambda run, e: ("a", "i", 2))
