"""F2 bounded inert-coldroom task family and C0-owned projections.

The generator/evaluation fields are private application data. ``project_task`` is
an honest data projection, not OS isolation: consumers receive only canonical C0
role/public envelopes and cannot infer the private evaluator state from IDs.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import itertools
import random
from typing import Any

from .research_hive_contracts import (
    CONTRACT_VERSION,
    _event_id,
    serialize_envelope,
    validate_event_stream,
)

PROTOCOL = "inert-coldroom-v1"
_COMPOSITIONS = {"chain", "fork", "impossible"}
_ROLES = ("queen", "assay", "protocol", "logistics")

# Held-out reservations contain graph shapes only: no seeds, rules, solutions,
# or answer keys are available to workers.
HELD_OUT_MANIFEST = {
    "family": PROTOCOL,
    "reservations": [
        {"name": "diamond-barrier", "graph_shape": "diamond", "resource_shape": "capacity-barrier"},
        {"name": "fork-join", "graph_shape": "fork-join", "resource_shape": "shared-capacity"},
    ],
}


def held_out_manifest() -> dict[str, Any]:
    return copy.deepcopy(HELD_OUT_MANIFEST)


def generate_task(seed: int, composition: str = "chain", revision: int = 0) -> dict[str, Any]:
    """Create one bounded task with a private, structurally varied graph."""
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must be a nonnegative 32-bit integer")
    if composition not in _COMPOSITIONS:
        raise ValueError("unsupported task composition")
    if type(revision) is not int or revision not in (0, 1):
        raise ValueError("revision must be 0 or 1")

    rng = random.Random((seed << 4) ^ revision)
    names = [f"sample-{i}" for i in range(4)]
    slots = [f"slot-{i}" for i in range(4)]
    kinds = ["amber", "teal", "violet", "amber"]
    rng.shuffle(kinds)

    if composition == "chain":
        prerequisites = {names[0]: [], names[1]: [names[0]], names[2]: [names[1]], names[3]: [names[2]]}
        resources = {"bench": 1, "sealed-tray": 1}
        requirements = {name: "bench" for name in names}
    elif composition == "fork":
        prerequisites = {names[0]: [], names[1]: [names[0]], names[2]: [names[0]], names[3]: [names[1], names[2]]}
        resources = {"bench": 2, "sealed-tray": 1}
        requirements = {names[0]: "bench", names[1]: "sealed-tray", names[2]: "sealed-tray", names[3]: "bench"}
    else:
        prerequisites = {names[0]: [], names[1]: [names[0]], names[2]: [names[1]], names[3]: [names[2]]}
        resources = {"bench": 1, "sealed-tray": 0}
        requirements = {name: "sealed-tray" for name in names}

    rules = {kind: (index + revision + rng.randrange(2)) % 4 for index, kind in enumerate(("amber", "teal", "violet"))}
    if revision == 1:
        rules["amber"] = (rules["amber"] + 1) % 4
    # Generate a compatible slot for every sample, including repeated kinds;
    # slot order remains randomized while normal fixtures are always feasible.
    zones = [rules[kind] for kind in kinds]
    rng.shuffle(zones)
    evaluation = {
        "known_impossible": composition == "impossible",
        "reason": "sealed-tray capacity is zero" if composition == "impossible" else "",
        "reference_plan": None if composition == "impossible" else "private-evaluator-plan",
    }
    return {
        "task_id": f"f2-development-{composition}-r{revision}",
        "protocol": PROTOCOL,
        "revision": revision,
        "max_actions": 12,
        "sample_kinds": dict(zip(names, kinds)),
        "slot_zones": dict(zip(slots, zones)),
        "rules": rules,
        "prerequisites": prerequisites,
        "resources": resources,
        "requirements": requirements,
        "evaluation": evaluation,
    }


def make_hive_task(seed: int, composition: str = "chain", revision: int = 0) -> dict[str, Any]:
    """Named alias for callers that distinguish F2 tasks from C0 tasks."""
    return generate_task(seed, composition, revision)


def _alias(key: bytes, prefix: str, value: str) -> str:
    return prefix + "-" + hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:16]


def project_task(task: dict[str, Any], *, adapter_key: bytes) -> dict[str, Any]:
    """Project evaluator state into strict C0 envelopes without old adapters."""
    if type(adapter_key) is not bytes or len(adapter_key) < 16:
        raise ValueError("explicit evaluator adapter bytes key required")
    if type(task) is not dict or task.get("protocol") != PROTOCOL:
        raise ValueError("invalid F2 task")
    samples = {name: _alias(adapter_key, "sample", name) for name in task["sample_kinds"]}
    slots = {name: _alias(adapter_key, "slot", name) for name in task["slot_zones"]}
    scope = {"protocol": PROTOCOL, "revision": task["revision"]}
    base = lambda kind, ordinal: {
        "version": CONTRACT_VERSION, "kind": kind, "event_id": "pending",
        "ordinal": ordinal, "scope": scope,
    }
    public = {**base("task-public", 0), "task_id": _alias(adapter_key, "worker-task", "f2-public"),
              "samples": list(samples.values()), "slots": list(slots.values()),
              "max_actions": task["max_actions"]}
    observations = {
        "queen": {"task_id": public["task_id"], "samples": list(samples.values()),
                  "slots": list(slots.values()), "goal": "place every inert vial safely",
                  "fixture_split": "development"},
        "assay": {"sample_kinds": {samples[k]: v for k, v in task["sample_kinds"].items()}},
        "protocol": {"allowed_zones": {kind: zone for kind, zone in task["rules"].items()},
                     "prerequisites": {samples[k]: [samples[p] for p in parents] for k, parents in task["prerequisites"].items()},
                     "requirements": {samples[k]: value for k, value in task["requirements"].items()}},
        "logistics": {"slot_zones": {slots[k]: v for k, v in task["slot_zones"].items()},
                      "capacity_per_slot": 1, "resources": copy.deepcopy(task["resources"])},
    }
    trace = [public]
    for ordinal, role in enumerate(_ROLES, 1):
        trace.append({**base("role-observation", ordinal), "role": role, "observation": observations[role]})
    evidence = {**base("evidence-reference", 5), "source": {"source_id": "f2-evaluator", "revision": f"r{task['revision']}", "applicability": "inert-coldroom-task", "dependencies": [PROTOCOL]}, "claim": "public task projection", "accepted": None}
    # This is only an unbound worker-action envelope template.  The projection
    # must not choose an evaluator-derived sample/slot candidate.
    action = {**base("typed-action", 6), "action": {"op": "reserve", "sample": "", "slot": ""}, "attempted": False, "accepted": None}
    outcome = {**base("outcome", 7), "disposition": "running", "scope_admitted": False, "accepted_transition": False, "task_success": None, "resource_budget": {"actions": task["max_actions"], "bytes": None, "seconds": None}, "resource_usage": {"actions": None, "bytes": None, "seconds": None}}
    trace = trace[:5] + [evidence, action, outcome]
    for event in trace:
        event["event_id"] = _event_id(event)
    validate_event_stream(trace)
    wire = [serialize_envelope(event["kind"], event) for event in trace]
    return {"public": public, "task_public": public, "trace": trace, "wire": wire, "action": action}


project_public = project_task


def reference_solve(task: dict[str, Any], *, adapter_key: bytes | None = None) -> list[dict[str, Any]] | None:
    """Find a complete plan by independent bounded enumeration.

    This is a full-information baseline, not a verifier replay: it searches
    topological sample orders and injective compatible slot assignments while
    applying the task's resource capacities directly.
    """
    samples = list(task["sample_kinds"])
    if task["max_actions"] < 2 * len(samples):
        return None
    slots = list(task["slot_zones"])
    compatible = {sample: [slot for slot in slots if task["slot_zones"][slot] == task["rules"][task["sample_kinds"][sample]]] for sample in samples}
    for order in itertools.permutations(samples):
        if any(parent not in order[:index] for index, sample in enumerate(order) for parent in task.get("prerequisites", {}).get(sample, [])):
            continue
        for chosen in itertools.product(*(compatible[sample] for sample in order)):
            if len(set(chosen)) != len(chosen):
                continue
            requirements = {task.get("requirements", {}).get(sample) for sample in order}
            if any(task.get("resources", {}).get(requirement, 0) <= 0 for requirement in requirements):
                continue
            plan = [
                {"op": op, "sample": sample, "slot": slot, "revision": task["revision"]}
                for sample, slot in zip(order, chosen) for op in ("reserve", "place")
            ]
            if adapter_key is not None:
                plan = [{**action, "sample": _alias(adapter_key, "sample", action["sample"]),
                         "slot": _alias(adapter_key, "slot", action["slot"])} for action in plan]
            return plan
    return None


def compose_canonical_bytes(wire: list[bytes]) -> list[dict[str, Any]]:
    """Compose a plan solely from projected C0 canonical role-observation bytes."""
    from .research_hive_contracts import deserialize_envelope, validate_event_stream

    events = [deserialize_envelope(item) for item in wire]
    validate_event_stream(events)
    roles = {event["role"]: event["observation"] for event in events if event["kind"] == "role-observation"}
    if set(roles) != set(_ROLES):
        raise ValueError("all projected role observations are required")
    expected_shapes = {
        "queen": {"task_id", "samples", "slots", "goal", "fixture_split"},
        "assay": {"sample_kinds"},
        "protocol": {"allowed_zones", "prerequisites", "requirements"},
        "logistics": {"slot_zones", "capacity_per_slot", "resources"},
    }
    if any(type(roles[role]) is not dict or set(roles[role]) != shape
           for role, shape in expected_shapes.items()):
        raise ValueError("role observations have an unsupported exact shape")
    if roles["queen"]["fixture_split"] != "development":
        raise ValueError("only development worker observations are accepted")
    kinds = roles["assay"]["sample_kinds"]
    zones = roles["logistics"]["slot_zones"]
    protocol = roles["protocol"]
    logistics = roles["logistics"]
    rules = protocol["allowed_zones"]
    prerequisites = protocol["prerequisites"]
    requirements = protocol["requirements"]
    resources = logistics["resources"]
    if type(logistics["capacity_per_slot"]) is not int or logistics["capacity_per_slot"] <= 0:
        raise ValueError("projected logistics capacity must be positive")
    if (set(requirements) != set(kinds) or
            any(requirement not in resources or type(resources[requirement]) is not int or resources[requirement] <= 0
                for requirement in requirements.values())):
        raise ValueError("projected resource requirements have zero capacity")
    order: list[str] = []
    while len(order) < len(kinds):
        available = [sample for sample in kinds if sample not in order and all(parent in order for parent in prerequisites.get(sample, []))]
        if not available:
            raise ValueError("projected observations contain a prerequisite cycle")
        order.extend(sorted(available))
    used: set[str] = set()
    actions: list[dict[str, Any]] = []
    revision = events[0]["scope"]["revision"]
    for sample in order:
        slot = next((candidate for candidate, zone in zones.items() if candidate not in used and zone == rules[kinds[sample]]), None)
        if slot is None:
            raise ValueError("projected observations have no compatible slot")
        used.add(slot)
        actions.extend({"op": op, "sample": sample, "slot": slot, "revision": revision} for op in ("reserve", "place"))
    return actions


compose_from_canonical_bytes = compose_canonical_bytes
