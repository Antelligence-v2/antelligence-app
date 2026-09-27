import pytest

from antelligence.kernel import memory as m
from antelligence.kernel.memory import (
    DependencyError,
    EvidenceMemory,
    EvidenceRecorder,
    ScopedRecall,
    StaleError,
    StatusError,
    TrustError,
)
from antelligence.kernel.signal import Signal
from antelligence.kernel.types import Intent, Outcome

S = "run:arm"


def claim(mem, author="a0", subject="food:1,1", body=None, deps=(), tick=1, scope=S):
    return mem.propose(scope=scope, kind=m.CLAIM, author=author, subject=subject,
                       body=body or {"food": True}, depends_on=deps, tick=tick)


def test_claim_admitted_immediately_with_single_confirmation():
    mem = EvidenceMemory()
    record = claim(mem)
    assert record.status == m.ADMITTED and record.usable
    assert [r.id for r in mem.recall(S)] == [record.id]


def test_confirmations_require_distinct_authors():
    mem = EvidenceMemory(min_confirmations=2)
    first = claim(mem, author="a0")
    assert first.status == m.CANDIDATE and mem.recall(S) == []
    assert claim(mem, author="a0").id == first.id, "same author re-proposing is idempotent"
    assert mem.get(first.id).status == m.CANDIDATE
    second = claim(mem, author="a1")
    assert mem.get(first.id).status == m.ADMITTED and second.status == m.ADMITTED
    assert len(mem.recall(S)) == 1, "recall deduplicates identical content"


def test_different_content_does_not_confirm():
    mem = EvidenceMemory(min_confirmations=2)
    claim(mem, author="a0", body={"food": True})
    claim(mem, author="a1", body={"food": False})
    assert mem.recall(S) == []


def test_only_authorities_write_outcomes():
    mem = EvidenceMemory()
    with pytest.raises(TrustError):
        mem.propose(scope=S, kind=m.OUTCOME, author="a0", subject="x", body={"done": True}, tick=1)
    record = mem.propose(scope=S, kind=m.OUTCOME, author=m.WORLD, subject="x", body={"done": True}, tick=1)
    assert record.status == m.ADMITTED


def test_source_replacement_invalidates_and_cascades():
    mem = EvidenceMemory()
    base = claim(mem, subject="food:1,1")
    procedure = mem.propose(scope=S, kind=m.PROCEDURE, author="a1", subject="plan:1",
                            body={"go": [1, 1]}, depends_on=[base.id], tick=2)
    grandchild = mem.propose(scope=S, kind=m.PROCEDURE, author="a2", subject="plan:2",
                             body={"then": "collect"}, depends_on=[procedure.id], tick=3)
    unrelated = claim(mem, subject="food:5,5")
    changed = mem.replace_source(S, "food:1,1", tick=4)
    assert changed == [base.id, procedure.id, grandchild.id]
    assert mem.get(procedure.id).reason == "dependency_invalidated"
    assert [r.id for r in mem.recall(S)] == [unrelated.id]
    assert mem.subject_rev(S, "food:1,1") == 1


def test_stale_proposals_are_refused():
    mem = EvidenceMemory()
    mem.replace_source(S, "food:1,1", tick=1)
    with pytest.raises(StaleError):
        mem.propose(scope=S, kind=m.CLAIM, author="a0", subject="food:1,1", body={}, subject_rev=0, tick=2)
    with pytest.raises(StaleError):
        mem.propose(scope=S, kind=m.CLAIM, author="a0", subject="food:1,1", body={}, subject_rev=5, tick=2)
    with pytest.raises(StaleError):
        mem.replace_source(S, "food:1,1", tick=3, new_rev=1)
    assert claim(mem, subject="food:1,1").subject_rev == 1


def test_dependencies_must_exist_be_admitted_and_share_scope():
    mem = EvidenceMemory(min_confirmations=2)
    with pytest.raises(DependencyError):
        claim(mem, deps=["nope"])
    candidate = claim(mem, subject="a")
    with pytest.raises(DependencyError, match="candidate"):
        claim(mem, subject="b", deps=[candidate.id])
    other = EvidenceMemory()
    foreign = claim(other, scope="run:other")
    admitted = claim(other, scope=S, subject="z")
    with pytest.raises(DependencyError, match="another scope"):
        claim(other, scope=S, subject="y", deps=[foreign.id])
    assert claim(other, scope=S, subject="y", deps=[admitted.id]).status == m.ADMITTED


def test_scopes_are_isolated_in_recall():
    mem = EvidenceMemory()
    claim(mem, scope="run:A")
    assert mem.recall("run:B") == []


def test_contradiction_removes_both_and_blocks_dependents_until_resolved():
    mem = EvidenceMemory()
    yes = claim(mem, author="a0", body={"food": True})
    no = claim(mem, author="a1", body={"food": False})
    child = mem.propose(scope=S, kind=m.PROCEDURE, author="a2", subject="plan", body={}, depends_on=[yes.id], tick=2)
    cid = mem.contradict(yes.id, no.id, author="a3", tick=3)
    assert {mem.get(yes.id).status, mem.get(no.id).status} == {m.CONTRADICTED}
    assert mem.get(child.id).status == m.INVALIDATED
    assert mem.recall(S) == []
    with pytest.raises(TrustError):
        mem.resolve(cid, winner=yes.id, author="a0", tick=4)
    winner = mem.resolve(cid, winner=yes.id, author=m.VERIFIER, tick=4)
    assert winner.status == m.ADMITTED and mem.get(no.id).status == m.INVALIDATED
    with pytest.raises(StatusError):
        mem.resolve(cid, winner=yes.id, author=m.VERIFIER, tick=5)


def test_resolution_does_not_revive_a_stale_winner():
    mem = EvidenceMemory()
    yes, no = claim(mem, author="a0", body={"v": 1}), claim(mem, author="a1", body={"v": 2})
    cid = mem.contradict(yes.id, no.id, author="a2", tick=2)
    mem.replace_source(S, "food:1,1", tick=3)
    assert mem.resolve(cid, winner=yes.id, author=m.WORLD, tick=4).status == m.INVALIDATED


def test_manual_transitions_and_guards():
    mem = EvidenceMemory(min_confirmations=3)
    record = claim(mem)
    assert mem.admit(record.id, tick=2).status == m.ADMITTED
    with pytest.raises(StatusError):
        mem.admit(record.id, tick=3)
    other = claim(mem, subject="q")
    assert mem.reject(other.id, tick=2, reason="spam").status == m.REJECTED
    stale = claim(mem, subject="s")
    mem.replace_source(S, "s", tick=3)
    with pytest.raises(StatusError):
        mem.admit(stale.id, tick=4)


def test_transitions_are_drained_in_order():
    mem = EvidenceMemory()
    record = claim(mem)
    mem.invalidate(record.id, tick=2, reason="manual")
    steps = [(t["from"], t["to"]) for t in mem.drain_transitions()]
    assert steps == [(None, m.CANDIDATE), (m.CANDIDATE, m.ADMITTED), (m.ADMITTED, m.INVALIDATED)]
    assert mem.drain_transitions() == []


def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "mem.sqlite")
    mem = EvidenceMemory(path)
    record = claim(mem)
    mem.close()
    reopened = EvidenceMemory(path)
    assert reopened.get(record.id).status == m.ADMITTED


def test_scoped_recall_filters_by_selected_subjects():
    mem = EvidenceMemory()
    near, far = claim(mem, subject="food:1,1"), claim(mem, subject="food:9,9")
    reader = ScopedRecall(mem, select=lambda agent, obs: [f"food:{x},{y}" for x, y in obs["nearby"]])
    assert reader.recall_for("a0", S, 1, {"nearby": [[1, 1]]}) == (near,)
    assert ScopedRecall(mem).recall_for("a0", S, 1, {}) == (near, far)


def _signal(sender="a0", kind="found", pos=(1, 1), cites=()):
    return Signal(sender=sender, scope=S, kind=kind, emitted_at=1, revision=0, ttl=3, pos=pos, cites=cites)


def test_recorder_turns_signals_into_claims_and_outcomes_into_source_changes():
    mem = EvidenceMemory()
    recorder = EvidenceRecorder(mem, {"found": lambda s: f"food:{int(s.pos[0])},{int(s.pos[1])}"})
    transitions = recorder.on_signal(_signal(), tick=1)
    assert [t["to"] for t in transitions] == [m.CANDIDATE, m.ADMITTED]
    assert recorder.on_signal(_signal(kind="alarm"), tick=1) == []
    outcome = Outcome(True, effects={"subjects_changed": ["food:1,1"],
                                     "facts": [{"subject": "food:1,1", "body": {"gone": True}}]})
    transitions = recorder.on_outcome(S, "a1", Intent("collect"), outcome, tick=2)
    assert [t["to"] for t in transitions] == [m.INVALIDATED, m.CANDIDATE, m.ADMITTED]
    [fact] = mem.recall(S)
    assert fact.kind == m.OUTCOME and fact.author == m.WORLD and fact.body == {"gone": True}


def test_recorder_ignores_rejected_outcomes():
    mem = EvidenceMemory()
    recorder = EvidenceRecorder(mem, {"found": lambda s: "food:1,1"})
    rejected = Outcome(False, "no", effects={"subjects_changed": ["food:1,1"]})
    assert recorder.on_outcome(S, "a0", Intent("collect"), rejected, 1) == []
    assert mem.subject_rev(S, "food:1,1") == 0


def test_recorder_logs_refusal_when_a_cited_record_is_no_longer_admitted():
    mem = EvidenceMemory()
    recorder = EvidenceRecorder(mem, {"found": lambda s: "food:2,2"})
    base = claim(mem, subject="food:1,1")
    mem.invalidate(base.id, tick=2, reason="gone")
    mem.drain_transitions()
    transitions = recorder.on_signal(_signal(pos=(2, 2), cites=(base.id,)), tick=3)
    assert len(transitions) == 1
    assert transitions[0]["to"] == m.REJECTED and "DependencyError" in transitions[0]["reason"]
    assert mem.recall(S) == []
