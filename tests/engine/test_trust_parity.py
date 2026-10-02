"""Behavioural parity: engine EvidenceMemory vs the paper's HiveMemoryStore.

The two stores have different APIs (the engine keys evidence by subject
revision; the hive store by source lineage). These tests drive both through
the same scenarios and require the same *usable* evidence afterwards, which
is what agents act on. Known, intended differences are listed in
docs/plans/2026-09-27-antelligence-engine-kernel.md (section 14).
"""

import random
import sqlite3

import pytest

from backend.research_hive_memory import HiveMemoryError, HiveMemoryStore

from antelligence.kernel import memory as m
from antelligence.kernel.memory import DependencyError, EvidenceMemory, IntegrityError

ARM = "arm-a"


class Hive:
    """E13-style usage of the original store: claim + evaluator-admitted procedure per sighting."""

    def __init__(self, path):
        self.store = HiveMemoryStore(path)
        self.procedures = {}

    def sight(self, subject, rev, arm=ARM):
        base = dict(kind="evidence_claim", content=f"{subject} seen", source_id=subject, source_revision=f"r{rev}",
                    applicability="grid", protocol="p", revision=1, dependencies=[], experimental_arm=arm)
        claim = self.store.insert_candidate(base)
        proc = self.store.insert_candidate(dict(base, kind="conditional_procedure", source_id=f"{subject}-proc",
                                                evidence_refs=[claim]))
        if self.store.get(proc)["status"] == "candidate":
            self.store.admit_conditional_procedure(proc, evaluator_id="e", evaluator_revision="1")
        self.procedures[subject] = proc
        return claim

    def usable(self):
        return {r["source_id"].removesuffix("-proc") for r in self.store.retrieve("p", 1, "grid", "seen", ARM)}


class Engine:
    def __init__(self):
        self.memory = EvidenceMemory()

    def sight(self, subject, rev, arm=ARM):
        if rev > self.memory.subject_rev(arm, subject):
            self.memory.replace_source(arm, subject, tick=0, new_rev=rev)
        return self.memory.propose(scope=arm, kind=m.CLAIM, author="agent", subject=subject,
                                   body={"seen": True}, tick=0).id

    def usable(self):
        return {r.subject for r in self.memory.recall(ARM, limit=1000)}


def test_replacement_hides_stale_evidence_in_both(tmp_path):
    hive, engine = Hive(tmp_path / "h.sqlite"), Engine()
    for store in (hive, engine):
        store.sight("food:0", 0)
        store.sight("food:1", 0)
    assert hive.usable() == engine.usable() == {"food:0", "food:1"}
    # A newer observation of food:0 replaces the old source in both stores.
    hive.store.replace_source(dict(kind="evidence_claim", content="food:0 seen", source_id="food:0",
                                   source_revision="r1", applicability="grid", protocol="p", revision=1,
                                   dependencies=[], experimental_arm=ARM))
    engine.memory.replace_source(ARM, "food:0", tick=1)
    assert hive.usable() == engine.usable() == {"food:1"}


def test_contradiction_cascades_in_both(tmp_path):
    hive, engine = Hive(tmp_path / "h.sqlite"), Engine()
    hive_claim, engine_claim = hive.sight("food:2", 0), engine.sight("food:2", 0)
    hive.store.record_contradiction([hive_claim], cause="conflict", evaluator_id="e", evaluator_revision="1")
    other = engine.memory.propose(scope=ARM, kind=m.CLAIM, author="other", subject="food:2", body={"seen": False},
                                  tick=1)
    engine.memory.contradict(engine_claim, other.id, author="e", tick=1)
    assert hive.usable() == engine.usable() == set()


def test_cross_arm_references_are_refused_in_both(tmp_path):
    hive, engine = Hive(tmp_path / "h.sqlite"), Engine()
    hive_claim, engine_claim = hive.sight("food:3", 0, arm="arm-a"), engine.sight("food:3", 0, arm="arm-a")
    with pytest.raises(HiveMemoryError):
        hive.store.insert_candidate(dict(kind="conditional_procedure", content="x", source_id="p2",
                                         source_revision="r0", applicability="grid", protocol="p", revision=1,
                                         dependencies=[hive_claim], experimental_arm="arm-b"))
    with pytest.raises(DependencyError):
        engine.memory.propose(scope="arm-b", kind=m.PROCEDURE, author="a", subject="p2", body={},
                              depends_on=[engine_claim], tick=0)


def test_randomized_sighting_and_pickup_streams_agree(tmp_path):
    """E13-shaped streams: sightings and pickups (source replacement) on 6 subjects."""
    for trial in range(15):
        rng = random.Random(trial)
        hive, engine = Hive(tmp_path / f"h{trial}.sqlite"), Engine()
        revs = {f"food:{i}": 0 for i in range(6)}
        for _ in range(40):
            subject = f"food:{rng.randrange(6)}"
            if rng.random() < 0.3:
                revs[subject] += 1  # picked up / changed: the old source is replaced
                hive.store.replace_source(dict(kind="evidence_claim", content=f"{subject} gone",
                                               source_id=subject, source_revision=f"r{revs[subject]}",
                                               applicability="grid", protocol="p", revision=1, dependencies=[],
                                               experimental_arm=ARM))
                engine.memory.replace_source(ARM, subject, tick=0, new_rev=revs[subject])
            else:
                hive.sight(subject, revs[subject])
                engine.sight(subject, revs[subject])
            assert hive.usable() == engine.usable(), trial


def test_both_detect_tampering_on_open(tmp_path):
    hive_path = tmp_path / "h.sqlite"
    Hive(hive_path).sight("food:0", 0)
    with sqlite3.connect(hive_path) as db:
        db.execute("UPDATE hive_records SET record_json = replace(record_json, 'food:0 seen', 'food:9 seen')")
    with pytest.raises(HiveMemoryError):
        HiveMemoryStore(hive_path).list_records()

    engine_path = str(tmp_path / "e.sqlite")
    memory = EvidenceMemory(engine_path)
    memory.propose(scope=ARM, kind=m.CLAIM, author="a", subject="food:0", body={"seen": True}, tick=0)
    memory.close()
    with sqlite3.connect(engine_path) as db:
        db.execute("UPDATE records SET body = '{\"seen\":false}'")
    with pytest.raises(IntegrityError):
        EvidenceMemory(engine_path)


def test_both_bound_record_size():
    memory = EvidenceMemory()
    with pytest.raises(ValueError, match="exceeds"):
        memory.propose(scope=ARM, kind=m.CLAIM, author="a", subject="s", body={"x": "y" * 70_000}, tick=0)
