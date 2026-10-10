import pytest

from antelligence.kernel import events as ev
from antelligence.kernel.memory import TrustError
from antelligence.kernel.reputation import (
    EVALUATOR,
    LABEL,
    VERIFICATION,
    ReputationLedger,
    ReputationView,
)


def test_unknown_persona_sits_exactly_at_chance():
    ledger = ReputationLedger()
    assert ledger.accuracy("new/scout", "qa/finance", chance=1 / 3) == pytest.approx(1 / 3)
    assert ledger.accuracy("new/scout", "qa/finance", chance=0.5) == pytest.approx(0.5)


def test_only_authorities_may_write():
    ledger = ReputationLedger()
    with pytest.raises(TrustError):
        ledger.record(persona="qwen/scout", area="qa", channel=LABEL, success=True, author="worker-1")
    with pytest.raises(TrustError):
        ledger.record(persona="qwen/scout", area="qa", channel=LABEL, success=True, author="qwen/scout")
    assert ledger.snapshot()["counts"] == []


def test_verdicts_move_the_posterior_and_areas_channels_are_separate():
    ledger = ReputationLedger(prior_strength=2.0)
    for _ in range(8):
        ledger.record(persona="qwen/scout", area="qa/finance", channel=LABEL, success=True, author=EVALUATOR)
    for _ in range(2):
        ledger.record(persona="qwen/scout", area="qa/finance", channel=LABEL, success=False, author=EVALUATOR)
    s = ledger.standing("qwen/scout", "qa/finance", chance=0.5)
    assert (s.successes, s.failures, s.n) == (8, 2, 10)
    assert s.accuracy == pytest.approx((1 + 8) / (2 + 10))
    assert ledger.accuracy("qwen/scout", "qa/medical", chance=0.5) == pytest.approx(0.5)
    assert ledger.accuracy("qwen/scout", "qa/finance", chance=0.5, channel=VERIFICATION) == pytest.approx(0.5)


def test_rejects_bad_channels_and_non_bool_success():
    ledger = ReputationLedger()
    with pytest.raises(ValueError):
        ledger.record(persona="p", area="a", channel="vibes", success=True, author=EVALUATOR)
    with pytest.raises(ValueError):
        ledger.record(persona="p", area="a", channel=LABEL, success=0.9, author=EVALUATOR)
    with pytest.raises(ValueError):
        ledger.accuracy("p", "a", chance=0)


def test_forgetting_down_weights_old_verdicts():
    ledger = ReputationLedger(forgetting=0.5)
    for _ in range(10):
        ledger.record(persona="p", area="a", channel=LABEL, success=True, author=EVALUATOR)
    ledger.record(persona="p", area="a", channel=LABEL, success=False, author=EVALUATOR)
    s = ledger.standing("p", "a", chance=0.5)
    assert s.failures == 1 and s.successes < 1.0


def test_snapshot_roundtrip_and_hash_changes_with_evidence():
    ledger = ReputationLedger()
    before = ledger.snapshot_hash()
    ledger.record(persona="p", area="a", channel=LABEL, success=True, author=EVALUATOR)
    after = ledger.snapshot_hash()
    assert before != after
    clone = ReputationLedger.from_snapshot(ledger.snapshot())
    assert clone.snapshot_hash() == after


def test_ledger_rebuilds_from_logged_updates():
    ledger = ReputationLedger()
    log = ev.EventLog()
    for i, ok in enumerate([True, False, True]):
        ledger.record(persona="p", area="a", channel=LABEL, success=ok, author=EVALUATOR, tick=i, ref=f"item{i}")
        for update in ledger.drain_updates():
            log.append(ev.REPUTATION_UPDATED, i, update)
    assert ReputationLedger.from_events(log).snapshot_hash() == ledger.snapshot_hash()


def test_view_is_frozen_and_named_by_its_snapshot():
    ledger = ReputationLedger()
    ledger.record(persona="qwen/scout", area="qa", channel=LABEL, success=True, author=EVALUATOR)
    view = ReputationView(ledger, {"worker-1": "qwen/scout"}, area="qa", chance=0.5)
    value, described = view("worker-1"), view.describe()
    for _ in range(5):
        ledger.record(persona="qwen/scout", area="qa", channel=LABEL, success=False, author=EVALUATOR)
    assert view("worker-1") == value  # later verdicts do not leak into a running view
    assert view.describe() == described and described["snapshot"] != ledger.snapshot_hash()
    assert view("stranger") is None


def test_reliability_adapter_feeds_the_aggregator_signature():
    ledger = ReputationLedger()
    ledger.record(persona="p", area="a", channel=LABEL, success=True, author=EVALUATOR)
    reliability = ledger.reliability("a")
    assert reliability("p", 0.5) == pytest.approx(ledger.accuracy("p", "a", chance=0.5))
