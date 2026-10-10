import itertools
import math

import pytest

from antelligence.kernel.aggregate import (
    ABSTAIN,
    FAILED,
    OTHER,
    UNVERIFIED,
    VERIFIED,
    Aggregator,
    Vote,
    canonical_answer,
)
from antelligence.kernel.reputation import EVALUATOR, LABEL, ReputationLedger

CHOICES = ["yes", "no", "maybe"]


def fixed(acc):
    return lambda persona, chance: acc.get(persona)


def plain_vote():
    return Aggregator(use_reputation=False, use_correlation=False, use_verification=False)


def test_with_all_mechanisms_off_it_is_plurality_vote():
    votes = [Vote("s1", "p", "yes"), Vote("s2", "p", "no"), Vote("s3", "p", "yes")]
    decision = plain_vote().decide(votes, choices=CHOICES)
    assert decision.answer == "yes" and not decision.abstained


def test_equal_reputation_and_zero_correlation_equals_plurality():
    agg = Aggregator(reliability=fixed({"a": 0.8, "b": 0.8, "c": 0.8}), use_verification=False)
    for answers in itertools.product(CHOICES, repeat=3):
        votes = [Vote(f"s{i}", p, ans) for i, (p, ans) in enumerate(zip("abc", answers))]
        counts = {c: answers.count(c) for c in CHOICES}
        best = max(counts.values())
        winners = sorted(c for c in CHOICES if counts[c] == best)
        assert agg.decide(votes, choices=CHOICES).answer in winners


def test_single_verified_voter_posterior_equals_its_reputation():
    for acc in (0.4, 0.6, 0.9):
        agg = Aggregator(reliability=fixed({"p": acc}))
        decision = agg.decide([Vote("s1", "p", "no", VERIFIED)], choices=CHOICES)
        assert decision.answer == "no"
        assert decision.posterior["no"] == pytest.approx(acc)
    agg = Aggregator(reliability=fixed({"p": 0.7}))
    open_decision = agg.decide([Vote("s1", "p", "12.5", VERIFIED)])
    assert open_decision.posterior["12.5"] == pytest.approx(0.7)
    assert set(open_decision.posterior) == {"12.5", OTHER}


def test_copies_count_as_one_agent():
    rel = fixed({"p": 0.8, "q": 0.7})
    copies = lambda a, b: 1.0 if a.startswith("copy") and b.startswith("copy") else 0.0  # noqa: E731
    agg = Aggregator(reliability=rel, correlation=copies)
    one = agg.decide([Vote("copy1", "p", "yes", VERIFIED), Vote("x", "q", "no", VERIFIED)], choices=CHOICES)
    many = agg.decide([Vote(f"copy{i}", "p", "yes", VERIFIED) for i in range(5)]
                      + [Vote("x", "q", "no", VERIFIED)], choices=CHOICES)
    assert many.answer == one.answer
    assert many.posterior == pytest.approx(one.posterior)
    assert many.voters_n_eff == pytest.approx(one.voters_n_eff) == pytest.approx(2.0)


def test_without_the_correlation_discount_copies_outvote_an_independent_expert():
    rel = fixed({"weak": 0.6, "expert": 0.9})
    copies = lambda a, b: 1.0 if a.startswith("c") and b.startswith("c") else 0.0  # noqa: E731
    votes = [Vote(f"c{i}", "weak", "yes", VERIFIED) for i in range(4)] + [Vote("e", "expert", "no", VERIFIED)]
    assert Aggregator(reliability=rel, correlation=copies).decide(votes, choices=CHOICES).answer == "no"
    ablated = Aggregator(reliability=rel, correlation=copies, use_correlation=False)
    assert ablated.decide(votes, choices=CHOICES).answer == "yes"


def test_failed_verification_never_changes_the_outcome():
    agg = Aggregator(reliability=fixed({"p": 0.9, "q": 0.6}))
    base = [Vote("s1", "q", "no", VERIFIED)]
    with_failed = base + [Vote("s2", "p", "yes", FAILED), Vote("s3", "p", "maybe", FAILED)]
    a, b = agg.decide(base, choices=CHOICES), agg.decide(with_failed, choices=CHOICES)
    assert a.answer == b.answer and a.posterior == pytest.approx(b.posterior)
    excluded = [c for c in b.contributions if c.get("excluded") == "failed_verification"]
    assert len(excluded) == 2


def test_unverified_claims_carry_less_weight_than_verified():
    agg = Aggregator(reliability=fixed({"p": 0.8}))
    verified = agg.decide([Vote("s1", "p", "yes", VERIFIED)], choices=CHOICES).posterior["yes"]
    unverified = agg.decide([Vote("s1", "p", "yes", UNVERIFIED)], choices=CHOICES).posterior["yes"]
    assert 1 / 3 < unverified < verified


def test_unknown_persona_has_no_weight_and_cold_start_falls_back_to_discounted_plurality():
    ledger = ReputationLedger()
    agg = Aggregator(reliability=ledger.reliability("qa"))
    votes = [Vote("s1", "new1", "yes", VERIFIED), Vote("s2", "new2", "yes", VERIFIED),
             Vote("s3", "new3", "no", VERIFIED)]
    decision = agg.decide(votes, choices=CHOICES)
    assert all(c["weight"] == 0 for c in decision.contributions)
    assert decision.posterior["yes"] == pytest.approx(1 / 3)  # no earned evidence, no confidence
    assert decision.answer == "yes"  # forced choice still picks the better-supported answer


def test_earned_reputation_lets_a_proven_minority_win():
    ledger = ReputationLedger()
    for _ in range(40):
        ledger.record(persona="good", area="qa", channel=LABEL, success=True, author=EVALUATOR)
    for ok in [True] * 12 + [False] * 28:
        ledger.record(persona="bad", area="qa", channel=LABEL, success=ok, author=EVALUATOR)
    agg = Aggregator(reliability=ledger.reliability("qa"))
    votes = [Vote("g", "good", "maybe", VERIFIED), Vote("b1", "bad", "yes", VERIFIED),
             Vote("b2", "bad", "yes", VERIFIED)]
    assert agg.decide(votes, choices=CHOICES).answer == "maybe"
    assert Aggregator(reliability=ledger.reliability("qa"), use_reputation=False).decide(
        votes, choices=CHOICES).answer == "yes"


def test_abstain_mode_reasons():
    rel = fixed({"p": 0.55, "q": 0.95})
    abstain = Aggregator(reliability=rel, mode=ABSTAIN, tau=0.6)
    low = abstain.decide([Vote("s1", "p", "yes", VERIFIED)], choices=CHOICES)
    assert low.abstained and low.reason == "low_confidence" and low.answer is None
    sure = abstain.decide([Vote("s1", "q", "yes", VERIFIED)], choices=CHOICES)
    assert not sure.abstained and sure.answer == "yes"
    thin = Aggregator(reliability=rel, mode=ABSTAIN, tau=0.5, min_support=1.0)
    weak_support = thin.decide([Vote("s1", "q", "yes", UNVERIFIED)], choices=CHOICES)
    assert weak_support.abstained and weak_support.reason == "low_independent_support"
    tie = plain_vote()
    tie.mode = ABSTAIN
    tied = tie.decide([Vote("s1", "p", "yes"), Vote("s2", "p", "no")], choices=CHOICES)
    assert tied.abstained and tied.reason == "tie"


def test_forced_mode_always_answers_when_anyone_voted_and_breaks_ties_deterministically():
    votes = [Vote("s1", "p", "yes"), Vote("s2", "p", "no")]
    a = plain_vote().decide(votes, choices=CHOICES)
    b = plain_vote().decide(list(reversed(votes)), choices=CHOICES)
    assert a.answer == b.answer == "no" and a.reason == "argmax_tiebreak_canonical"
    empty = plain_vote().decide([Vote("s1", "p", None)], choices=CHOICES)
    assert empty.answer is None and empty.reason == "no_votes"


def test_order_independent_and_one_vote_per_seat():
    agg = Aggregator(reliability=fixed({"p": 0.7, "q": 0.8, "r": 0.6}), correlation=lambda a, b: 0.3)
    votes = [Vote("a", "p", "yes", VERIFIED), Vote("b", "q", "no", UNVERIFIED), Vote("c", "r", "yes")]
    results = {agg.decide(list(perm), choices=CHOICES).to_dict().__repr__() for perm in itertools.permutations(votes)}
    assert len(results) == 1
    with pytest.raises(ValueError):
        agg.decide([Vote("a", "p", "yes"), Vote("a", "q", "no")], choices=CHOICES)
    with pytest.raises(ValueError):
        agg.decide([Vote("a", "p", "perhaps")], choices=CHOICES)


def test_numeric_answers_group_by_value():
    assert canonical_answer("1,234.50") == canonical_answer("1234.5") == canonical_answer("$1234.500")
    assert canonical_answer("12.3456789") == canonical_answer("12.34568")
    assert canonical_answer("Yes ") == canonical_answer("yes")
    votes = [Vote("a", "p", "1,200"), Vote("b", "p", "1200.0"), Vote("c", "p", "1300")]
    decision = plain_vote().decide(votes)
    assert decision.answer == canonical_answer("1200")


def test_weights_are_clipped_and_never_inverted():
    agg = Aggregator(reliability=fixed({"liar": 0.05, "oracle": 0.999999}), max_weight=4.0)
    assert agg.weight("liar", 3) == 0.0
    assert agg.weight("oracle", 3) == 4.0
    assert math.isclose(agg.weight("unknown", 3), 0.0)


def test_decision_serialises_for_the_event_log():
    import json

    agg = Aggregator(reliability=fixed({"p": 0.7}))
    json.dumps(agg.decide([Vote("a", "p", "yes", VERIFIED), Vote("b", "p", None)], choices=CHOICES).to_dict())
    json.dumps(agg.describe())
