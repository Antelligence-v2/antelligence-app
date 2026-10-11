import json

import pytest

from antelligence.experiments import v4_calibration as c
from antelligence.experiments import v4_pilot as p
from antelligence.experiments.v4_metrics import calibration_summary
from antelligence.kernel.decision import Answer, DecisionResponse, Question
from tests.engine.fake_pilot_world import FakePilotWorld


def test_harvest_is_balanced_dev_only_and_carries_accept():
    worlds = {"a": FakePilotWorld("a"), "b": FakePilotWorld("b")}
    items = c.harvest_questions(worlds, total=40)
    assert len(items) == 40 and {i["world"] for i in items} == {"a", "b"}
    assert sum(i["world"] == "a" for i in items) == 20
    assert {i["kind"] for i in items} == {"judgement", "move"}
    assert abs(sum(i["kind"] == "move" for i in items) - 20) <= 2
    assert len({i["id"] for i in items}) == 40 and all(i["seed"] in p.DEV_SEEDS for i in items)
    assert all(i["accept"] == [i["label"]] for i in items if i["kind"] == "move")
    assert all(i["accept"] == [] for i in items if i["kind"] == "judgement")
    with pytest.raises(ValueError):
        c.harvest_questions(worlds, seeds=[1, 2])


def test_calibrate_rows_fit_the_metric_summary():
    items = c.harvest_questions({"a": FakePilotWorld("a")}, total=30)
    rows = c.asyncio.run(c.calibrate(p.DryBackend("x"), "x", items))
    assert len(rows) == 30 and all(r["latency_s"] >= 0 for r in rows)
    assert all("probabilities" in r for r in rows) and all("accept" in r for r in rows if r["kind"] == "move")
    s = calibration_summary(rows)
    assert s["scored"] == 30 and 0 <= s["accuracy"] <= 1 and 0 <= s["ece"] <= 1
    again = c.asyncio.run(c.calibrate(p.DryBackend("x"), "x", items, done=[f"x:{i['id']}" for i in items[:10]]))
    assert len(again) == 20
    json.dumps(rows)


class Fixed:
    """A backend that always answers with the given probabilities."""

    def __init__(self, probs):
        self.probs = probs

    def describe(self):
        return {"model": "fixed"}

    async def decide(self, request):
        top = max(self.probs, key=self.probs.get)
        return DecisionResponse({"q": Answer("choice", top, dict(self.probs), self.probs[top])}, "fixed",
                                request.request_hash, 1, 1)


def test_choice_item_is_correct_for_any_accepted_answer_and_scores_the_accepted_mass():
    q = Question("choice", "Which?", ("a", "b", "c"))
    item = {"id": "i", "world": "w", "kind": "move", "qtype": "choice", "state": "s", "question": q, "label": "a",
            "accept": ["a", "b"], "seed": 100, "tick": 1}
    row = c.asyncio.run(c.calibrate(Fixed({"a": 0.2, "b": 0.5, "c": 0.3}), "f", [item]))[0]
    assert row["answer"] == "b" and row["correct"] is True and row["label"] is True
    assert row["prob"] == pytest.approx(0.7) and row["accept"] == ["a", "b"]
    assert row["probabilities"] == {"a": 0.2, "b": 0.5, "c": 0.3}  # kept so the row can be rescored
    wrong = c.asyncio.run(c.calibrate(Fixed({"a": 0.1, "b": 0.1, "c": 0.8}), "f", [item]))[0]
    assert wrong["correct"] is False and wrong["prob"] == pytest.approx(0.2)
    legacy = {**item, "accept": []}  # an item without an accept set falls back to its label
    assert c.asyncio.run(c.calibrate(Fixed({"a": 0.6, "b": 0.3, "c": 0.1}), "f", [legacy]))[0]["accept"] == ["a"]
