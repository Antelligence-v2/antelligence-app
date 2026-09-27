"""C0 executable shared envelopes for the model-free coldroom.

The trusted evaluator helpers are an explicit in-process authority boundary;
they are not wire authentication.
"""
from __future__ import annotations
import hashlib, hmac, json
from typing import Any

CONTRACT_VERSION = "hive-contract-v1"
class ContractError(ValueError):
    """Malformed, unauthorized, or privately contaminated data."""

_SCOPE = {"protocol", "revision"}
_PRIVATE = {"seed", "ground_truth", "reference_plan", "rules", "answer_key", "private_metadata"}
_SCHEMAS: dict[str, dict[str, tuple[type, bool]]] = {
    "task-public": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "task_id": (str, False), "samples": (list, False), "slots": (list, False), "max_actions": (int, False)},
    "role-observation": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "role": (str, False), "observation": (dict, False)},
    "evidence-reference": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "source": (dict, False), "claim": (str, False), "accepted": (bool, True)},
    "memory-query": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "query": (str, False)},
    "memory-result": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "source": (dict, False), "result": (dict, False), "found": (bool, False)},
    "consultation": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "from_role": (str, False), "to_role": (str, False), "question": (str, False), "answer": (str, True)},
    "typed-action": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "action": (dict, False), "attempted": (bool, False), "accepted": (bool, True)},
    "checkpoint": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "resume_position": (str, True), "terminal": (bool, False)},
    "outcome": {"version": (str, False), "kind": (str, False), "event_id": (str, False), "ordinal": (int, False), "scope": (dict, False), "disposition": (str, False), "scope_admitted": (bool, False), "accepted_transition": (bool, False), "task_success": (bool, True), "resource_budget": (dict, False), "resource_usage": (dict, False)},
}

def _validate_json_tree(value: Any) -> None:
    if value is None or type(value) in {str, int, bool}: return
    if type(value) is list:
        for child in value: _validate_json_tree(child)
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value): raise ContractError("JSON object keys must be strings")
        for child in value.values(): _validate_json_tree(child)
        return
    raise ContractError("envelope values must be JSON-compatible primitives")

def _walk_private(value: Any) -> None:
    if isinstance(value, dict):
        if _PRIVATE.intersection(value): raise ContractError("private evaluator metadata is forbidden")
        for child in value.values(): _walk_private(child)
    elif isinstance(value, list):
        for child in value: _walk_private(child)

def _validate_source(source: Any) -> None:
    if (type(source) is not dict or set(source) != {"source_id", "revision", "applicability", "dependencies"}
        or any(type(source[k]) is not str or not source[k] for k in ("source_id", "revision", "applicability"))
        or type(source["dependencies"]) is not list or any(type(x) is not str or not x for x in source["dependencies"])):
        raise ContractError("source identity, revision, applicability, dependencies required")

def _validate_common(kind: str, envelope: dict[str, Any]) -> None:
    if type(kind) is not str or type(envelope) is not dict or kind not in _SCHEMAS: raise ContractError("unsupported envelope kind or shape")
    _validate_json_tree(envelope)
    schema = _SCHEMAS[kind]
    if set(envelope) != set(schema): raise ContractError("exact envelope fields required")
    if envelope["version"] != CONTRACT_VERSION or envelope["kind"] != kind: raise ContractError("unsupported version or kind")
    if type(envelope["event_id"]) is not str or not envelope["event_id"]: raise ContractError("event_id required")
    if type(envelope["ordinal"]) is not int or envelope["ordinal"] < 0: raise ContractError("ordinal must be nonnegative")
    scope = envelope["scope"]
    if (type(scope) is not dict or set(scope) != _SCOPE or type(scope["protocol"]) is not str or not scope["protocol"]
        or scope["protocol"] != "inert-coldroom-v1" or type(scope["revision"]) is not int or scope["revision"] < 0): raise ContractError("invalid scope")
    for field, (expected, nullable) in schema.items():
        value = envelope[field]
        if value is None and not nullable: raise ContractError(f"null forbidden for {field}")
        if value is not None and type(value) is not expected: raise ContractError(f"wrong type for {field}")
    _walk_private(envelope)
    if kind in {"evidence-reference", "memory-result"}: _validate_source(envelope["source"])
    if kind == "role-observation" and envelope["role"] not in {"queen", "assay", "protocol", "logistics"}: raise ContractError("unsupported coldroom role")
    if kind == "task-public" and envelope["max_actions"] < 0: raise ContractError("max_actions must be nonnegative")
    if kind == "typed-action":
        if envelope["accepted"] is True and not envelope["attempted"]: raise ContractError("accepted action must be attempted")
    if kind == "checkpoint":
        if envelope["terminal"] != (envelope["resume_position"] is None): raise ContractError("terminal checkpoint must have explicit null resume")
    if kind == "outcome":
        if envelope["disposition"] not in {"running", "accepted", "rejected", "abstained", "completed"}: raise ContractError("invalid terminal disposition")
        for name in ("resource_budget", "resource_usage"):
            values = envelope[name]
            if type(values) is not dict or set(values) != {"actions", "bytes", "seconds"} or any(v is not None and (type(v) is not int or v < 0) for v in values.values()): raise ContractError("resources must be nonnegative integers or null")
        for name, usage in envelope["resource_usage"].items():
            budget = envelope["resource_budget"][name]
            if budget is not None and usage is not None and usage > budget: raise ContractError("resource usage exceeds budget")
        running = envelope["disposition"] == "running"
        if running and (envelope["scope_admitted"] or envelope["accepted_transition"] or envelope["task_success"] is not None): raise ContractError("running outcome is undecided")
        if envelope["accepted_transition"] and not envelope["scope_admitted"]: raise ContractError("accepted transition requires admitted scope")
        if envelope["disposition"] in {"rejected", "abstained"} and envelope["task_success"] is True: raise ContractError("rejected or abstained outcome cannot succeed")
        if envelope["task_success"] is True and not envelope["accepted_transition"]: raise ContractError("success requires accepted transition")
        if envelope["disposition"] == "completed" and envelope["task_success"] is None: raise ContractError("completed outcome requires evaluator decision")

def validate_envelope(kind: str, envelope: dict[str, Any]) -> dict[str, Any]:
    _validate_common(kind, envelope)
    if kind == "evidence-reference" and envelope["accepted"] is not None: raise ContractError("worker cannot admit evidence")
    if kind == "typed-action" and envelope["accepted"] is not None: raise ContractError("worker cannot accept action")
    if kind == "outcome" and (envelope["scope_admitted"] or envelope["accepted_transition"] or envelope["task_success"] is not None or envelope["disposition"] != "running"): raise ContractError("worker cannot author outcome authority")
    return envelope

def validate_worker_envelope(kind: str, envelope: dict[str, Any]) -> dict[str, Any]:
    return validate_envelope(kind, envelope)

def validate_trusted_envelope(kind: str, envelope: dict[str, Any]) -> dict[str, Any]:
    """Validate evaluator-authoritative data at a trusted call boundary, not auth."""
    _validate_common(kind, envelope)
    return envelope

def _event_id(envelope: dict[str, Any]) -> str:
    content = {k: v for k, v in envelope.items() if k != "event_id"}
    return "evt-" + hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()[:24]

def _canonical(kind: str, envelope: dict[str, Any], trusted: bool) -> bytes:
    (validate_trusted_envelope if trusted else validate_worker_envelope)(kind, envelope)
    return (json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()

def serialize_envelope(kind: str, envelope: dict[str, Any]) -> bytes: return _canonical(kind, envelope, False)
def serialize_trusted_envelope(kind: str, envelope: dict[str, Any]) -> bytes: return _canonical(kind, envelope, True)

def _decode(raw: bytes, trusted: bool) -> dict[str, Any]:
    if type(raw) is not bytes: raise ContractError("consumer requires bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ContractError("invalid canonical JSON") from exc
    if type(value) is not dict or raw != (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(): raise ContractError("invalid canonical JSON")
    (validate_trusted_envelope if trusted else validate_worker_envelope)(value.get("kind"), value)
    return value

def deserialize_envelope(raw: bytes) -> dict[str, Any]: return _decode(raw, False)
def deserialize_trusted_envelope(raw: bytes) -> dict[str, Any]: return _decode(raw, True)

def validate_event_stream(envelopes: list[dict[str, Any]], *, trusted: bool = False) -> list[dict[str, Any]]:
    if type(envelopes) is not list: raise ContractError("event stream must be a list")
    seen, scope = set(), None
    for ordinal, envelope in enumerate(envelopes):
        if type(envelope) is not dict: raise ContractError("event stream members must be envelopes")
        (validate_trusted_envelope if trusted else validate_envelope)(envelope.get("kind"), envelope)
        if envelope["ordinal"] != ordinal: raise ContractError("event ordinals must be contiguous and ordered")
        if scope is None: scope = envelope["scope"]
        if envelope["scope"] != scope: raise ContractError("event stream scope mismatch")
        if envelope["event_id"] in seen or envelope["event_id"] != _event_id(envelope): raise ContractError("event ID is duplicate or content-tampered")
        seen.add(envelope["event_id"])
    return envelopes

def _base(kind: str, scope: dict[str, Any], ordinal: int = 0) -> dict[str, Any]:
    value = {"version": CONTRACT_VERSION, "kind": kind, "event_id": "pending", "ordinal": ordinal, "scope": scope}
    value["event_id"] = _event_id(value); return value

def _author(kind: str, envelope: dict[str, Any], ordinal: int, **updates: Any) -> dict[str, Any]:
    if type(ordinal) is not int or ordinal <= envelope["ordinal"]: raise ContractError("authority event ordinal must advance")
    value = {**envelope, **updates, "ordinal": ordinal, "event_id": "pending"}
    value["event_id"] = _event_id(value); validate_trusted_envelope(kind, value); return value

def evaluator_admit_evidence(envelope: dict[str, Any], *, accepted: bool, ordinal: int) -> dict[str, Any]: return _author("evidence-reference", envelope, ordinal, accepted=accepted)
def evaluator_record_action(envelope: dict[str, Any], *, accepted: bool, ordinal: int) -> dict[str, Any]: return _author("typed-action", envelope, ordinal, accepted=accepted)
def evaluator_record_outcome(envelope: dict[str, Any], *, disposition: str, scope_admitted: bool, accepted_transition: bool, task_success: bool | None, ordinal: int) -> dict[str, Any]: return _author("outcome", envelope, ordinal, disposition=disposition, scope_admitted=scope_admitted, accepted_transition=accepted_transition, task_success=task_success)

def _validate_adapter_inputs(task: Any, views: Any) -> None:
    task_fields = {"task_id", "protocol", "revision", "max_actions", "sample_kinds", "slot_zones", "rules"}
    if type(task) is not dict or set(task) != task_fields: raise ContractError("exact coldroom task shape required")
    if (type(task["task_id"]) is not str or not task["task_id"]
        or task["protocol"] != "inert-coldroom-v1" or type(task["revision"]) is not int or task["revision"] < 0
        or type(task["max_actions"]) is not int or task["max_actions"] < 0
        or type(task["sample_kinds"]) is not dict or not task["sample_kinds"]
        or type(task["slot_zones"]) is not dict or not task["slot_zones"]
        or type(task["rules"]) is not dict): raise ContractError("invalid coldroom task values")
    if (any(type(key) is not str or not key or type(value) is not str or not value for key, value in task["sample_kinds"].items())
        or any(type(key) is not str or not key or type(value) is not int or value < 0 for key, value in task["slot_zones"].items())
        or any(type(key) is not str or not key or type(value) is not int or value < 0 for key, value in task["rules"].items())): raise ContractError("invalid coldroom task mappings")
    if views is None: return
    shapes = {
        "queen": {"task_id", "protocol", "revision", "max_actions", "samples", "slots", "goal"},
        "assay": {"sample_kinds"}, "protocol": {"rules"},
        "logistics": {"slot_zones", "capacity_per_slot"},
    }
    if type(views) is not dict or set(views) != set(shapes): raise ContractError("complete worker views required")
    _validate_json_tree(views)
    if any(type(views[role]) is not dict or set(views[role]) != fields for role, fields in shapes.items()): raise ContractError("exact worker view shape required")
    if (views["assay"]["sample_kinds"] != task["sample_kinds"]
        or views["protocol"]["rules"] != task["rules"]
        or views["logistics"]["slot_zones"] != task["slot_zones"]
        or views["queen"]["task_id"] != task["task_id"]): raise ContractError("worker views do not match evaluator task")

def adapt_coldroom(task: dict[str, Any], *, worker_views_output: dict[str, Any] | None = None, adapter_key: bytes | None = None) -> dict[str, Any]:
    if type(adapter_key) is not bytes or len(adapter_key) < 16: raise ContractError("explicit evaluator adapter bytes key required")
    _validate_adapter_inputs(task, worker_views_output)
    scope = {"protocol": task["protocol"], "revision": task["revision"]}
    def alias(prefix: str, value: str) -> str:
        if type(value) is not str or not value: raise ContractError("opaque identifiers require nonempty strings")
        return f"{prefix}-" + hmac.new(adapter_key, value.encode(), hashlib.sha256).hexdigest()[:16]
    samples = [alias("sample", x) for x in task["sample_kinds"]]; slots = [alias("slot", x) for x in task["slot_zones"]]
    public = {**_base("task-public", scope), "task_id": alias("worker-task", task["task_id"]), "samples": samples, "slots": slots, "max_actions": task["max_actions"]}
    source = {"source_id": "coldroom-evaluator", "revision": f"r{task['revision']}", "applicability": "inert-coldroom-task", "dependencies": ["inert-coldroom-v1"]}
    evidence = {**_base("evidence-reference", scope, 1), "source": source, "claim": "public coldroom observation", "accepted": None}
    action = {**_base("typed-action", scope, 2), "action": {"op": "reserve", "sample": samples[0], "slot": slots[0]}, "attempted": True, "accepted": None}
    outcome = {**_base("outcome", scope, 3), "disposition": "running", "scope_admitted": False, "accepted_transition": False, "task_success": None, "resource_budget": {"actions": task["max_actions"], "bytes": None, "seconds": None}, "resource_usage": {"actions": None, "bytes": None, "seconds": None}}
    trace = [public, evidence, action, outcome]
    if worker_views_output is not None:
        for role in ("queen", "assay", "protocol", "logistics"):
            observation = json.loads(json.dumps(worker_views_output[role]))
            if role == "protocol": observation = {"guidance_redacted": True}
            observation = _remap(observation, task, alias)
            trace.insert(1 + list(("queen", "assay", "protocol", "logistics")).index(role), {**_base("role-observation", scope, 0), "role": role, "observation": observation})
        for i, item in enumerate(trace): item["ordinal"] = i; item["event_id"] = _event_id(item)
    for item in trace:
        item["event_id"] = _event_id(item)
    validate_event_stream(trace)
    return {"task_public": public, "evidence": evidence, "action": action, "outcome": outcome, "trace": trace}

def _remap(value: Any, task: dict[str, Any], alias: Any) -> Any:
    if isinstance(value, dict):
        return {_remap(k, task, alias): _remap(v, task, alias) for k, v in value.items()}
    if isinstance(value, list): return [_remap(v, task, alias) for v in value]
    if isinstance(value, str):
        if value in task["sample_kinds"]: return alias("sample", value)
        if value in task["slot_zones"]: return alias("slot", value)
        if value == task["task_id"]: return alias("worker-task", value)
    return value

def consume_coldroom_bytes(raw: bytes) -> dict[str, Any]:
    envelope = deserialize_envelope(raw)
    if envelope["kind"] != "task-public": raise ContractError("consumer requires task-public envelope")
    return {"task_id": envelope["task_id"], "scope": envelope["scope"], "private_metadata_leaked": False}

def consume_coldroom_trace_bytes(items: list[bytes]) -> dict[str, Any]:
    """Separate worker-side consumer for a complete canonical candidate trace."""
    if type(items) is not list or not items or any(type(item) is not bytes for item in items): raise ContractError("consumer requires a nonempty bytes list")
    events = [deserialize_envelope(item) for item in items]
    validate_event_stream(events)
    expected_kinds = ["task-public"] + ["role-observation"] * 4 + ["evidence-reference", "typed-action", "outcome"]
    if [event["kind"] for event in events] != expected_kinds: raise ContractError("complete ordered coldroom worker trace required")
    public = [event for event in events if event["kind"] == "task-public"]
    roles = [event for event in events if event["kind"] == "role-observation"]
    if [event["role"] for event in roles] != ["queen", "assay", "protocol", "logistics"]: raise ContractError("complete ordered coldroom roles required")
    return {
        "task_public": public[0],
        "role_observations": {event["role"]: event["observation"] for event in roles},
        "event_ids": [event["event_id"] for event in events],
    }
