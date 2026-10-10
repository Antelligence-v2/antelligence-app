"""Reputation reaches signals and recalled claims without changing old hashes."""

import pytest

from antelligence.kernel import GridField, RunConfig, Scheduler, SignalDraft
from antelligence.kernel import events as ev
from antelligence.kernel.memory import CLAIM, EvidenceMemory, RecalledRecord, ScopedRecall
from antelligence.kernel.reputation import EVALUATOR, LABEL, ReputationLedger, ReputationView
from antelligence.kernel.signal import Signal, SignalError
from tests.engine.toy_world import ForagerPolicy, ToyWorld

# Computed on upstream main @ 3c7418e, before sender_reputation existed. Old signal ids,
# config hashes and trace hashes (and so every recorded replay) must not move.
PINNED_SIGNAL_ID = "24924df93ef3b6689dbc82685c4a30a0f8cbec1b111f4fa1ab5370cba1cdbdb5"
PINNED_CONFIG_HASH = "5833e81697543a15c4f83fdfdb9a4a7be63d7b7a49a52cea3f4e99c10dfb0497"
PINNED_TRACE_HASH = "73fcf304f1da6b3c08d8560ce36cbec49da6a35501428c86d2562d27b49bd0fd"


def _signal(**kw):
    return Signal.stamp(SignalDraft(kind="food", pos=(1, 2), payload={"n": 1}), sender="a0", scope="arm",
                        tick=3, revision=0, **kw)


def test_absent_reputation_leaves_the_signal_body_and_id_unchanged():
    plain = _signal()
    assert plain.id == PINNED_SIGNAL_ID
    assert "sender_reputation" not in plain.to_dict()
    assert Signal.from_dict(plain.to_dict()).id == plain.id


def test_stamped_reputation_is_hashed_and_roundtrips():
    stamped = _signal(sender_reputation=0.8)
    assert stamped.id != _signal().id and stamped.to_dict()["sender_reputation"] == 0.8
    assert Signal.from_dict(stamped.to_dict()) == stamped
    forged = dict(stamped.to_dict(), sender_reputation=0.99)
    with pytest.raises(SignalError):
        Signal.from_dict(forged)  # id no longer matches: reputation cannot be edited after stamping
    with pytest.raises(SignalError):
        _signal(sender_reputation=1.5)


def _run(reputation=None, seed=5):
    world = ToyWorld()
    sched = Scheduler(world, {a: ForagerPolicy() for a in world.agents()}, GridField(),
                      RunConfig("r", seed=seed, max_ticks=40), reputation=reputation)
    return sched, sched.run()


def test_scheduler_without_reputation_keeps_its_config_and_trace_hashes():
    _, result = _run(reputation=None)
    assert (result.config_hash, result.trace_hash) == (PINNED_CONFIG_HASH, PINNED_TRACE_HASH)


def test_scheduler_stamps_frozen_reputation_on_every_signal_and_pins_it_in_the_config_hash():
    ledger = ReputationLedger()
    ledger.record(persona="forager", area="toy", channel=LABEL, success=True, author=EVALUATOR)
    view = ReputationView(ledger, {"a0": "forager", "a1": "forager", "a2": "forager"}, area="toy", chance=0.5)
    sched, result = _run(reputation=view)
    deposited = sched.log.of_type(ev.SIGNAL_DEPOSITED)
    assert deposited, "toy foragers should emit signals"
    assert {e.data["sender_reputation"] for e in deposited} == {view("a0")}
    _, plain = _run(reputation=None)
    assert result.config_hash != plain.config_hash
    ledger.record(persona="forager", area="toy", channel=LABEL, success=True, author=EVALUATOR)
    _, other = _run(reputation=ReputationView(ledger, view.persona_of, area="toy", chance=0.5))
    assert other.config_hash != result.config_hash  # a different starting record is a different run


def test_recall_attaches_author_reputation_at_read_time_without_touching_content():
    memory = EvidenceMemory(min_confirmations=2)
    a = memory.propose(scope="s", kind=CLAIM, author="w1", subject="q", body={"answer": "yes"}, tick=1)
    b = memory.propose(scope="s", kind=CLAIM, author="w2", subject="q", body={"answer": "yes"}, tick=1)
    assert a.content_key == b.content_key and memory.is_usable(a.id)  # two-witness admission still works
    standings = {"w1": 0.9, "w2": 0.4}
    plain = ScopedRecall(memory).recall_for("w3", "s", 2, {})
    rich = ScopedRecall(memory, reputation=standings.get).recall_for("w3", "s", 2, {})
    assert all(not isinstance(r, RecalledRecord) for r in plain)
    assert all(isinstance(r, RecalledRecord) for r in rich)
    assert [r.id for r in rich] == [r.id for r in plain]
    assert rich[0].author_reputation == standings[rich[0].author]
    assert rich[0].to_dict()["author_reputation"] == standings[rich[0].author]
