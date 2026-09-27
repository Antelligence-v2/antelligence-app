from antelligence.kernel.admission import AdmissionPolicy
from antelligence.kernel.signal import Signal

S = "run:arm"


def sig(sender="a0", kind="found", t=2, ttl=3, pos=(0, 0), topic=None, parents=(), cites=(), payload=None, scope=S):
    return Signal(sender=sender, scope=scope, kind=kind, emitted_at=t, revision=0, ttl=ttl,
                  pos=None if topic else pos, topic=topic, parent_ids=parents, cites=cites, payload=payload or {})


def test_default_policy_admits_plain_signals():
    assert AdmissionPolicy().check(sig(), 2) is None


def test_kind_allowlist_and_payload_schema():
    policy = AdmissionPolicy(kinds={"found": lambda p: None if "cells" in p else "missing_cells", "alarm": None})
    assert policy.check(sig(kind="recruit"), 2) == "kind_not_allowed"
    assert policy.check(sig(), 2) == "bad_payload:missing_cells"
    assert policy.check(sig(payload={"cells": 3}), 2) is None
    assert policy.check(sig(kind="alarm"), 2) is None


def test_ttl_bound():
    assert AdmissionPolicy(max_ttl=2).check(sig(ttl=3), 2) == "ttl_too_long"


def test_causality_requires_known_earlier_same_scope_parents():
    policy = AdmissionPolicy()
    parent = sig(t=1)
    assert policy.check(sig(parents=("ghost",)), 2) == "unknown_parent"
    assert policy.check(parent, 1) is None
    assert policy.check(sig(sender="a1", t=1, parents=(parent.id,)), 1) == "parent_not_earlier"
    assert policy.check(sig(sender="a1", t=2, parents=(parent.id,)), 2) is None
    assert policy.check(sig(sender="a2", t=2, parents=(parent.id,), scope="run:other"), 2) == "parent_out_of_scope"


def test_rejected_signals_cannot_become_parents():
    policy = AdmissionPolicy(max_ttl=1)
    rejected = sig(ttl=5, t=1)
    assert policy.check(rejected, 1) == "ttl_too_long"
    assert policy.check(sig(sender="a1", ttl=1, parents=(rejected.id,)), 2) == "unknown_parent"


def test_citations_need_a_resolver_and_usable_records():
    assert AdmissionPolicy().check(sig(cites=("r1",)), 2) == "citations_unverifiable"
    policy = AdmissionPolicy(cite_resolver=lambda rid: rid == "good")
    assert policy.check(sig(cites=("good", "bad")), 2) == "citation_not_usable"
    assert policy.check(sig(cites=("good",)), 2) is None


def test_sender_budget_resets_each_tick():
    policy = AdmissionPolicy(max_per_sender_per_tick=2)
    assert [policy.check(sig(pos=(i, 0)), 2) for i in range(3)] == [None, None, "sender_budget_exceeded"]
    assert policy.check(sig(sender="a1"), 2) is None
    assert policy.check(sig(pos=(9, 9), t=3), 3) is None


def test_topic_and_run_budgets():
    policy = AdmissionPolicy(max_per_topic_per_tick=1, max_total=3)
    assert policy.check(sig(topic="q1"), 2) is None
    assert policy.check(sig(sender="a1", topic="q1"), 2) == "topic_budget_exceeded"
    assert policy.check(sig(sender="a1", topic="q2"), 2) is None
    assert policy.check(sig(sender="a2", pos=(1, 1)), 2) is None
    assert policy.check(sig(sender="a3", pos=(2, 2)), 2) == "run_budget_exceeded"
    assert policy.check(sig(sender="a3", pos=(2, 2), scope="run:other"), 2) is None
