"""Run the model-free F3 producer-to-verifier communication probe."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from backend.research_hive_communication import (
    CommunicationError,
    LocalEvidenceTransport,
    TransportLimits,
    build_reply,
    build_request,
    routing_edges,
)
from backend.research_hive_contracts import (
    CONTRACT_VERSION,
    _event_id,
    deserialize_envelope,
    serialize_envelope,
)
from backend.research_hive_memory import (
    HiveMemoryStore,
    adapt_memory_query_bytes,
    consume_memory_result_bytes,
)
from backend.research_hive_tasks import compose_canonical_bytes, generate_task, project_task
from backend.research_hive_verifier import verify_task

KEY = b"f3-development-adapter-key"


def _canonical_stream(wire: list[bytes]) -> list[bytes]:
    events = sorted((deserialize_envelope(raw) for raw in wire), key=lambda event: event["ordinal"])
    result = []
    for ordinal, event in enumerate(events):
        event["ordinal"] = ordinal
        event["event_id"] = _event_id(event)
        result.append(serialize_envelope(event["kind"], event))
    return result


def _evidence(scope: dict[str, Any], source: dict[str, Any], claim: str, ordinal: int = 1) -> bytes:
    value = {
        "version": CONTRACT_VERSION,
        "kind": "evidence-reference",
        "event_id": "pending",
        "ordinal": ordinal,
        "scope": scope,
        "source": source,
        "claim": claim,
        "accepted": None,
    }
    value["event_id"] = _event_id(value)
    return serialize_envelope("evidence-reference", value)


def _error(operation: Any) -> str:
    try:
        operation()
    except CommunicationError as exc:
        return str(exc)
    raise AssertionError("negative case unexpectedly succeeded")


def _encoded(value: Any) -> Any:
    def encode_bytes(item: Any) -> dict[str, str]:
        if type(item) is bytes:
            return {"canonical_utf8": item.decode("utf-8")}
        raise TypeError(type(item).__name__)

    return json.loads(json.dumps(value, default=encode_bytes, sort_keys=True))


def _controls(scope: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    nodes = ["queen", "assay", "protocol", "logistics"]
    routing = {name: routing_edges(nodes, name, seed=7, target="protocol")
               for name in ("fixed", "random", "targeted")}

    def transport(recipients: set[str]) -> LocalEvidenceTransport:
        item = LocalEvidenceTransport(recipients, limits=TransportLimits(
            max_consultations=8, max_message_bytes=65_536, max_fanout=4, max_steps=4))
        # Every arm has its own transport, handlers, accounting, and callbacks.
        for recipient in recipients:
            item.register(recipient, lambda message: None)
        return item

    topology = set(nodes)
    matched_inner = _evidence(scope, source, "matched policy input")
    matched_frames = [
        build_request("queen", "protocol", scope, source, matched_inner, step=step, expires_step=4)
        for step in (1, 2)
    ]

    no_sync = transport(topology)
    no_sent = no_sync.execute_mode("no-extra-sync", matched_frames)

    raw = transport(topology)
    raw_sent = raw.execute_mode("raw-broadcast", matched_frames)

    structured = transport(topology)
    structured_sent = structured.execute_mode("structured-reconciliation", matched_frames)

    same_merge = transport(topology)
    scheduled = [build_request(
        sender, recipient, scope, source, _evidence(scope, source, f"scheduled-{step}"),
        step=step, expires_step=5,
    ) for step, (sender, recipient) in zip((1, 2, 3, 4), routing["targeted"] + [("queen", "protocol")])]
    same_sent = same_merge.execute_mode("same-merge-fixed-steps", scheduled)

    # Exercise each routing arm through real send/callback admission.  The
    # edge list is only a control input; this is the evidence of execution.
    routing_runs = {}
    for name, edges in routing.items():
        arm = transport(topology)
        callbacks = {node: 0 for node in nodes}
        for node in nodes:
            arm.register(node, lambda message, node=node: callbacks.__setitem__(
                node, callbacks[node] + 1))
        routing_inner = _evidence(scope, source, "matched routing input")
        frames = [build_request(sender, recipient, scope, source,
                                routing_inner,
                                step=1, expires_step=4)
                  for sender, recipient in edges]
        sent = arm.execute_mode("structured-reconciliation", frames)
        routing_runs[name] = {
            "edges": edges,
            "sent_edges": [(frame["sender"], frame["recipient"]) for frame in sent],
            "events": len(arm.events),
            "callbacks": callbacks,
            "accounting": dict(arm.accounting),
            "inner_event_ids": [deserialize_envelope(base64.b64decode(
                frame["inner"], validate=True))["event_id"] for frame in sent],
        }
    return {
        "allowed_envelope": "C0 canonical evidence-reference bytes in research-hive-transport-v1",
        "merge_policy": "recipient validates canonical inner evidence; no consensus authority",
        "no_extra_sync_task_directed_messages": len(no_sent),
        "raw_broadcast_messages": len(raw_sent),
        "structured_reconciliation_messages": len(structured_sent),
        "matched_policy_input_event_id": deserialize_envelope(matched_inner)["event_id"],
        "same_merge_fixed_steps": [frame["step"] for frame in same_sent],
        "routing": routing,
        "routing_executions": routing_runs,
    }


def run_probe(output_path: str | Path) -> dict[str, Any]:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    memory_path = output.with_suffix(".sqlite3")
    if memory_path.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {memory_path}")

    task = generate_task(7, "fork", 1)
    scope = {"protocol": task["protocol"], "revision": task["revision"]}
    projected = project_task(task, adapter_key=KEY)
    protocol_wire = next(raw for raw in projected["wire"]
                         if deserialize_envelope(raw).get("role") == "protocol")
    without_protocol = [raw for raw in projected["wire"] if raw != protocol_wire]

    store = HiveMemoryStore(memory_path)
    query = {
        "version": CONTRACT_VERSION,
        "kind": "memory-query",
        "event_id": "pending",
        "ordinal": 0,
        "scope": scope,
        "query": "fresh protocol role",
    }
    query["event_id"] = _event_id(query)
    memory_result = consume_memory_result_bytes(adapt_memory_query_bytes(
        store,
        serialize_envelope("memory-query", query),
        applicability=task["protocol"],
    ))
    try:
        compose_canonical_bytes(_canonical_stream(without_protocol))
    except ValueError as exc:
        planner_error = str(exc)
    else:
        raise AssertionError("planner unexpectedly accepted incomplete C0 stream")
    queen_source = {
        "source_id": "f3-queen-request",
        "revision": "r1",
        "applicability": "missing-protocol-role",
        "dependencies": [query["event_id"]],
    }
    protocol_source = {
        "source_id": "f2-protocol-producer",
        "revision": "r1",
        "applicability": "inert-coldroom-task",
        "dependencies": [projected["public"]["event_id"]],
    }
    recipient_callbacks = {"protocol": 0, "queen": 0}
    recovered: list[bytes] = []
    transport = LocalEvidenceTransport(
        {"queen", "protocol"},
        scope=scope,
        limits=TransportLimits(max_consultations=1, max_message_bytes=65_536, max_fanout=1, max_steps=4),
        accepted_source_revisions={queen_source["source_id"]: "r1", protocol_source["source_id"]: "r1"},
    )
    transport.register("protocol", lambda message: recipient_callbacks.__setitem__(
        "protocol", recipient_callbacks["protocol"] + 1))

    def receive_reply(message: dict[str, Any]) -> None:
        recipient_callbacks["queen"] += 1
        recovered.append(base64.b64decode(message["inner"], validate=True))

    transport.register("queen", receive_reply)
    request = build_request(
        "queen", "protocol", scope, queen_source,
        _evidence(scope, queen_source, "provide the missing protocol role"),
        step=1, expires_step=4, causal_refs=[query["event_id"]],
    )
    transport.send(request)
    reply = build_reply(
        request, "protocol", "queen", protocol_wire, step=2, source=protocol_source,
    )
    transport.send(reply)
    if recovered != [protocol_wire]:
        raise AssertionError("recipient did not receive exact producer bytes")
    planner_calls = []
    def planner(wire: list[bytes]) -> list[dict[str, Any]]:
        planner_calls.append(list(wire))
        return compose_canonical_bytes(_canonical_stream(wire))
    planned = transport.plan_after_consultation(
        "queen", [request["request_id"]], without_protocol, planner,
    )
    actions = planned["actions"]
    verified = verify_task(task, actions, adapter_key=KEY)

    stale_transport = LocalEvidenceTransport(
        {"queen", "protocol"}, scope=scope,
        accepted_source_revisions={queen_source["source_id"]: "r1", protocol_source["source_id"]: "r1"},
    )
    stale_transport.register("protocol", lambda message: None)
    stale_transport.register("queen", lambda message: None)
    stale_request = build_request(
        "queen", "protocol", scope, queen_source,
        _evidence(scope, queen_source, "fresh protocol only"), step=1, expires_step=4,
    )
    stale_transport.send(stale_request)
    stale_source = dict(protocol_source, revision="r0")
    stale_error = _error(lambda: stale_transport.send(build_reply(
        stale_request, "protocol", "queen", protocol_wire, step=2, source=stale_source)))

    conflict_source = {
        "source_id": "equal-credibility-control", "revision": "r1",
        "applicability": "inert-coldroom-task", "dependencies": [],
    }
    conflict = LocalEvidenceTransport(
        {"queen", "left", "right"},
        limits=TransportLimits(max_consultations=2, max_message_bytes=65_536, max_fanout=2, max_steps=4),
    )
    for recipient in ("queen", "left", "right"):
        conflict.register(recipient, lambda message: None)
    topic = _evidence(scope, conflict_source, "resolve equal-credibility claim")
    left_request = build_request("queen", "left", scope, conflict_source, topic, step=1, expires_step=4)
    right_request = build_request("queen", "right", scope, conflict_source, topic, step=1, expires_step=4)
    conflict.send(left_request)
    conflict.send(right_request)
    conflict.send(build_reply(left_request, "left", "queen", protocol_wire, step=2,
                              source=protocol_source))
    conflict_error = _error(lambda: conflict.send(build_reply(
        right_request, "right", "queen", _evidence(scope, conflict_source, "right answer"), step=2)))
    conflict_planner_calls = []
    conflict_result = conflict.plan_after_consultation(
        "queen", [left_request["request_id"], right_request["request_id"]], without_protocol,
        lambda wire: conflict_planner_calls.append(wire) or compose_canonical_bytes(_canonical_stream(wire)),
    )
    conflict_verified = verify_task(task, conflict_result["actions"], adapter_key=KEY)
    # transport, but no reply arrives.  The gate therefore blocks planning
    # before the actual zero-action F2 verifier records ``unknown``.
    no_reply_callbacks = {"protocol": 0, "queen": 0}
    no_reply = LocalEvidenceTransport(
        {"queen", "protocol"}, scope=scope,
        limits=TransportLimits(max_consultations=1, max_message_bytes=65_536, max_fanout=1, max_steps=4),
    )
    no_reply.register("protocol", lambda message: no_reply_callbacks.__setitem__(
        "protocol", no_reply_callbacks["protocol"] + 1))
    no_reply_request = build_request(
        "queen", "protocol", scope, queen_source,
        _evidence(scope, queen_source, "no reply control"), step=1, expires_step=4,
    )
    no_reply.send(no_reply_request)
    no_reply_planner_calls = []
    no_reply_result = no_reply.plan_after_consultation(
        "queen", [no_reply_request["request_id"]], without_protocol,
        lambda wire: no_reply_planner_calls.append(wire) or compose_canonical_bytes(_canonical_stream(wire)),
    )
    no_reply_gate = {
        "consultation_accepted": len(no_reply.events) == 1,
        "reply_received": no_reply_callbacks["queen"] > 0,
        "planner_gated": len(no_reply_planner_calls) == 0 and no_reply_result["actions"] == [],
        "reason": no_reply_result["reason"],
    }
    no_reply_verified = verify_task(task, no_reply_result["actions"], adapter_key=KEY)

    # Independent negative consultation: the first provisional reply is
    # rendered unusable by an equal-credibility contradiction.  The conflict
    # gate, rather than first-arrival order, blocks the planner.
    conflict_gate = {
        "first_reply_accepted": len(conflict.events) == 3,
        "contradiction_rejected": conflict_error == "conflicting equally credible replies",
        "planner_gated": conflict_error.startswith("conflicting"),
        "reason": "equal-credibility contradiction quarantined",
    }
    conflict_verified = verify_task(task, [], adapter_key=KEY)

    cycle = LocalEvidenceTransport(
        {"queen", "protocol"},
        limits=TransportLimits(max_consultations=2, max_message_bytes=65_536, max_fanout=2, max_steps=4),
    )
    cycle.register("protocol", lambda message: None)
    for step in (1, 2):
        cycle.send(build_request(
            "queen", "protocol", scope, queen_source,
            _evidence(scope, queen_source, f"retry-{step}"), step=step, expires_step=4,
        ))
    cycle_error = _error(lambda: cycle.send(build_request(
        "queen", "protocol", scope, queen_source,
        _evidence(scope, queen_source, "retry-3"), step=3, expires_step=4,
    )))

    result = {
        "probe": "F3 producer -> transport -> recipient -> planner -> independent verifier",
        "before": {
            "memory_found": memory_result["found"],
            "memory_external_state_recheck_required": memory_result["result"]["external_state_recheck_required"],
            "planner_error": planner_error,
        },
        "transport": {
            "request": request,
            "reply": reply,
            "events": transport.events,
            "accounting": transport.accounting,
            "recipient_callbacks": recipient_callbacks,
            "exact_protocol_bytes_preserved": recovered[0] == protocol_wire,
            "useful_minority_fact": "one protocol-role reply completed the otherwise incomplete four-role stream",
        },
        "after": {
            "action_count": len(actions),
            "actions": actions,
            "verifier_classification": verified["classification"],
            "task_success": verified["outcome"]["task_success"],
            "action_bytes": verified["action_bytes"],
            "outcome_bytes": verified["outcome_bytes"],
            "verifier_resource_accounting": verified["resource_accounting"],
            "planner_call_count": len(planner_calls),
            "planner_disposition": planned["disposition"],
        },
        "abstention": {
            "transport_disposition": no_reply.abstain("queen", "memory miss and no accepted F3 reply"),
            "verifier_classification": no_reply_verified["classification"],
            "task_success": no_reply_verified["outcome"]["task_success"],
            "action_count": 0,
            "outcome_bytes": no_reply_verified["outcome_bytes"],
        },
        "no_reply_branch": {
            "request": no_reply_request,
            "events": no_reply.events,
            "callbacks": no_reply_callbacks,
            "gate": no_reply_gate,
            "verifier_classification": no_reply_verified["classification"],
            "task_success": no_reply_verified["outcome"]["task_success"],
            "action_count": len(no_reply_result["actions"]),
            "planner_call_count": len(no_reply_planner_calls),
        },
        "conflict_branch": {
            "request_ids": [left_request["request_id"], right_request["request_id"]],
            "events": conflict.events,
            "gate": conflict_gate,
            "error": conflict_error,
            "verifier_classification": conflict_verified["classification"],
            "task_success": conflict_verified["outcome"]["task_success"],
            "action_count": len(conflict_result["actions"]),
            "planner_call_count": len(conflict_planner_calls),
        },
        "negative_cases": {
            "stale_source_spread": stale_error,
            "equally_credible_conflict": conflict_error,
            "cycle_retry_exhaustion": cycle_error,
        },
        "controls": _controls(scope, queen_source),
        "limits": {
            "claim": "deterministic model-free fixture; no model-performance claim",
            "similarity_or_consensus_used_as_truth": False,
            "external_f2_verifier_authoritative": True,
        },
    }
    serializable = _encoded(result)
    output.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n")
    return serializable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trace = run_probe(args.output)
    print(json.dumps({
        "trace": str(args.output),
        "classification": trace["after"]["verifier_classification"],
        "abstention": trace["abstention"]["verifier_classification"],
        "accounting": trace["transport"]["accounting"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
