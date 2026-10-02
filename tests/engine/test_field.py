import math

import pytest

from antelligence.kernel.field import BoardField, FieldFullError, GridField, SenseQuery
from antelligence.kernel.signal import Signal


def sig(sender="a0", scope="r:x", kind="found", t=1, ttl=3, pos=(0, 0), topic=None, payload=None):
    return Signal(sender=sender, scope=scope, kind=kind, emitted_at=t, revision=0, ttl=ttl,
                  pos=None if topic else pos, topic=topic, payload=payload or {})


def test_grid_sense_respects_radius_scope_liveness_and_sender():
    field = GridField()
    near, far = sig(pos=(1, 0)), sig(pos=(10, 0), sender="a1")
    other_arm = sig(scope="r:y", pos=(0, 1))
    mine = sig(sender="me", pos=(0, 0))
    for s in (near, far, other_arm, mine):
        assert field.deposit(s)
    q = SenseQuery(pos=(0, 0), radius=2)
    assert field.sense("r:x", 1, q) == [], "same-tick signals are invisible"
    assert field.sense("r:x", 2, q, exclude_sender="me") == [near]
    assert set(field.sense("r:x", 2, q)) == {near, mine}
    assert field.sense("r:x", 5, q) == [], "expired after ttl"


def test_grid_sense_orders_by_distance_and_caps_results():
    field = GridField()
    signals = [sig(sender=f"a{i}", pos=(i, 0)) for i in range(5)]
    for s in reversed(signals):
        field.deposit(s)
    got = field.sense("r:x", 2, SenseQuery(pos=(0, 0), radius=10, max_results=3))
    assert got == signals[:3]


def test_kind_filter_and_topic_signals_invisible_on_grid():
    field = GridField()
    found, alarm = sig(kind="found"), sig(kind="alarm", sender="a1")
    field.deposit(found), field.deposit(alarm), field.deposit(sig(topic="q1", sender="a2"))
    q = SenseQuery(pos=(0, 0), radius=1, kinds=frozenset({"alarm"}))
    assert field.sense("r:x", 2, q) == [alarm]


def test_duplicate_deposit_is_refused_and_capacity_enforced():
    field = GridField(max_live=2)
    s = sig()
    assert field.deposit(s) is True
    assert field.deposit(sig()) is False
    field.deposit(sig(sender="a1"))
    with pytest.raises(FieldFullError):
        field.deposit(sig(sender="a2"))


def test_expire_removes_only_dead_signals():
    field = GridField()
    short, long = sig(ttl=1), sig(ttl=5, sender="a1")
    field.deposit(short), field.deposit(long)
    assert field.expire(1) == []
    assert field.expire(2) == [short]
    assert len(field) == 1


def test_intensity_decays_with_distance_and_age():
    field = GridField(decay_rate=0.5)
    field.deposit(sig(kind="trail", pos=(0, 0), payload={"amount": 2.0}, ttl=10))
    at_source = field.intensity_at("r:x", 2, (0, 0), "trail", radius=4)
    assert at_source == pytest.approx(2.0)
    assert field.intensity_at("r:x", 2, (2, 0), "trail", radius=4) == pytest.approx(1.0)
    assert field.intensity_at("r:x", 4, (0, 0), "trail", radius=4) == pytest.approx(2.0 * math.exp(-1.0))
    assert field.intensity_at("r:x", 2, (9, 0), "trail", radius=4) == 0.0


def test_board_field_is_topical():
    board = BoardField()
    q1a, q1b, q2 = sig(topic="q1"), sig(topic="q1", sender="a1"), sig(topic="q2", sender="a2")
    for s in (q1a, q1b, q2):
        board.deposit(s)
    assert board.sense("r:x", 2, SenseQuery(topic="q1")) == sorted([q1a, q1b], key=lambda s: s.id)
    assert board.sense("r:x", 2, SenseQuery(pos=(0, 0), radius=99)) == []
    assert board.snapshot("r:x", 2) and board.snapshot("r:y", 2) == []


def test_sense_query_validation():
    with pytest.raises(ValueError):
        SenseQuery(radius=-1)
    with pytest.raises(ValueError):
        SenseQuery(radius=math.inf)
