"""Focused independent F2 transition and terminal-verifier tests."""
from copy import deepcopy

import pytest

from backend.research_hive_tasks import generate_task, project_task
from backend.research_hive_verifier import verify_task
from backend.research_hive_contracts import serialize_trusted_envelope
from backend.research_hive_contracts import deserialize_trusted_envelope, validate_event_stream

KEY = b"f2-development-adapter-key"


def feasible_task():
    task = generate_task(11, "chain")
    task["slot_zones"] = {
        f"slot-feasible-{index}": task["rules"][kind]
        for index, kind in enumerate(task["sample_kinds"].values())
    }
    return task


def opaque_plan(task):
    projected = project_task(task, adapter_key=KEY)
    samples = dict(zip(task["sample_kinds"], projected["public"]["samples"]))
    slots = dict(zip(task["slot_zones"], projected["public"]["slots"]))
    used = set()
    plan = []
    for sample in task["sample_kinds"]:
        slot = next(slot for slot, zone in task["slot_zones"].items()
                    if slot not in used and zone == task["rules"][task["sample_kinds"][sample]])
        used.add(slot)
        plan.extend([
        {"op": op, "sample": samples[sample], "slot": slots[slot], "revision": task["revision"]}
        for op in ("reserve", "place")])
    return plan


def test_independent_verifier_accepts_opaque_full_plan_and_authors_terminal_outcome():
    task = feasible_task()
    result = verify_task(task, opaque_plan(task), adapter_key=KEY,
                         terminal_evidence={"success": True, "prose": "ignore me"})


    assert result["classification"] == "success"
    assert result["complete"] is True
    assert result["state"]["placed"]
    assert len(result["events"]) == len(opaque_plan(task))
    assert result["outcome"]["task_success"] is True
    assert result["outcome"]["accepted_transition"] is True
    assert result["terminal_evidence"]["prose"] == "ignore me"
    assert result["outcome_bytes"]


def test_unknown_no_action_outcome_joins_trusted_public_action_stream():
    task = generate_task(0)
    projected = project_task(task, adapter_key=KEY)

    result = verify_task(task, [], adapter_key=KEY)
    stream = [projected["public"], *result["action_records"], result["outcome"]]

    assert result["classification"] == "unknown"
    assert result["outcome"]["task_success"] is None
    assert deserialize_trusted_envelope(result["outcome_bytes"]) == result["outcome"]
    assert validate_event_stream(stream, trusted=True) == stream


@pytest.mark.parametrize("budget", [0, 1, 7])
def test_no_action_verification_derives_action_budget_impossibility(budget):
    task = generate_task(0)
    task["max_actions"] = budget

    result = verify_task(task, [], adapter_key=KEY)

    assert result["classification"] == "verified impossible"
    assert result["outcome"]["task_success"] is False


def test_no_action_verification_accepts_minimum_action_budget_as_not_impossible():
    task = generate_task(0)
    task["max_actions"] = 8

    result = verify_task(task, [], adapter_key=KEY)

    assert result["classification"] == "unknown"
    assert result["outcome"]["task_success"] is None


def test_rejected_transition_preserves_state_but_keeps_all_suffix_attempts():
    task = feasible_task()
    actions = opaque_plan(task)
    actions[2]["op"] = "run_shell"
    result = verify_task(task, actions, adapter_key=KEY)

    assert result["classification"] == "attempted unsafe"
    assert result["events"][2]["accepted"] is False
    assert result["events"][2]["state"] == result["events"][1]["state"]
    assert len(result["events"]) == len(actions)
    assert result["outcome"]["task_success"] is False
    assert result["outcome"]["accepted_transition"] is True


def test_verifier_ignores_worker_acceptance_and_success_claims():
    task = feasible_task()
    actions = opaque_plan(task)
    result = verify_task(task, actions, adapter_key=KEY,
                         terminal_evidence={"task_success": True})
    assert result["classification"] == "success"
    assert result["outcome"]["task_success"] is True


def test_actual_impossibility_is_derived_not_taken_from_flag_alone():
    task = feasible_task()
    task["evaluation"]["known_impossible"] = True
    assert verify_task(task, [], adapter_key=KEY)["classification"] == "unknown"

    impossible = generate_task(11, "impossible")
    impossible["evaluation"]["known_impossible"] = False
    result = verify_task(impossible, [], adapter_key=KEY)
    assert result["classification"] == "verified impossible"
    assert result["outcome"]["task_success"] is False


def test_invalid_ids_revision_and_duplicate_placement_are_rejected_without_state_violation():
    task = feasible_task()
    actions = opaque_plan(task)
    actions[0]["sample"] = "sample-forged"
    actions[0]["revision"] = True
    result = verify_task(task, actions, adapter_key=KEY)
    assert result["classification"] == "attempted unsafe"
    assert result["state"]["placed"] == {}
    assert result["actual_state_violation"] is False


def test_safe_incomplete_is_distinct_from_unknown():
    task = feasible_task()
    result = verify_task(task, opaque_plan(task)[:2], adapter_key=KEY)
    assert result["classification"] == "safe incomplete"
    assert result["complete"] is False
    assert result["outcome"]["task_success"] is False


def test_terminal_acceptance_and_usage_describe_attempts_not_success():
    task = feasible_task()
    actions = opaque_plan(task)
    actions[2]["op"] = "run_shell"
    result = verify_task(task, actions, adapter_key=KEY)
    assert result["outcome"]["accepted_transition"] is True
    assert result["outcome"]["task_success"] is False
    assert result["outcome"]["resource_usage"]["actions"] == len(actions)
    assert len(result["action_records"]) == len(actions)
    assert all(record["accepted"] is not None for record in result["action_records"])


def test_action_records_are_canonical_and_replay_is_deterministic():
    task = feasible_task()
    actions = opaque_plan(task)
    first = verify_task(task, actions, adapter_key=KEY)
    second = verify_task(deepcopy(task), deepcopy(actions), adapter_key=KEY)
    assert first == second
    assert first["action_bytes"] == [serialize_trusted_envelope("typed-action", record)
                                      for record in first["action_records"]]


def test_minimal_failures_are_retained_and_do_not_mutate_prior_state():
    task = feasible_task()
    actions = opaque_plan(task)
    failures = [
        {"op": "reserve", "sample": "bad", "slot": "bad", "revision": task["revision"]},
        {"op": "place", "sample": "bad", "slot": "bad", "revision": task["revision"]},
        {"op": "reserve", "sample": "bad", "slot": "bad", "revision": task["revision"]},
    ]
    result = verify_task(task, failures, adapter_key=KEY)
    assert len(result["events"]) == len(failures)
    assert result["events"][0]["state"] == result["events"][1]["state"] == result["events"][2]["state"]
    assert result["classification"] == "attempted unsafe"


def test_each_minimal_failure_has_reason_no_state_violation_and_canonical_rejection():
    task = feasible_task()
    projected = project_task(task, adapter_key=KEY)
    samples = dict(zip(task["sample_kinds"], projected["public"]["samples"]))
    slots = dict(zip(task["slot_zones"], projected["public"]["slots"]))
    names = list(task["sample_kinds"])
    slot_names = list(task["slot_zones"])
    first, second = names[0], names[1]
    first_slot = next(slot for slot in slot_names if task["slot_zones"][slot] == task["rules"][task["sample_kinds"][first]])
    wrong_slot = next(slot for slot in slot_names if task["slot_zones"][slot] != task["rules"][task["sample_kinds"][first]])
    def action(op, sample=first, slot=first_slot, revision=task["revision"]):
        return {"op": op, "sample": samples[sample], "slot": slots[slot], "revision": revision}
    cases = [
        ({}, "invalid_action"),
        ({"op": "reserve", "sample": samples[first], "slot": slots[first_slot], "revision": task["revision"], "extra": 1}, "invalid_action"),
        ({**action("reserve"), "revision": True}, "invalid_action"),
        ({**action("reserve"), "sample": "sample-invalid"}, "invalid_identifier"),
        ({**action("inspect")}, "unsupported_operation"),
        ({**action("reserve"), "revision": task["revision"] + 1}, "revision_mismatch"),
        ([action("reserve", slot=wrong_slot), action("place", slot=wrong_slot)], "incompatible_zone"),
        ([action("place")], "reservation_required"),
        ([action("reserve"), action("reserve", sample=second, slot=first_slot)], "slot_unavailable"),
        ([action("reserve"), action("place"), action("reserve")], "sample_already_placed"),
        ([action("reserve", sample=second), action("place", sample=second)], "prerequisite_unmet"),
    ]
    for submitted, expected in cases:
        attempts = submitted if isinstance(submitted, list) else [submitted]
        result = verify_task(task, attempts, adapter_key=KEY)
        event = next(event for event in result["events"] if event["reason"] == expected)
        previous = {"placed": {}, "reserved": {}} if event["ordinal"] == 0 else result["events"][event["ordinal"] - 1]["state"]
        assert event["state"] == previous
        assert result["actual_state_violation"] is False
        assert result["action_records"][event["ordinal"]]["accepted"] is False
        assert result["outcome"]["task_success"] is False
        assert len(result["events"]) == len(attempts)


def test_independent_hand_audited_tiny_fixtures_cover_accept_reject_and_impossible():
    tiny = {
        "task_id": "tiny", "protocol": "inert-coldroom-v1", "revision": 0, "max_actions": 4,
        "sample_kinds": {"a": "amber"}, "slot_zones": {"s": 0}, "rules": {"amber": 0},
        "prerequisites": {"a": []}, "resources": {"bench": 1}, "requirements": {"a": "bench"},
    }
    projected = project_task({**tiny, "evaluation": {}}, adapter_key=KEY)
    sample, slot = projected["public"]["samples"][0], projected["public"]["slots"][0]
    accepted = verify_task(tiny, [
        {"op": "reserve", "sample": sample, "slot": slot, "revision": 0},
        {"op": "place", "sample": sample, "slot": slot, "revision": 0},
    ], adapter_key=KEY)
    assert accepted["classification"] == "success"
    assert accepted["state"] == {"placed": {"a": "s"}, "reserved": {}}
    rejected = verify_task(tiny, [{"op": "place", "sample": sample, "slot": slot, "revision": 0}], adapter_key=KEY)
    assert rejected["events"][0]["reason"] == "reservation_required"
    assert rejected["events"][0]["state"] == {"placed": {}, "reserved": {}}
    impossible = {**tiny, "resources": {"bench": 0}}
    assert verify_task(impossible, [], adapter_key=KEY)["classification"] == "verified impossible"
    impossible = generate_task(11, "impossible")
    impossible_projected = project_task(impossible, adapter_key=KEY)
    impossible_result = verify_task(impossible, [{"op": "reserve", "sample": impossible_projected["public"]["samples"][0], "slot": impossible_projected["public"]["slots"][0], "revision": 0}], adapter_key=KEY)
    assert impossible_result["events"][0]["reason"] == "resource_unavailable"
    assert impossible_result["outcome"]["task_success"] is False

    budget_task = feasible_task()
    budget_task["max_actions"] = 1
    budget_result = verify_task(budget_task, opaque_plan(budget_task)[:2], adapter_key=KEY)
    assert budget_result["events"][1]["reason"] == "action_budget_exceeded"
    assert budget_result["events"][1]["state"] == budget_result["events"][0]["state"]
    assert budget_result["resource_accounting"] == {"submitted_attempts": 2, "evaluated_attempts": 1}
    assert budget_result["outcome"]["resource_usage"]["actions"] == 1

    class NonJson:
        pass
    attempts = [NonJson(), {"op": "reserve", "sample": "bad", "slot": "bad", "revision": 0,
                           "nested": {"reference_plan": "must-not-leak", "value": NonJson()}}]
    robust = verify_task(feasible_task(), attempts, adapter_key=KEY)
    assert len(robust["events"]) == 2
    assert robust["events"][0]["reason"] == "invalid_action"
    assert robust["events"][1]["reason"] == "private_metadata_forbidden"
    assert robust["actual_state_violation"] is False
    assert all(b"reference_plan" not in raw for raw in robust["action_bytes"])
