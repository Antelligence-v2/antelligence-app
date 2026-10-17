from dataclasses import dataclass

import pytest

from antelligence.kernel import BoardField, Intent, RunConfig, Scheduler
from antelligence.kernel.hive import HiveWorld
from tests.engine.hive_helpers import ChoiceWorld, board_summary
from tests.engine.toy_world import ToyWorld


@dataclass
class Summary:
    counts: dict


def test_adds_queen_and_routes_board_sensing():
    world = HiveWorld(ChoiceWorld(n=2), board_summary)
    assert world.agents() == ["w0", "w1", "queen"]
    worker = world.observe("w0", 3)
    assert worker.data == {"tick": 3}
    assert worker.sense.topic == "board" and worker.sense.kinds == frozenset({"queen"})
    queen = world.observe("queen", 3)
    assert queen.sense.topic == "board" and queen.sense.kinds == frozenset({"report"})


def test_queen_observation_is_only_tick_and_counts():
    inner = ChoiceWorld(n=2, best="zzz-secret")
    inner.hits = 7
    obs = HiveWorld(inner, board_summary).observe("queen", 5)
    assert dict(obs.data) == {"tick": 5, "counts": {"hits": 7}}
    assert "secret" not in repr(obs.data)


def test_summary_accepts_object_with_counts():
    hive = HiveWorld(ChoiceWorld(), lambda w, t: Summary({"n": t}))
    assert dict(hive.observe("queen", 4).data["counts"]) == {"n": 4}
    with pytest.raises(TypeError):
        HiveWorld(ChoiceWorld(), lambda w, t: 5).observe("queen", 1)


def test_queen_apply_accepted_and_worker_apply_delegates():
    inner = ChoiceWorld(n=1)
    hive = HiveWorld(inner, board_summary)
    assert hive.apply("queen", Intent("noop"), 1).accepted
    hive.apply("w0", Intent("a"), 1)
    assert hive.metrics() == {"hits": 1} and inner.acts["w0"] == ["a"]
    assert hive.done(1) is False and hive.revision == inner.revision


def test_no_queen_is_pure_passthrough():
    inner = ChoiceWorld(n=2)
    hive = HiveWorld(inner, board_summary, queen=False)
    assert hive.agents() == ["w0", "w1"]
    assert hive.observe("w0", 1).sense == inner.observe("w0", 1).sense
    assert hive.describe()["queen"] is False


def test_describe_includes_inner_and_config():
    d = HiveWorld(ChoiceWorld(n=3), board_summary).describe()
    assert d["queen"] is True and d["inner"]["n"] == 3 and d["board_topic"] == "board"


def test_snapshot_and_scene_delegate_only_if_present():
    assert not hasattr(HiveWorld(ChoiceWorld(), board_summary), "snapshot")
    toy = ToyWorld()
    toy.snapshot = lambda: {"x": 1}
    assert HiveWorld(toy, board_summary).snapshot() == {"x": 1}


def test_inner_agent_named_queen_rejected():
    class Q(ChoiceWorld):
        def agents(self):
            return ["queen"]

    with pytest.raises(ValueError):
        HiveWorld(Q(), board_summary)
    HiveWorld(Q(), board_summary, queen=False)


def test_scheduler_runs_hive_world():
    class Idle:
        def decide(self, view):
            return Intent("noop")

        def describe(self):
            return {}

    sched = Scheduler(HiveWorld(ChoiceWorld(n=2), board_summary), {}, BoardField(), RunConfig(run_id="t", max_ticks=2),
                      default_policy=Idle())
    assert sched.run().ticks == 2
