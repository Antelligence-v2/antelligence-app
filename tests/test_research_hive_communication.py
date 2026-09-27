import pytest

from backend.research_hive_communication import (
    CommunicationError,
    TransportLimits,
    LocalEvidenceTransport,
    build_request,
    build_reply,
    routing_edges,
)
from backend.research_hive_contracts import CONTRACT_VERSION, _event_id, serialize_envelope


SCOPE = {"protocol": "inert-coldroom-v1", "revision": 0}
SOURCE = {"source_id": "assay-a", "revision": "r0", "applicability": "inert-coldroom-task", "dependencies": []}


def inner(role="assay", claim="minority fact", scope=SCOPE):
    value = {"version": CONTRACT_VERSION, "kind": "evidence-reference", "event_id": "pending", "ordinal": 1,
             "scope": scope, "source": SOURCE, "claim": claim, "accepted": None}
    value["event_id"] = _event_id(value)
    return serialize_envelope("evidence-reference", value)


def test_request_reply_are_typed_and_canonical_inner_evidence_is_preserved():
    request = build_request("queen", "assay-a", SCOPE, SOURCE, inner(), step=2, expires_step=4, causal_refs=["evt-root"])
    reply = build_reply(request, "assay-a", "queen", inner(claim="answer"), step=3)
    assert request["type"] == "evidence-request"
    assert reply["type"] == "evidence-reply"
    assert request["version"] == reply["version"] == "research-hive-transport-v1"
    assert request["causal_refs"] == ["evt-root"]
    assert reply["request_id"] == request["request_id"]


def test_budget_is_checked_before_recipient_side_effect_and_actual_accounting_is_recorded():
    seen = []
    transport = LocalEvidenceTransport({"queen", "assay-a"}, limits=TransportLimits(max_consultations=1, max_message_bytes=10_000, max_fanout=1, max_steps=4))
    transport.register("assay-a", lambda message: seen.append(message))
    request = build_request("queen", "assay-a", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    transport.send(request)
    assert len(seen) == 1
    assert transport.accounting["consultations"] == 1
    assert transport.accounting["message_bytes"] == len(transport.events[0]["raw"])
    with pytest.raises(CommunicationError, match="consultation budget exhausted"):
        transport.send(build_request("queen", "assay-a", SCOPE, SOURCE, inner(), step=2, expires_step=3))
    assert len(seen) == 1


def test_duplicate_expired_scope_recipient_and_unknown_recipient_fail_closed():
    transport = LocalEvidenceTransport({"queen", "assay-a"}, scope=SCOPE)
    transport.register("assay-a", lambda message: None)
    request = build_request("queen", "assay-a", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    transport.send(request)
    for bad, message in [
        (request, "duplicate/replay"),
        (build_request("queen", "assay-a", SCOPE, SOURCE, inner(), step=3, expires_step=3), "expired"),
        (build_request("queen", "assay-a", {"protocol": "inert-coldroom-v1", "revision": 1}, SOURCE, inner(scope={"protocol": "inert-coldroom-v1", "revision": 1}), step=1, expires_step=2), "scope mismatch"),
        (build_request("assay-a", "queen", SCOPE, SOURCE, inner(), step=1, expires_step=2), "recipient"),
        (build_request("queen", "ghost", SCOPE, SOURCE, inner(), step=1, expires_step=2), "unknown recipient"),
    ]:
        with pytest.raises(CommunicationError, match=message):
            transport.send(bad)


def test_equally_credible_conflicting_replies_and_missing_facts_abstain():
    transport = LocalEvidenceTransport({"queen", "a", "b"})
    transport.register("queen", lambda message: None)
    transport.register("a", lambda message: None)
    transport.register("b", lambda message: None)
    request_a = build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    request_b = build_request("queen", "b", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    transport.send(request_a)
    transport.send(request_b)
    first = build_reply(request_a, "a", "queen", inner(claim="left"), step=2)
    second = build_reply(request_b, "b", "queen", inner(claim="right"), step=2)
    transport.send(first)
    with pytest.raises(CommunicationError, match="conflicting equally credible replies"):
        transport.send(second)
    assert transport.abstain("queen", "missing evidence")["disposition"] == "abstained"


def test_modes_execute_on_same_transport_seam():
    transport = LocalEvidenceTransport({"queen", "a", "b"})
    seen = []
    for recipient in ("a", "b"):
        transport.register(recipient, lambda message: seen.append(message))
    assert transport.execute_mode("no-extra-sync", []) == []
    request = build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    assert len(transport.execute_mode("raw-broadcast", [request])) == 2
    second = build_request("queen", "a", SCOPE, SOURCE, inner(claim="second"), step=2, expires_step=3)
    assert transport.execute_mode("structured-reconciliation", [second])[0]["type"] == "evidence-request"
    assert len(seen) == 3


def test_tampering_missing_handler_and_aggregate_byte_exhaustion_precede_side_effects():
    seen = []
    request = build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=4)
    one_message = len((__import__("json").dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode())
    missing_handler = LocalEvidenceTransport({"queen", "b"})
    with pytest.raises(CommunicationError, match="handler"):
        missing_handler.send(build_request("queen", "b", SCOPE, SOURCE, inner(claim="other"), step=2, expires_step=4))
    assert missing_handler.accounting["events"] == 0

    transport = LocalEvidenceTransport(
        {"queen", "a", "b"},
        limits=TransportLimits(max_consultations=3, max_message_bytes=one_message, max_fanout=2, max_steps=4),
    )
    transport.register("a", lambda message: seen.append(message))
    transport.send(request)

    tampered = dict(build_request("queen", "a", SCOPE, SOURCE, inner(claim="new"), step=2, expires_step=4))
    tampered["recipient"] = "b"
    with pytest.raises(CommunicationError, match="message ID"):
        transport.send(tampered)
    with pytest.raises(CommunicationError, match="message byte budget exhausted"):
        transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(claim="third"), step=2, expires_step=4))
    assert len(seen) == 1
    assert transport.accounting["events"] == 1


def test_admitted_return_and_rejection_diagnostics_are_detached_and_bounded():
    transport = LocalEvidenceTransport({"queen", "a"}, limits=TransportLimits(max_consultations=1, max_message_bytes=20_000, max_fanout=1, max_steps=4))
    transport.register("a", lambda message: message["source"]["dependencies"].append("callback-mutation"))
    request = build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=3)
    returned = transport.send(request)
    returned["source"]["dependencies"].append("caller-mutation")
    assert transport.events[0]["message"]["source"]["dependencies"] == []
    with pytest.raises(CommunicationError, match="consultation budget exhausted"):
        transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(claim="retry"), step=2, expires_step=3))
    assert transport.diagnostics[-1]["disposition"] == "rejected"
    assert transport.accounting["events"] == 1
    for step in range(64):
        with pytest.raises(CommunicationError):
            transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(claim=f"overflow-{step}"), step=2, expires_step=3))
    assert len(transport.diagnostics) == 64


def test_reply_must_come_from_requested_recipient_and_source_matches_inner_evidence():
    transport = LocalEvidenceTransport({"queen", "a", "b"})
    transport.register("queen", lambda message: None)
    transport.register("a", lambda message: None)
    request = build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=4)
    transport.send(request)
    with pytest.raises(CommunicationError, match="requested recipient"):
        transport.send(build_reply(request, "b", "queen", inner(), step=2))

    other_source = {**SOURCE, "source_id": "forged"}
    forged = build_request("queen", "a", SCOPE, other_source, inner(), step=2, expires_step=4)
    with pytest.raises(CommunicationError, match="source mismatch"):
        transport.send(forged)


def test_causal_refs_and_steps_are_bounded_and_cycles_exhaust_without_callback():
    with pytest.raises(CommunicationError, match="causal references"):
        build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=4, causal_refs=[str(i) for i in range(17)])
    seen = []
    transport = LocalEvidenceTransport({"queen", "a"}, limits=TransportLimits(max_consultations=2, max_message_bytes=20_000, max_fanout=2, max_steps=2))
    transport.register("a", lambda message: seen.append(message))
    transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(), step=1, expires_step=3))
    transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(claim="retry"), step=2, expires_step=3))
    with pytest.raises(CommunicationError, match="step budget exhausted|consultation budget exhausted"):
        transport.send(build_request("queen", "a", SCOPE, SOURCE, inner(claim="cycle"), step=3, expires_step=4))
    assert len(seen) == 2


def test_fixed_random_and_targeted_routing_hold_topology_and_envelope_policy_fixed():
    nodes = ["queen", "assay", "protocol", "logistics"]
    fixed = routing_edges(nodes, "fixed", seed=7, target="protocol")
    random = routing_edges(nodes, "random", seed=7, target="protocol")
    targeted = routing_edges(nodes, "targeted", seed=7, target="protocol")
    for edges in (fixed, random, targeted):
        assert len(edges) == 3
        assert {sender for sender, _ in edges} | {recipient for _, recipient in edges} == set(nodes)
        assert all(sender != recipient for sender, recipient in edges)
    assert fixed != random != targeted


def test_same_merge_control_executes_documented_steps_two_and_four():
    seen = []
    transport = LocalEvidenceTransport({"queen", "a"})
    transport.register("a", lambda message: seen.append(message["step"]))
    frames = [
        build_request("queen", "a", SCOPE, SOURCE, inner(claim=f"step-{step}"), step=step, expires_step=5)
        for step in (1, 2, 3, 4)
    ]
    sent = transport.execute_mode("same-merge-fixed-steps", frames)
    assert [frame["step"] for frame in sent] == [2, 4]
    assert seen == [2, 4]


def test_probe_keeps_routing_arms_and_negative_gates_on_real_paths(tmp_path):
    from scripts.probe_hive_communication import run_probe

    trace = run_probe(tmp_path / "F3-CONTROLS.json")
    for strategy, execution in trace["controls"]["routing_executions"].items():
        assert execution["sent_edges"] == execution["edges"]
        assert execution["events"] == len(execution["edges"])
        assert sum(execution["callbacks"].values()) == len(execution["edges"])
        assert len(set(execution["inner_event_ids"])) == 1
    assert trace["controls"]["no_extra_sync_task_directed_messages"] == 2
    assert trace["controls"]["raw_broadcast_messages"] == 6
    assert trace["controls"]["structured_reconciliation_messages"] == 1
    assert trace["no_reply_branch"]["gate"]["planner_gated"] is True
    assert trace["no_reply_branch"]["verifier_classification"] == "unknown"
    assert trace["no_reply_branch"]["task_success"] is None
    assert trace["abstention"]["transport_disposition"]["reason"] == "memory miss and no accepted F3 reply"
    assert trace["conflict_branch"]["gate"]["first_reply_accepted"] is True
    assert trace["conflict_branch"]["gate"]["planner_gated"] is True
    assert trace["conflict_branch"]["verifier_classification"] == "unknown"
    assert trace["conflict_branch"]["task_success"] is None


def test_real_f1_transport_f2_probe_emits_success_and_justified_abstention(tmp_path):
    from scripts.probe_hive_communication import run_probe

    path = tmp_path / "F3-TRACE.json"
    trace = run_probe(path)

    assert path.exists()
    assert trace["before"]["memory_found"] is False
    assert trace["before"]["planner_error"] == "all projected role observations are required"
    assert trace["after"]["verifier_classification"] == "success"
    assert trace["after"]["task_success"] is True
    assert trace["abstention"]["verifier_classification"] == "unknown"
    assert trace["abstention"]["task_success"] is None
    assert trace["negative_cases"] == {
        "stale_source_spread": "stale source revision",
        "equally_credible_conflict": "conflicting equally credible replies",
        "cycle_retry_exhaustion": "consultation budget exhausted",
    }
    assert trace["transport"]["accounting"]["consultations"] == 1
    assert trace["transport"]["accounting"]["message_bytes"] > 0
    assert trace["transport"]["recipient_callbacks"] == {"protocol": 1, "queen": 1}
    assert trace["controls"]["same_merge_fixed_steps"] == [2, 4]
    assert set(trace["controls"]["routing"]) == {"fixed", "random", "targeted"}
    assert trace["limits"]["claim"] == "deterministic model-free fixture; no model-performance claim"


def test_consumer_reads_detached_authoritative_retained_bytes_after_public_mutation():
    scope = SCOPE
    source = SOURCE
    transport = LocalEvidenceTransport({"queen", "protocol"}, scope=scope,
                                       accepted_source_revisions={"assay-a": "r0"})
    public_events = []
    callback_snapshots = []
    transport.register("protocol", lambda frame: callback_snapshots.append(frame))
    transport.register("queen", lambda frame: callback_snapshots.append(frame))
    request = build_request("queen", "protocol", scope, source, inner(), step=1, expires_step=4)
    transport.send(request)
    reply = build_reply(request, "protocol", "queen", inner(claim="authoritative"), step=2)
    returned = transport.send(reply)
    public_events.extend(transport.events)
    public_events[0]["message"]["source"]["revision"] = "forged"
    public_events[1]["raw"] = b"forged"
    callback_snapshots[0]["source"]["revision"] = "forged"
    returned["source"]["revision"] = "forged"
    transport.diagnostics.append({"type": "reply", "message_id": "forged"})
    calls = []
    result = transport.plan_after_consultation(
        "queen", [request["request_id"]], [inner(claim="initial")],
        lambda wire: calls.append(wire) or list(wire),
    )
    assert result["disposition"] == "planned"
    assert len(calls) == 1
    assert calls[0][1] == inner(claim="authoritative")


def test_consumer_abstains_when_configured_source_revision_changes_after_admission():
    transport = LocalEvidenceTransport({"queen", "protocol"}, scope=SCOPE,
                                       accepted_source_revisions={"assay-a": "r0"})
    transport.register("protocol", lambda frame: None)
    transport.register("queen", lambda frame: None)
    request = build_request("queen", "protocol", SCOPE, SOURCE, inner(), step=1, expires_step=4)
    transport.send(request)
    transport.accepted_source_revisions["assay-a"] = "r1"
    calls = []
    result = transport.plan_after_consultation(
        "queen", [request["request_id"]], [inner()],
        lambda wire: calls.append(wire) or [],
    )
    assert result["disposition"] == "abstained"
    assert result["actions"] == []
    assert calls == []
