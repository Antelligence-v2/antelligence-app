import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

from backend.research_hive_memory import (
    HiveMemoryError,
    HiveMemoryStore,
    STORE_VERSION,
    adapt_memory_query_bytes,
    consume_memory_result_bytes,
)
from backend.research_hive_contracts import serialize_envelope


def evidence(source="paper-1", revision="rev-1"):
    return {
        "kind": "evidence_claim",
        "content": {"claim": "reservation succeeds under the stated scope"},
        "source_id": source,
        "source_revision": revision,
        "applicability": "inert-coldroom-v1",
        "protocol": "inert-coldroom-v1",
        "revision": 1,
        "dependencies": [],
    }


def procedure(*, evidence_refs, status="admitted"):
    return {
        "kind": "conditional_procedure",
        "content": {"when": "slot is available", "steps": ["reserve", "place"]},
        "source_id": "worker-plan-1",
        "source_revision": "candidate-1",
        "applicability": "inert-coldroom-v1",
        "protocol": "inert-coldroom-v1",
        "revision": 1,
        "dependencies": [],
        "evidence_refs": evidence_refs,
        "status": status,
    }


def test_worker_candidate_is_stored_in_its_own_versioned_store_without_admission(tmp_path):
    path = tmp_path / "scratch" / "hive.sqlite3"
    store = HiveMemoryStore(path)
    record_id = store.insert_candidate(procedure(evidence_refs=[], status="admitted"))

    record = store.get(record_id)
    assert record["kind"] == "conditional_procedure"
    assert record["status"] == "candidate"
    assert store.list_admitted() == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM hive_metadata WHERE key='version'").fetchone() == (STORE_VERSION,)
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'").fetchone() is None


def test_evaluator_can_atomically_admit_only_evidence_backed_procedure(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    evidence_id = store.insert_candidate(evidence())
    candidate = procedure(evidence_refs=[evidence_id])
    candidate["dependencies"] = [evidence_id]
    procedure_id = store.insert_candidate(candidate)

    admitted = store.admit_conditional_procedure(
        procedure_id, evaluator_id="evaluator-1", evaluator_revision="eval-7"
    )

    assert admitted["status"] == "admitted"
    assert admitted["evaluator_id"] == "evaluator-1"
    assert store.get(procedure_id)["status"] == "admitted"


def test_failure_notes_are_retained_and_never_promoted(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    failure_id = store.insert_candidate({
        "kind": "failure_note",
        "content": {"failure": "incompatible zone"},
        "source_id": "worker-1",
        "source_revision": "run-2",
        "applicability": "inert-coldroom-v1",
        "protocol": "inert-coldroom-v1",
        "revision": 1,
        "dependencies": [],
    })
    candidate = procedure(evidence_refs=[failure_id])
    candidate["dependencies"] = [failure_id]
    procedure_id = store.insert_candidate(candidate)

    assert store.get(failure_id)["status"] == "retained"
    with pytest.raises(HiveMemoryError, match="evidence-backed"):
        store.admit_conditional_procedure(procedure_id, evaluator_id="evaluator-1", evaluator_revision="eval-1")
    assert store.get(procedure_id)["status"] == "candidate"


def test_duplicate_insert_is_idempotent_but_changed_content_supersedes_history(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    first = store.insert_candidate(evidence())
    assert store.insert_candidate(evidence()) == first

    changed = evidence()
    changed["content"]["claim"] = "different"
    successor = store.insert_candidate(changed)
    assert successor != first
    assert store.get(first)["status"] == "superseded"
    assert store.get(successor)["status"] == "retained"


def test_records_enforce_json_and_dependency_bounds(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    oversized = evidence()
    oversized["content"] = {"x": "a" * 65537}
    with pytest.raises(HiveMemoryError, match="record JSON"):
        store.insert_candidate(oversized)

    too_many = evidence()
    too_many["dependencies"] = [str(i) for i in range(129)]
    with pytest.raises(HiveMemoryError, match="dependencies"):
        store.insert_candidate(too_many)


def test_source_replacement_retains_history_and_invalidates_only_transitive_descendants(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    source = store.insert_candidate(evidence(source="paper-1"))
    child = dict(procedure(evidence_refs=[source], status="candidate"))
    child["dependencies"] = [source, source]
    child_id = store.insert_candidate(child)
    grandchild = dict(procedure(evidence_refs=[child_id], status="candidate"))
    grandchild["source_id"] = "worker-plan-2"
    grandchild_id = store.insert_candidate(grandchild)
    unrelated = store.insert_candidate(evidence(source="paper-2"))

    changed = evidence(source="paper-1")
    changed["content"]["claim"] = "changed claim"
    successor = store.replace_source(changed)

    assert successor != source
    assert store.get(source)["status"] == "superseded"
    assert "source replacement" in store.get(source)["supersession_cause"]
    assert store.get(child_id)["status"] == "invalidated"
    assert store.get(grandchild_id)["status"] == "invalidated"
    assert store.get(unrelated)["status"] == "retained"
    assert store.get(successor)["status"] == "retained"
    assert store.get(child_id)["dependencies"] == [source]


@pytest.mark.parametrize("path", ["replace_source", "insert_candidate"])
def test_changed_source_revision_supersedes_lineage_and_invalidates_descendants(tmp_path, path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    source_r1 = evidence(source="paper-lineage", revision="r1")
    source_r1["experimental_arm"] = "arm-a"
    source_id = store.insert_candidate(source_r1)

    child = dict(procedure(evidence_refs=[source_id], status="candidate"))
    child.update(source_id="lineage-child", experimental_arm="arm-a", dependencies=[source_id])
    child_id = store.insert_candidate(child)
    grandchild = dict(procedure(evidence_refs=[child_id], status="candidate"))
    grandchild.update(source_id="lineage-grandchild", experimental_arm="arm-a", dependencies=[child_id])
    grandchild_id = store.insert_candidate(grandchild)

    unrelated = store.insert_candidate(evidence(source="unrelated", revision="r1"))
    other_arm = evidence(source="paper-lineage", revision="r1")
    other_arm["experimental_arm"] = "arm-b"
    other_arm_id = store.insert_candidate(other_arm)
    other_scope = evidence(source="paper-lineage", revision="r1")
    other_scope.update(protocol="other-protocol", applicability="other-applicability")
    other_scope_id = store.insert_candidate(other_scope)

    source_r2 = dict(source_r1, source_revision="r2", content={"claim": "revised claim"})
    if path == "replace_source":
        successor_id = store.replace_source(source_r2)
    else:
        successor_id = store.insert_candidate(source_r2)

    assert successor_id != source_id
    assert store.get(source_id)["status"] == "superseded"
    assert store.get(child_id)["status"] == "invalidated"
    assert store.get(grandchild_id)["status"] == "invalidated"
    assert store.get(unrelated)["status"] == "retained"
    assert store.get(other_arm_id)["status"] == "retained"
    assert store.get(other_scope_id)["status"] == "retained"
    assert store.get(successor_id)["status"] == "retained"

    assert store.insert_candidate(source_r2) == successor_id
    assert store.get(source_id)["status"] == "superseded"
    assert store.get(successor_id)["status"] == "retained"


def test_missing_parent_and_cycle_fail_closed_for_admission(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    missing = store.insert_candidate(procedure(evidence_refs=["missing-parent"], status="candidate"))
    with pytest.raises(HiveMemoryError, match="dependency"):
        store.admit_conditional_procedure(missing, evaluator_id="e", evaluator_revision="r")

    first = store.insert_candidate(evidence(source="cycle-a"))
    second_record = evidence(source="cycle-b")
    second_record["dependencies"] = [first]
    second = store.insert_candidate(second_record)
    with pytest.raises(HiveMemoryError, match="cycle"):
        store.replace_source({**evidence(source="cycle-a"), "dependencies": [second], "content": {"claim": "cycle"}})


def test_transitive_missing_parent_blocks_admission(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    parent = evidence(source="parent")
    parent["dependencies"] = ["missing-grandparent"]
    parent_id = store.insert_candidate(parent)
    plan = procedure(evidence_refs=[parent_id], status="candidate")
    plan["dependencies"] = [parent_id]
    plan_id = store.insert_candidate(plan)

    with pytest.raises(HiveMemoryError, match="dependency"):
        store.admit_conditional_procedure(plan_id, evaluator_id="e", evaluator_revision="r")


def test_transitive_invalid_parent_blocks_admission(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    parent = evidence(source="parent")
    grandparent_id = store.insert_candidate(evidence(source="grandparent"))
    parent["dependencies"] = [grandparent_id]
    parent_id = store.insert_candidate(parent)
    plan = procedure(evidence_refs=[parent_id], status="candidate")
    plan["dependencies"] = [parent_id]
    plan_id = store.insert_candidate(plan)
    store.record_contradiction([grandparent_id], cause="invalid", evaluator_id="e", evaluator_revision="r")

    with pytest.raises(HiveMemoryError, match="invalidated|contradiction"):
        store.admit_conditional_procedure(plan_id, evaluator_id="e", evaluator_revision="r")


def test_legacy_admitted_record_with_broken_transitive_graph_is_not_retrievable(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    broken_evidence = evidence(source="broken-evidence")
    broken_evidence["dependencies"] = ["missing-legacy-parent"]
    evidence_id = store.insert_candidate(broken_evidence)
    plan = procedure(evidence_refs=[evidence_id])
    plan.update(source_id="broken-plan", dependencies=[evidence_id])
    plan_id = store.insert_candidate(plan)
    with sqlite3.connect(path) as db:
        value = json.loads(db.execute("SELECT record_json FROM hive_records WHERE record_id=?", (plan_id,)).fetchone()[0])
        value.update(status="admitted", evaluator_id="legacy", evaluator_revision="legacy-r1")
        db.execute(
            "UPDATE hive_records SET status='admitted', record_json=? WHERE record_id=?",
            (json.dumps(value, sort_keys=True, separators=(",", ":")), plan_id),
        )
        db.commit()

    assert store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "slot") == []


def test_unusable_legacy_record_does_not_block_unrelated_scoped_retrieval(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    broken_evidence = evidence(source="broken-evidence")
    broken_evidence.update(experimental_arm="arm-bad", dependencies=["missing-parent"])
    broken_id = store.insert_candidate(broken_evidence)
    broken_plan = procedure(evidence_refs=[broken_id])
    broken_plan.update(source_id="broken-plan", experimental_arm="arm-bad", dependencies=[broken_id])
    broken_plan_id = store.insert_candidate(broken_plan)
    with sqlite3.connect(path) as db:
        value = json.loads(db.execute("SELECT record_json FROM hive_records WHERE record_id=?", (broken_plan_id,)).fetchone()[0])
        value.update(status="admitted", evaluator_id="legacy", evaluator_revision="legacy-r1")
        db.execute(
            "UPDATE hive_records SET status='admitted', record_json=? WHERE record_id=?",
            (json.dumps(value, sort_keys=True, separators=(",", ":")), broken_plan_id),
        )

    good_evidence = evidence(source="good-evidence")
    good_evidence["experimental_arm"] = "arm-good"
    good_id = store.insert_candidate(good_evidence)
    good_plan = procedure(evidence_refs=[good_id])
    good_plan.update(source_id="good-plan", experimental_arm="arm-good", dependencies=[good_id])
    good_plan_id = store.insert_candidate(good_plan)
    store.admit_conditional_procedure(good_plan_id, evaluator_id="eval", evaluator_revision="r1")

    results = store.retrieve(
        "inert-coldroom-v1", 1, "inert-coldroom-v1", "slot", "arm-good"
    )
    assert [item["record_id"] for item in results] == [good_plan_id]


@pytest.mark.parametrize("field", ["protocol", "applicability", "query", "experimental_arm"])
def test_retrieval_rejects_oversized_scope_inputs(tmp_path, field):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    args = {"protocol": "protocol", "revision": 1, "applicability": "scope", "query": "query", "experimental_arm": "arm"}
    args[field] = "x" * 4097
    with pytest.raises(HiveMemoryError, match="invalid bounded memory query"):
        store.retrieve(**args)


def test_corruption_is_detected_before_mutating_operations(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    record_id = store.insert_candidate(evidence())
    with sqlite3.connect(path) as db:
        db.execute("UPDATE hive_records SET identity_json='{}' WHERE record_id=?", (record_id,))
        db.commit()
    replacement = evidence(source="replacement")
    for operation in (
        lambda: store.replace_source(replacement),
        lambda: store.record_contradiction([record_id], cause="bad", evaluator_id="e", evaluator_revision="r"),
        lambda: store.admit_conditional_procedure(record_id, evaluator_id="e", evaluator_revision="r"),
    ):
        with pytest.raises(HiveMemoryError):
            operation()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT identity_json FROM hive_records WHERE record_id=?", (record_id,)).fetchone()[0] == "{}"


def test_credible_contradiction_is_preserved_and_invalidates_affected_procedure(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    left = store.insert_candidate(evidence(source="paper-left"))
    right_record = evidence(source="paper-right")
    right_record["content"]["claim"] = "contradictory claim"
    right = store.insert_candidate(right_record)
    plan = procedure(evidence_refs=[left, right], status="candidate")
    plan["dependencies"] = [left, right]
    plan_id = store.insert_candidate(plan)

    store.record_contradiction([left, right], cause="credible sources disagree", evaluator_id="eval-1", evaluator_revision="r1")

    assert store.get(left)["status"] == "contradicted"
    assert store.get(right)["status"] == "contradicted"
    assert store.get(left)["evaluator_id"] == "eval-1"
    assert store.get(right)["evaluator_revision"] == "r1"
    assert store.get(plan_id)["status"] == "invalidated"
    with pytest.raises(HiveMemoryError, match="contradiction"):
        store.admit_conditional_procedure(plan_id, evaluator_id="e", evaluator_revision="r")


@pytest.mark.parametrize("kwargs", [
    {},
    {"evaluator_id": "", "evaluator_revision": "r1"},
    {"evaluator_id": "eval-1", "evaluator_revision": ""},
    {"evaluator_id": "eval-1", "evaluator_revision": "r1", "cause": ""},
])
def test_contradiction_requires_evaluator_authority(tmp_path, kwargs):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    record_id = store.insert_candidate(evidence())
    with pytest.raises(HiveMemoryError):
        store.record_contradiction([record_id], cause=kwargs.pop("cause", "worker says contradiction"), **kwargs)


def test_admitted_record_identity_ignores_worker_authority_and_status(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    evidence_id = store.insert_candidate(evidence())
    candidate = procedure(evidence_refs=[evidence_id])
    candidate["dependencies"] = [evidence_id]
    record_id = store.insert_candidate(candidate)
    store.admit_conditional_procedure(record_id, evaluator_id="eval-1", evaluator_revision="r1")

    replay = dict(candidate, status="admitted", evaluator_id="worker-claim", evaluator_revision="worker-rev")
    assert store.insert_candidate(replay) == record_id
    assert store.get(record_id)["status"] == "admitted"
    assert store.get(record_id)["evaluator_id"] == "eval-1"


def test_source_replacement_does_not_cross_arms(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    arm_a = evidence(source="paper-a")
    arm_a["experimental_arm"] = "arm-a"
    old_a = store.insert_candidate(arm_a)
    replacement_a = dict(arm_a, content={"claim": "new arm-a claim"})

    arm_b = evidence(source="paper-b")
    arm_b["experimental_arm"] = "arm-b"
    b_evidence = store.insert_candidate(arm_b)
    plan_b = procedure(evidence_refs=[b_evidence])
    plan_b.update(experimental_arm="arm-b", dependencies=[b_evidence])
    plan_b_id = store.insert_candidate(plan_b)
    store.admit_conditional_procedure(plan_b_id, evaluator_id="eval-1", evaluator_revision="r1")

    store.replace_source(replacement_a)
    assert store.get(old_a)["status"] == "superseded"
    assert store.get(plan_b_id)["status"] == "admitted"
    assert store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "slot", "arm-b")


def test_existing_cross_arm_reference_is_rejected_at_insertion(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    arm_a = evidence(source="paper-a")
    arm_a["experimental_arm"] = "arm-a"
    arm_a_id = store.insert_candidate(arm_a)
    cross_arm = procedure(evidence_refs=[arm_a_id])
    cross_arm.update(experimental_arm="arm-b", dependencies=[arm_a_id])
    with pytest.raises(HiveMemoryError, match="cross experimental arms"):
        store.insert_candidate(cross_arm)


def test_admitted_disagreeing_procedures_are_both_retrievable(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    evidence_id = store.insert_candidate(evidence())
    for source_id, step in (("worker-a", "reserve"), ("worker-b", "inspect")):
        plan = procedure(evidence_refs=[evidence_id])
        plan.update(source_id=source_id, content={"when": "slot", "steps": [step]}, dependencies=[evidence_id])
        plan_id = store.insert_candidate(plan)
        store.admit_conditional_procedure(plan_id, evaluator_id="eval-1", evaluator_revision="r1")
    results = store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "slot")
    assert {tuple(item["content"]["steps"]) for item in results} == {("reserve",), ("inspect",)}


@pytest.mark.parametrize("args, max_results", [
    (("", 1, "scope", "query", "arm-a"), 1),
    (("protocol", -1, "scope", "query", "arm-a"), 1),
    (("protocol", 1, "", "query", "arm-a"), 1),
    (("protocol", 1, "scope", "", "arm-a"), 1),
    (("protocol", 1, "scope", "query", ""), 1),
    (("protocol", 1, "scope", "query", "arm-a"), 0),
    (("protocol", 1, "scope", "query", "arm-a"), 9),
])
def test_retrieval_rejects_empty_or_out_of_bounds_inputs(tmp_path, args, max_results):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    with pytest.raises(HiveMemoryError, match="invalid bounded memory query"):
        store.retrieve(*args, max_results=max_results)


def test_retrieval_excludes_protocol_revision_applicability_and_arm_mismatches(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    evidence_id = store.insert_candidate(evidence())
    plan = procedure(evidence_refs=[evidence_id])
    plan["dependencies"] = [evidence_id]
    plan_id = store.insert_candidate(plan)
    store.admit_conditional_procedure(plan_id, evaluator_id="eval", evaluator_revision="r1")
    assert store.retrieve("wrong-protocol", 1, "inert-coldroom-v1", "slot") == []
    assert store.retrieve("inert-coldroom-v1", 2, "inert-coldroom-v1", "slot") == []
    assert store.retrieve("inert-coldroom-v1", 1, "wrong-applicability", "slot") == []
    assert store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "slot", "arm-b") == []


def test_canonical_adapter_useful_and_not_found_roundtrip_c0_bytes(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    evidence_id = store.insert_candidate(evidence())
    plan = procedure(evidence_refs=[evidence_id])
    plan["dependencies"] = [evidence_id]
    plan["content"]["lesson"] = "recheck before acting"
    plan_id = store.insert_candidate(plan)
    store.admit_conditional_procedure(plan_id, evaluator_id="eval", evaluator_revision="r1")
    query = {"version": "hive-contract-v1", "kind": "memory-query", "event_id": "q", "ordinal": 0,
             "scope": {"protocol": "inert-coldroom-v1", "revision": 1}, "query": "lesson"}
    useful = consume_memory_result_bytes(adapt_memory_query_bytes(
        store, serialize_envelope("memory-query", query), applicability="inert-coldroom-v1"))
    assert useful["found"] is True
    assert useful["result"]["external_state_recheck_required"] is True
    assert "evaluator_outcome" not in useful["result"]
    assert "task_success" not in useful["result"]
    assert "accepted_action" not in useful["result"]
    query["query"] = "absent"
    absent = consume_memory_result_bytes(adapt_memory_query_bytes(
        store, serialize_envelope("memory-query", query), applicability="inert-coldroom-v1"))
    assert absent["found"] is False
    assert absent["result"]["evidence"] == []


@pytest.mark.parametrize("corruption", ["metadata", "schema", "identity", "content"])
def test_corrupt_storage_fails_closed_without_results(tmp_path, corruption):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    record_id = store.insert_candidate(evidence())
    with sqlite3.connect(path) as db:
        if corruption == "metadata":
            db.execute("UPDATE hive_metadata SET value='bad-version' WHERE key='version'")
        elif corruption == "schema":
            db.execute("ALTER TABLE hive_records RENAME TO hive_records_old")
            db.execute("CREATE TABLE hive_records (record_id TEXT PRIMARY KEY)")
        elif corruption == "identity":
            db.execute("UPDATE hive_records SET identity_json='{}' WHERE record_id=?", (record_id,))
        else:
            db.execute("UPDATE hive_records SET record_json='{}' WHERE record_id=?", (record_id,))
        db.commit()
    with pytest.raises((HiveMemoryError, sqlite3.Error)):
        HiveMemoryStore(path).retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "claim")


def test_source_replacement_rolls_back_all_graph_mutations_on_failure(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    source = store.insert_candidate(evidence())
    child = dict(procedure(evidence_refs=[source], status="candidate"))
    child["dependencies"] = [source]
    child_id = store.insert_candidate(child)
    changed = evidence()
    changed["content"]["claim"] = "changed"

    with pytest.raises(RuntimeError, match="injected"):
        store.replace_source(changed, inject_failure="after-statuses")

    assert store.get(source)["status"] == "retained"
    assert store.get(child_id)["status"] == "candidate"
    assert store.list_records() == [store.get(source), store.get(child_id)]


def test_scoped_retrieval_is_bounded_deterministic_and_arm_isolated(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    ids = []
    for arm in ("arm-a", "arm-b"):
        ev = evidence(source=f"paper-{arm}")
        ev["experimental_arm"] = arm
        evidence_id = store.insert_candidate(ev)
        plan = procedure(evidence_refs=[evidence_id])
        plan.update(experimental_arm=arm, content={"when": "slot available", "steps": [f"use {arm}"]})
        plan["dependencies"] = [evidence_id]
        ids.append(store.insert_candidate(plan))
        store.admit_conditional_procedure(ids[-1], evaluator_id="eval", evaluator_revision="r1")
    assert [r["experimental_arm"] for r in store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "arm-a", "arm-a", max_results=8)] == ["arm-a"]
    results = store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "arm-a", "arm-a", max_results=8)
    assert len(results) <= 8
    assert [r["record_id"] for r in results] == sorted(r["record_id"] for r in results)


def test_canonical_memory_adapter_returns_evidence_only_and_recheck_signal(tmp_path):
    store = HiveMemoryStore(tmp_path / "hive.sqlite3")
    query = {"version": "hive-contract-v1", "kind": "memory-query", "event_id": "q", "ordinal": 0,
             "scope": {"protocol": "inert-coldroom-v1", "revision": 1}, "query": "slot"}
    raw = serialize_envelope("memory-query", query)
    result_raw = adapt_memory_query_bytes(store, raw, applicability="slot", experimental_arm="arm-a")
    result = consume_memory_result_bytes(result_raw)
    assert result["kind"] == "memory-result"
    assert result["result"]["evidence"] == []
    assert result["result"]["external_state_recheck_required"] is True
    assert "success" not in result["result"]


def test_corrupt_record_fails_closed(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    record_id = store.insert_candidate(evidence())
    with sqlite3.connect(path) as db:
        db.execute("UPDATE hive_records SET record_json=? WHERE record_id=?", ('{"kind":"evidence_claim"}', record_id))
        db.commit()
    with pytest.raises(HiveMemoryError):
        store.list_records()


def test_same_handle_metadata_corruption_fails_closed_for_reads_and_mutations_without_changes(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    record_id = store.insert_candidate(evidence())
    snapshot = sqlite3.connect(path).execute(
        "SELECT record_id, identity_json, record_json, kind, status, source_id, protocol, revision "
        "FROM hive_records ORDER BY rowid"
    ).fetchall()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE hive_metadata SET value='bad-version' WHERE key='version'")
        db.commit()

    operations = (
        lambda: store.get(record_id),
        lambda: store.list_records(),
        lambda: store.list_admitted(),
        lambda: store.retrieve("inert-coldroom-v1", 1, "inert-coldroom-v1", "claim"),
        lambda: store.insert_candidate(evidence(source="new-source")),
        lambda: store.replace_source(evidence(source="replacement")),
        lambda: store.record_contradiction([record_id], cause="bad", evaluator_id="e", evaluator_revision="r"),
    )
    for operation in operations:
        with pytest.raises(HiveMemoryError, match="unsupported hive memory store version"):
            operation()

    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT record_id, identity_json, record_json, kind, status, source_id, protocol, revision "
            "FROM hive_records ORDER BY rowid"
        ).fetchall() == snapshot
        assert db.execute("SELECT value FROM hive_metadata WHERE key='version'").fetchone() == ("bad-version",)


def test_fresh_process_recalls_canonical_query_bytes(tmp_path):
    path = tmp_path / "hive.sqlite3"
    store = HiveMemoryStore(path)
    evidence_id = store.insert_candidate(evidence())
    candidate = procedure(evidence_refs=[evidence_id])
    candidate["dependencies"] = [evidence_id]
    candidate["content"]["lesson"] = "reserve before placing"
    procedure_id = store.insert_candidate(candidate)
    store.admit_conditional_procedure(procedure_id, evaluator_id="eval", evaluator_revision="r1")
    script = """import sys
from backend.research_hive_memory import HiveMemoryStore, adapt_memory_query_bytes, consume_memory_result_bytes
from backend.research_hive_contracts import serialize_envelope
s = HiveMemoryStore(sys.argv[1])
q = {'version':'hive-contract-v1','kind':'memory-query','event_id':'q','ordinal':0,'scope':{'protocol':'inert-coldroom-v1','revision':1},'query':'reserve'}
r = consume_memory_result_bytes(adapt_memory_query_bytes(s, serialize_envelope('memory-query', q), applicability='inert-coldroom-v1'))
assert r['found'] and 'reserve before placing' in str(r['result']['evidence'])
print(r['result']['evidence'][0]['content']['lesson'])
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    output = subprocess.check_output([sys.executable, "-c", script, str(path)], cwd=Path(__file__).parents[1], env=env, text=True)
    assert output.strip() == "reserve before placing"
