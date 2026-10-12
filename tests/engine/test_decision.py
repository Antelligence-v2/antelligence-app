import json
from pathlib import Path

import pytest

from antelligence.experiments.pilot_contract import LabelledQuestion, PilotWorld, report_is_true
from antelligence.kernel.decision import (
    REPORT,
    Answer,
    DecisionError,
    DecisionRequest,
    Question,
    SensedState,
    Sensor,
    check_answers,
)
from antelligence.kernel.types import LocalView

FIXTURES = Path(__file__).parent / "fixtures" / "decision"


def questions():
    return {
        "food_known": Question("noul", "Does the agent know where food is?",
                               criteria={"true": "A food location is stated", "false": "No food location is stated"}),
        "move": Question("choice", "Which action moves toward the food?", ("move north", "move south", "stay")),
        "urgency": Question("score", "How urgent is moving now?", ("Not urgent", "Somewhat urgent", "Very urgent")),
    }


def test_wire_payload_matches_recorded_jev_request():
    recorded = json.loads((FIXTURES / "jev_1_13_0_reply.json").read_text())["request"]
    request = DecisionRequest("jev-1.13.0", recorded["state"], questions())
    assert request.payload() == recorded


def test_seeded_shuffle_is_deterministic_and_recorded_in_hash():
    a = DecisionRequest.build("jev-1.13.0", "state", questions(), seed=7)
    b = DecisionRequest.build("jev-1.13.0", "state", questions(), seed=7)
    assert a.payload() == b.payload() and a.request_hash == b.request_hash
    orders = {DecisionRequest.build("m", "state", questions(), seed=s).questions["move"].options for s in range(20)}
    assert len(orders) > 1
    assert all(sorted(o) == sorted(questions()["move"].options) for o in orders)
    # noul and score are never reordered: score levels are ordinal
    assert a.questions["urgency"].options == questions()["urgency"].options


def test_question_validation():
    with pytest.raises(ValueError):
        Question("free_text", "x")
    with pytest.raises(ValueError):
        Question("noul", "x", ("a", "b"))
    with pytest.raises(ValueError):
        Question("choice", "x", ("only",))
    with pytest.raises(ValueError):
        Question("choice", "x", ("a", "a"))


def test_request_rejects_long_or_empty_state():
    with pytest.raises(ValueError):
        DecisionRequest("m", "", questions())
    with pytest.raises(ValueError):
        DecisionRequest("m", "x" * 5000, questions())


def test_answers_from_both_fixtures_satisfy_the_contract():
    for name in ("jev_1_13_0_reply.json", "laya_typed_decisions_reply.json"):
        data = json.loads((FIXTURES / name).read_text())
        request = DecisionRequest(data["request"]["model"], data["request"]["state"], questions())
        answers = {}
        for qid, raw in data["response"]["answers"].items():
            if raw["type"] == "noul":
                answers[qid] = Answer("noul", raw["noul"], {"yes": raw["noul"], "no": 1 - raw["noul"]})
            elif raw["type"] == "choice":
                answers[qid] = Answer("choice", raw["choice"], raw["probabilities"], raw["confidence"])
            else:
                answers[qid] = Answer("score", raw["score"], raw["probabilities"], raw["confidence"])
        check_answers(request, answers)


def test_check_answers_refuses_mismatches():
    request = DecisionRequest("m", "state", {"move": questions()["move"]})
    with pytest.raises(DecisionError):
        check_answers(request, {})
    bad = Answer("choice", "fly", {"fly": 1.0}, 1.0)
    with pytest.raises(DecisionError):
        check_answers(request, {"move": bad})
    with pytest.raises(ValueError):
        Answer("noul", 0.5, {"yes": 0.9, "no": 0.9})


def test_sensed_state_rules():
    s = SensedState("Carrying food: no.", {"carrying": False}, {"north": "move one cell north"})
    assert s.fields == {"carrying": False}
    with pytest.raises(ValueError):
        SensedState("x", {}, {REPORT: "not allowed as a world action"})
    with pytest.raises(ValueError):
        SensedState("", {}, {"north": "x"})
    check = Question("noul", "Is the food patch you remember still there?")
    assert SensedState("x", {}, {"north": "x"}, {"patch": check}).checks == {"patch": check}
    with pytest.raises(ValueError):
        SensedState("x", {}, {"north": "x"}, {"a": check, "b": check, "c": check})
    with pytest.raises(ValueError):
        SensedState("x", {}, {"north": "x"}, {"m": questions()["move"]})


def test_labelled_question_and_report_truth():
    q = questions()["move"]
    LabelledQuestion("m", "move", q, "stay")
    with pytest.raises(ValueError):
        LabelledQuestion("m", "move", q, "fly")
    with pytest.raises(ValueError):
        LabelledQuestion("f", "judgement", questions()["food_known"], 1)
    assert report_is_true("explore", ("go_patch",)) is True
    assert report_is_true("go_patch", ("go_patch", "explore")) is False
    assert report_is_true(("a", "b"), ("b",)) is False  # one good action allowed -> the report is false
    assert report_is_true(("a", "b"), ("c",)) is True


def test_labelled_question_accept_set():
    q = Question("choice", "Which?", ("a", "b", "c"))
    assert LabelledQuestion("m", "move", q, "a").accept == ("a",)
    assert LabelledQuestion("m", "move", q, "a", accept=("a", "c")).accept == ("a", "c")
    for bad in (("b",), ("a", "z")):
        with pytest.raises(ValueError):
            LabelledQuestion("m", "move", q, "a", accept=bad)
    with pytest.raises(ValueError):
        LabelledQuestion("f", "judgement", questions()["food_known"], True, accept=("a",))


def test_protocols_are_runtime_checkable():
    class Echo:
        def sense(self, view: LocalView) -> SensedState:
            return SensedState(f"Tick {view.tick}.", {}, {"stay": "do nothing"})

        def describe(self):
            return {"sensor": "echo"}

    assert isinstance(Echo(), Sensor)
    assert not isinstance(Echo(), PilotWorld)


def test_pilot_world_needs_short_instructions():
    from antelligence.experiments.pilot_contract import MAX_INSTRUCTIONS
    from tests.engine.fake_pilot_world import FakePilotWorld

    world = FakePilotWorld()
    assert isinstance(world, PilotWorld) and 0 < len(world.instructions) <= MAX_INSTRUCTIONS
    bare = type("Bare", (), {k: v for k, v in vars(FakePilotWorld).items() if k != "instructions"})()
    assert not isinstance(bare, PilotWorld)
