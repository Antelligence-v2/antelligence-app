"""Focused F2 task-generator and C0 projection tests."""
import json

import pytest

from backend.research_hive_tasks import (
    compose_canonical_bytes,
    generate_task,
    held_out_manifest,
    project_task,
    reference_solve,
)
from backend.research_hive_verifier import verify_task
from backend.research_hive_contracts import (
    deserialize_envelope,
    serialize_envelope,
    validate_event_stream,
)


KEY = b"f2-development-adapter-key"


def test_bounded_family_has_distinct_graphs_changed_rule_and_private_impossibility():
    chain = generate_task(11, composition="chain")
    fork = generate_task(11, composition="fork")
    changed = generate_task(11, composition="chain", revision=1)
    impossible = generate_task(11, composition="impossible")

    assert chain["protocol"] == fork["protocol"] == "inert-coldroom-v1"
    assert chain["max_actions"] <= 12
    assert chain["prerequisites"] != fork["prerequisites"]
    assert chain["resources"] != fork["resources"]
    assert chain["rules"] != changed["rules"]
    assert impossible["evaluation"]["known_impossible"] is True
    assert impossible["evaluation"]["reason"]
    assert "reference_plan" in impossible["evaluation"]


def test_projection_uses_c0_canonical_bytes_and_keeps_private_facts_out():
    task = generate_task(11, composition="chain")
    produced = project_task(task, adapter_key=KEY)
    trace = produced["trace"]

    assert [event["kind"] for event in trace] == [
        "task-public", "role-observation", "role-observation", "role-observation",
        "role-observation", "evidence-reference", "typed-action", "outcome",
    ]
    assert validate_event_stream(trace) == trace
    wire = [serialize_envelope(event["kind"], event) for event in trace]
    assert [deserialize_envelope(raw) for raw in wire] == trace
    public_payload = wire[0]
    assert b"11" not in public_payload
    assert b"reference_plan" not in public_payload
    assert b"prerequisites" not in public_payload
    assert b"rules" not in public_payload
    assert produced["public"] == trace[0]


def test_paired_worlds_have_identical_public_and_queen_projection_but_different_protocol_facts():
    first = project_task(generate_task(11, composition="chain"), adapter_key=KEY)
    second = project_task(generate_task(29, composition="chain"), adapter_key=KEY)

    assert first["public"] == second["public"]
    queen = lambda result: next(e for e in result["trace"] if e.get("role") == "queen")
    assert queen(first) == queen(second)
    protocol = lambda result: next(e for e in result["trace"] if e.get("role") == "protocol")
    assert protocol(first) != protocol(second)
    assert first["action"]["action"] == second["action"]["action"]
    assert first["action"]["attempted"] is False


def test_projection_rejects_non_bytes_key_and_does_not_mutate_task():
    task = generate_task(11)
    snapshot = json.loads(json.dumps(task))
    with pytest.raises(ValueError, match="adapter bytes key"):
        project_task(task, adapter_key=b"short")
    assert task == snapshot


@pytest.mark.parametrize("composition", ["chain", "fork"])
def test_reference_solver_completes_every_development_family(composition):
    for seed in range(32):
        task = generate_task(seed, composition)
        solution = reference_solve(task, adapter_key=KEY)
        assert solution is not None
        assert verify_task(task, solution, adapter_key=KEY)["classification"] == "success"


@pytest.mark.parametrize("budget", [0, 1, 7])
def test_reference_solver_returns_no_plan_below_two_actions_per_sample(budget):
    task = generate_task(0)
    task["max_actions"] = budget

    assert reference_solve(task, adapter_key=KEY) is None


def test_reference_solver_returns_plan_at_two_actions_per_sample_boundary():
    task = generate_task(0)
    task["max_actions"] = 8

    solution = reference_solve(task, adapter_key=KEY)

    assert solution is not None
    assert len(solution) == 8


def test_model_free_composer_uses_only_canonical_c0_bytes():
    task = generate_task(17, "fork")
    projected = project_task(task, adapter_key=KEY)
    actions = compose_canonical_bytes(projected["wire"])
    assert verify_task(task, actions, adapter_key=KEY)["classification"] == "success"
    assert all("reference_plan" not in str(action) for action in actions)


def test_development_fixture_marking_is_in_role_wire_and_held_out_manifest_is_structural_only():
    task = generate_task(3, "chain")
    assert "fixture_split" not in task
    manifest = held_out_manifest()
    assert manifest["family"] == "inert-coldroom-v1"
    assert manifest["reservations"]
    assert not any(name in str(manifest) for name in ("seed", "rules", "solution", "answer_key"))
    projected = project_task(task, adapter_key=KEY)
    queen = next(event for event in projected["trace"] if event.get("role") == "queen")
    assert queen["observation"]["fixture_split"] == "development"
    assert b"fixture_split" in projected["wire"][1]
    assert b"held_out" not in b"".join(projected["wire"])


def test_paired_worlds_keep_complete_queen_bytes_but_change_composed_plan_and_cross_use_fails():
    first = project_task(generate_task(0, "chain"), adapter_key=KEY)
    second = project_task(generate_task(1, "chain"), adapter_key=KEY)
    assert first["public"] == second["public"]
    public_bytes = lambda result: [raw for raw in result["wire"] if b'"kind":"task-public"' in raw]
    queen_bytes = lambda result: [raw for raw in result["wire"] if b'"role":"queen"' in raw]
    assert public_bytes(first) == public_bytes(second)
    assert queen_bytes(first) == queen_bytes(second)
    first_plan = compose_canonical_bytes(first["wire"])
    second_plan = compose_canonical_bytes(second["wire"])
    assert first_plan != second_plan
    cross = verify_task(generate_task(1, "chain"), first_plan, adapter_key=KEY)
    assert cross["classification"] == "attempted unsafe"
    assert any(event["reason"] == "incompatible_zone" for event in cross["events"])


def test_composer_fails_closed_for_zero_projected_capacity_and_wrong_role_shape():
    projected = project_task(generate_task(11, "chain"), adapter_key=KEY)
    events = [deserialize_envelope(raw) for raw in projected["wire"]]
    logistics = next(event for event in events if event.get("role") == "logistics")
    logistics["observation"]["resources"]["bench"] = 0
    logistics["event_id"] = "pending"
    logistics["event_id"] = __import__("backend.research_hive_contracts", fromlist=["_event_id"])._event_id(logistics)
    zero = [serialize_envelope(event["kind"], event) for event in events]
    with pytest.raises(ValueError, match="zero capacity"):
        compose_canonical_bytes(zero)
    queen = next(event for event in events if event.get("role") == "queen")
    del queen["observation"]["fixture_split"]
    queen["event_id"] = __import__("backend.research_hive_contracts", fromlist=["_event_id"])._event_id(queen)
    malformed = [serialize_envelope(event["kind"], event) for event in events]
    with pytest.raises(ValueError, match="exact shape"):
        compose_canonical_bytes(malformed)


def test_identifier_and_input_order_permutation_preserves_semantics():
    import copy
    original = generate_task(11, "chain")
    renamed = copy.deepcopy(original)
    sample_map = {name: f"renamed-sample-{index}" for index, name in enumerate(reversed(list(original["sample_kinds"])))}
    slot_map = {name: f"renamed-slot-{index}" for index, name in enumerate(reversed(list(original["slot_zones"])))}
    renamed["sample_kinds"] = {sample_map[k]: v for k, v in reversed(list(original["sample_kinds"].items()))}
    renamed["slot_zones"] = {slot_map[k]: v for k, v in reversed(list(original["slot_zones"].items()))}
    renamed["prerequisites"] = {sample_map[k]: [sample_map[p] for p in parents] for k, parents in reversed(list(original["prerequisites"].items()))}
    renamed["requirements"] = {sample_map[k]: v for k, v in reversed(list(original["requirements"].items()))}
    left = project_task(original, adapter_key=KEY)
    right = project_task(renamed, adapter_key=KEY)
    left_result = verify_task(original, compose_canonical_bytes(left["wire"]), adapter_key=KEY)
    right_result = verify_task(renamed, compose_canonical_bytes(right["wire"]), adapter_key=KEY)
    assert (left_result["classification"], left_result["complete"], len(left_result["events"]), left_result["state"].keys()) == ("success", True, 8, right_result["state"].keys())
    assert right_result["classification"] == left_result["classification"]
    assert right_result["complete"] == left_result["complete"]
    assert len(right_result["events"]) == len(left_result["events"])
