import math

import pytest

from antelligence.kernel.canonical import CanonicalError, canonical_json, content_hash
from antelligence.kernel.signal import MAX_PAYLOAD_BYTES, Signal, SignalDraft, SignalError


def make(**overrides):
    base = dict(sender="a0", scope="run1:arm", kind="found", emitted_at=3, revision=0, ttl=2, pos=(1, 2))
    base.update(overrides)
    return Signal(**base)


def test_canonical_json_is_order_independent_and_rejects_nan():
    assert canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1})
    with pytest.raises(CanonicalError):
        canonical_json({"x": math.nan})
    with pytest.raises(CanonicalError):
        canonical_json({1: "int key"})
    with pytest.raises(CanonicalError):
        canonical_json({"x": object()})


def test_signal_id_is_content_derived_and_stable():
    a = make(payload={"cells": 7, "z": [1, 2]})
    b = make(payload={"z": [1, 2], "cells": 7})
    assert a.id == b.id and a == b and hash(a) == hash(b)
    assert make(sender="a1").id != a.id
    assert make(scope="run1:other").id != a.id
    assert a.pos == (1.0, 2.0)


def test_liveness_is_deferred_and_bounded_by_ttl():
    signal = make(emitted_at=3, ttl=2)
    assert not signal.is_live(3), "never visible in the tick it was emitted"
    assert signal.is_live(4) and signal.is_live(5)
    assert not signal.is_live(6)
    assert signal.expires_at == 5


def test_roundtrip_and_tamper_detection():
    signal = make(topic=None, payload={"k": "v"}, cites=("e1",), parent_ids=("p1",))
    data = signal.to_dict()
    assert Signal.from_dict(data) == signal
    data["payload"] = {"k": "forged"}
    with pytest.raises(SignalError, match="does not match"):
        Signal.from_dict(data)


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "Bad Kind"},
        {"kind": ""},
        {"ttl": 0},
        {"ttl": True},
        {"pos": None},  # neither pos nor topic
        {"topic": "q1"},  # both pos and topic
        {"sender": ""},
        {"emitted_at": -1},
        {"cites": ("e1", "e1")},
        {"payload": {"x": float("inf")}},
        {"pos": (1, 2, 3, 4)},
    ],
)
def test_invalid_signals_are_rejected(overrides):
    with pytest.raises(SignalError):
        make(**overrides)


def test_payload_size_limit():
    with pytest.raises(SignalError, match="exceeds"):
        make(payload={"blob": "x" * (MAX_PAYLOAD_BYTES + 1)})


def test_payload_is_detached_from_caller():
    payload = {"nested": {"v": 1}}
    signal = make(payload=payload)
    payload["nested"]["v"] = 2
    assert signal.payload["nested"]["v"] == 1


def test_stamp_sets_identity_from_scheduler_not_draft():
    draft = SignalDraft(kind="claim", topic="q1", payload={"answer": "B"}, cites=("e3",))
    signal = Signal.stamp(draft, sender="agent-7", scope="r:a", tick=4, revision=2)
    assert (signal.sender, signal.scope, signal.emitted_at, signal.revision) == ("agent-7", "r:a", 4, 2)
    assert signal.topic == "q1" and signal.cites == ("e3",)
    assert signal.id == content_hash({k: v for k, v in signal.to_dict().items() if k != "id"})


def test_draft_validates_eagerly():
    with pytest.raises(SignalError):
        SignalDraft(kind="found")
