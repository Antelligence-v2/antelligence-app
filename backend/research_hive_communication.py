"""Bounded local transport for C0 canonical evidence.

Transport frames are deliberately local and are not added to the C0 contract.
The bytes carried in ``inner`` remain canonical C0 envelopes and retain their
C0 validation and authority rules.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Callable

from .research_hive_contracts import CONTRACT_VERSION, deserialize_envelope

TRANSPORT_VERSION = "research-hive-transport-v1"


class CommunicationError(ValueError):
    """Malformed, unauthorized, stale, duplicate, or over-budget transport."""


@dataclass(frozen=True)
class TransportLimits:
    max_consultations: int = 8
    max_message_bytes: int = 16_384
    max_fanout: int = 4
    max_steps: int = 16

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 0 for v in (self.max_consultations, self.max_message_bytes, self.max_fanout, self.max_steps)):
            raise CommunicationError("transport limits must be nonnegative integers")


def _scope(value: Any) -> None:
    if (type(value) is not dict or set(value) != {"protocol", "revision"}
            or type(value["protocol"]) is not str or not value["protocol"]
            or type(value["revision"]) is not int or value["revision"] < 0):
        raise CommunicationError("invalid transport scope")


def _source(value: Any) -> None:
    if (type(value) is not dict or set(value) != {"source_id", "revision", "applicability", "dependencies"}
            or any(type(value[k]) is not str or not value[k] for k in ("source_id", "revision", "applicability"))
            or type(value["dependencies"]) is not list
            or any(type(x) is not str or not x for x in value["dependencies"])):
        raise CommunicationError("invalid transport source")


def _inner(raw: Any, scope: dict[str, Any]) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise CommunicationError("inner evidence must be canonical bytes")
    try:
        value = deserialize_envelope(raw)
    except Exception as exc:
        raise CommunicationError("invalid canonical inner evidence") from exc
    if value["scope"] != scope:
        raise CommunicationError("inner evidence scope mismatch")
    if value["kind"] not in {"evidence-reference", "memory-result", "role-observation", "task-public"}:
        raise CommunicationError("inner evidence kind is not exchangeable")
    return value


def routing_edges(nodes: list[str], strategy: str, *, seed: int, target: str) -> list[tuple[str, str]]:
    """Return equal-size edge sets while changing only routing selection."""
    if (type(nodes) is not list or len(nodes) < 2 or len(set(nodes)) != len(nodes)
            or any(type(node) is not str or not node for node in nodes)
            or type(seed) is not int or target not in nodes):
        raise CommunicationError("routing requires unique nodes, integer seed, and known target")
    ordered = list(nodes)
    if strategy == "fixed":
        return list(zip(ordered[:-1], ordered[1:]))
    if strategy == "random":
        random.Random(seed).shuffle(ordered)
        return list(zip(ordered[:-1], ordered[1:]))
    if strategy == "targeted":
        return [(node, target) for node in ordered if node != target]
    raise CommunicationError("unsupported routing strategy")


def _frame_id(frame: dict[str, Any]) -> str:
    omitted = {"message_id"}
    if frame.get("type") == "evidence-request":
        omitted.add("request_id")
    body = {k: v for k, v in frame.items() if k not in omitted}
    return "msg-" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


def _frame(kind: str, sender: str, recipient: str, scope: dict[str, Any], source: dict[str, Any], raw: bytes,
           *, step: int, expires_step: int, causal_refs: list[str], request_id: str | None = None) -> dict[str, Any]:
    if kind not in {"evidence-request", "evidence-reply"}:
        raise CommunicationError("unsupported transport frame")
    if any(type(x) is not str or not x for x in (sender, recipient)):
        raise CommunicationError("sender and recipient are required")
    _scope(scope); _source(source); _inner(raw, scope)
    if type(step) is not int or step < 0 or type(expires_step) is not int or expires_step < step:
        raise CommunicationError("invalid transport lifetime")
    if (type(causal_refs) is not list or len(causal_refs) > 16
            or any(type(x) is not str or not x or len(x) > 128 for x in causal_refs)):
        raise CommunicationError("causal references are required and bounded")
    value: dict[str, Any] = {"type": kind, "version": TRANSPORT_VERSION, "sender": sender,
        "recipient": recipient, "scope": scope, "source": source, "step": step,
        "expires_step": expires_step, "causal_refs": list(causal_refs),
        "inner": base64.b64encode(raw).decode("ascii")}
    if request_id is not None:
        value["request_id"] = request_id
    value["message_id"] = _frame_id(value)
    if kind == "evidence-request":
        value["request_id"] = value["message_id"]
    return value


def build_request(sender: str, recipient: str, scope: dict[str, Any], source: dict[str, Any], inner: bytes,
                  *, step: int, expires_step: int, causal_refs: list[str] | None = None) -> dict[str, Any]:
    return _frame("evidence-request", sender, recipient, scope, source, inner, step=step,
                  expires_step=expires_step, causal_refs=[] if causal_refs is None else causal_refs)


def build_reply(request: dict[str, Any], sender: str, recipient: str, inner: bytes, *, step: int,
                source: dict[str, Any] | None = None) -> dict[str, Any]:
    if type(request) is not dict or request.get("type") != "evidence-request" or type(request.get("message_id")) is not str:
        raise CommunicationError("reply requires a valid evidence request")
    return _frame("evidence-reply", sender, recipient, request["scope"], request["source"] if source is None else source, inner,
                  step=step, expires_step=request["expires_step"], causal_refs=[request["message_id"]],
                  request_id=request["message_id"])


class LocalEvidenceTransport:
    """In-process, recipient-addressed transport with admission before callbacks."""

    def __init__(self, recipients: set[str] | list[str], *, limits: TransportLimits | None = None,
                 scope: dict[str, Any] | None = None, current_step: int = 0,
                 accepted_source_revisions: dict[str, str] | None = None):
        self.recipients = set(recipients)
        self.limits = limits or TransportLimits()
        self.scope = scope
        self.current_step = current_step
        self.accepted_source_revisions = dict(accepted_source_revisions or {})
        if any(type(key) is not str or not key or type(value) is not str or not value
               for key, value in self.accepted_source_revisions.items()):
            raise CommunicationError("accepted source revisions must be bounded identities")
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []
        self.accounting = {"consultations": 0, "message_bytes": 0, "events": 0, "fanout": 0, "steps": 0}
        self._seen: set[str] = set()
        self._requests: dict[str, dict[str, Any]] = {}
        self._replies: dict[str, tuple[str, str]] = {}
        self._reply_records: dict[str, dict[str, Any]] = {}
        self._quarantined_topics: set[str] = set()

    def register(self, recipient: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if recipient not in self.recipients:
            raise CommunicationError("unknown recipient")
        self.handlers[recipient] = handler

    def _validate(self, frame: dict[str, Any]) -> bytes:
        if type(frame) is not dict or frame.get("version") != TRANSPORT_VERSION:
            raise CommunicationError("unsupported transport version")
        expected = {"type", "version", "sender", "recipient", "scope", "source", "step",
                    "expires_step", "causal_refs", "inner", "message_id", "request_id"}
        if set(frame) != expected or frame.get("type") not in {"evidence-request", "evidence-reply"}:
            raise CommunicationError("invalid transport frame shape")
        if frame["message_id"] != _frame_id(frame):
            raise CommunicationError("message ID is content-tampered")
        if frame["type"] == "evidence-request" and frame["request_id"] != frame["message_id"]:
            raise CommunicationError("request identity mismatch")
        if frame["type"] == "evidence-reply" and frame["causal_refs"] != [frame["request_id"]]:
            raise CommunicationError("reply causal reference mismatch")
        if (type(frame["causal_refs"]) is not list or len(frame["causal_refs"]) > 16
                or any(type(ref) is not str or not ref or len(ref) > 128
                       for ref in frame["causal_refs"])):
            raise CommunicationError("causal references are required and bounded")
        _scope(frame.get("scope")); _source(frame.get("source"))
        expected_revision = self.accepted_source_revisions.get(frame["source"]["source_id"])
        if expected_revision is not None and frame["source"]["revision"] != expected_revision:
            raise CommunicationError("stale source revision")
        if frame.get("sender") not in self.recipients:
            raise CommunicationError("unknown sender")
        if frame.get("recipient") not in self.recipients:
            raise CommunicationError("unknown recipient")
        if self.scope is not None and frame.get("scope") != self.scope:
            raise CommunicationError("scope mismatch")
        if frame["sender"] == frame["recipient"]:
            raise CommunicationError("wrong recipient")
        if (type(frame.get("step")) is not int or frame["step"] < 0
                or frame["step"] > self.limits.max_steps):
            raise CommunicationError("step budget exhausted")
        if (type(frame.get("expires_step")) is not int or frame["expires_step"] < 0
                or self.current_step >= frame["expires_step"] or frame["step"] >= frame["expires_step"]):
            raise CommunicationError("expired")
        if frame["message_id"] in self._seen:
            raise CommunicationError("duplicate/replay")
        raw = base64.b64decode(frame.get("inner", ""), validate=True)
        inner = _inner(raw, frame["scope"])
        if "source" in inner and inner["source"] != frame["source"]:
            raise CommunicationError("transport source mismatch")
        encoded = (json.dumps(frame, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if (len(encoded) > self.limits.max_message_bytes
                or self.accounting["message_bytes"] + len(encoded) > self.limits.max_message_bytes):
            raise CommunicationError("message byte budget exhausted")
        if frame["type"] == "evidence-reply":
            request = self._requests.get(frame["request_id"])
            if request is None or request["type"] != "evidence-request":
                raise CommunicationError("reply references unknown request")
            if frame["recipient"] != request["sender"]:
                raise CommunicationError("wrong recipient")
            if frame["sender"] != request["recipient"]:
                raise CommunicationError("reply sender is not requested recipient")
            if (frame["scope"] != request["scope"]
                    or frame["step"] < request["step"]
                    or frame["step"] >= request["expires_step"]
                    or frame["expires_step"] != request["expires_step"]):
                raise CommunicationError("reply falls outside request interval")
            claim = deserialize_envelope(raw).get("claim", json.dumps(deserialize_envelope(raw), sort_keys=True))
            key = self._reply_topic(frame["request_id"])
            if key in self._quarantined_topics:
                raise CommunicationError("conflicting equally credible replies; topic quarantined")
            prior = self._replies.get(key)
            if prior and prior[1] != claim:
                self._quarantined_topics.add(key)
                raise CommunicationError("conflicting equally credible replies")
        return encoded

    def _request_sender(self, message_id: str) -> str:
        request = self._requests.get(message_id)
        if request is None:
            raise CommunicationError("reply references unknown request")
        return request["sender"]

    def _reply_topic(self, request_id: str) -> str:
        request = self._requests.get(request_id)
        if request is None or request["type"] != "evidence-request":
            raise CommunicationError("reply references unknown request")
        inner = deserialize_envelope(base64.b64decode(request["inner"], validate=True))
        return inner["event_id"]

    def _diagnose(self, frame: Any, exc: CommunicationError) -> None:
        """Retain bounded rejection evidence without making it an accepted event."""
        if len(self.diagnostics) >= 64:
            self.diagnostics.pop(0)
        self.diagnostics.append({
            "disposition": "conflict" if "conflicting" in str(exc) else "rejected",
            "reason": str(exc),
            "type": frame.get("type") if isinstance(frame, dict) else None,
            "message_id": frame.get("message_id") if isinstance(frame, dict) else None,
        })

    def send(self, frame: dict[str, Any]) -> dict[str, Any]:
        candidate = json.loads(json.dumps(frame)) if isinstance(frame, dict) else frame
        try:
            encoded = self._validate(candidate)
            if candidate["type"] == "evidence-request":
                if self.accounting["consultations"] >= self.limits.max_consultations:
                    raise CommunicationError("consultation budget exhausted")
                sent = sum(1 for event in self.events if event["message"]["sender"] == candidate["sender"] and event["message"]["step"] == candidate["step"])
                if sent >= self.limits.max_fanout:
                    raise CommunicationError("fanout budget exhausted")
            handler = self.handlers.get(candidate["recipient"])
            if handler is None:
                raise CommunicationError("recipient has no handler")
            snapshot = json.loads(json.dumps(candidate))
            event = {"event": "transport", "message": json.loads(json.dumps(snapshot)), "raw": encoded, "resource": {"bytes": len(encoded), "step": candidate["step"]}}
            self._seen.add(candidate["message_id"]); self.events.append(event)
            self.accounting["message_bytes"] += len(encoded); self.accounting["events"] += 1
            self.accounting["steps"] = max(self.accounting["steps"], candidate["step"])
            if candidate["type"] == "evidence-request":
                self.accounting["consultations"] += 1
                self.accounting["fanout"] += 1
                self._requests[candidate["request_id"]] = json.loads(json.dumps(snapshot))
            else:
                raw = base64.b64decode(candidate["inner"], validate=True)
                inner = deserialize_envelope(raw)
                claim = inner.get("claim", json.dumps(inner, sort_keys=True))
                self._replies[self._reply_topic(candidate["request_id"])] = (candidate["sender"], claim)
                self._reply_records[candidate["request_id"]] = {
                    "sender": candidate["sender"],
                    "recipient": candidate["recipient"],
                    "source": json.loads(json.dumps(candidate["source"])),
                    "raw": bytes(raw),
                }
            handler(json.loads(json.dumps(snapshot)))
            return json.loads(json.dumps(snapshot))
        except CommunicationError as exc:
            self._diagnose(frame, exc)
            raise

    def abstain(self, recipient: str, reason: str) -> dict[str, str]:
        if recipient not in self.recipients or not isinstance(reason, str) or not reason:
            raise CommunicationError("missing facts require a known recipient and reason")
        return {"disposition": "abstained", "recipient": recipient, "reason": reason}

    def plan_after_consultation(self, recipient: str, request_ids: list[str],
                                initial_evidence: list[bytes], planner: Callable[[list[bytes]], list[dict[str, Any]]]) -> dict[str, Any]:
        """Gate planning on the transport's admitted, retained consultation state."""
        def blocked(reason: str) -> dict[str, Any]:
            return {"actions": [], "disposition": "abstained", "recipient": recipient, "reason": reason}

        if recipient not in self.recipients:
            return blocked("unknown recipient")
        if type(request_ids) is not list or not request_ids:
            return blocked("empty request IDs")
        if any(type(request_id) is not str or not request_id for request_id in request_ids):
            return blocked("invalid request IDs")
        if type(initial_evidence) is not list or not initial_evidence:
            return blocked("empty initial evidence")
        if not callable(planner):
            return blocked("planner is not callable")
        try:
            initial = []
            for raw in initial_evidence:
                if type(raw) is not bytes:
                    return blocked("initial evidence must be canonical bytes")
                event = deserialize_envelope(raw)
                if raw != (json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode():
                    return blocked("initial evidence must be canonical bytes")
                if self.scope is not None and event["scope"] != self.scope:
                    return blocked("initial evidence scope mismatch")
                initial.append(bytes(raw))
        except Exception:
            return blocked("invalid initial evidence")

        retained: list[bytes] = []
        for request_id in request_ids:
            request = self._requests.get(request_id)
            reply = self._reply_records.get(request_id)
            if request is None:
                return blocked("unknown request")
            if request["sender"] != recipient or request["type"] != "evidence-request":
                return blocked("request recipient mismatch")
            if self.current_step >= request["expires_step"]:
                return blocked("consultation expired")
            source_id = request["source"]["source_id"]
            configured = self.accepted_source_revisions.get(source_id)
            if configured is not None and configured != request["source"]["revision"]:
                return blocked("source revision changed")
            if reply is None or reply["recipient"] != recipient:
                return blocked("missing accepted reply")
            reply_configured = self.accepted_source_revisions.get(reply["source"]["source_id"])
            if reply_configured is not None and reply_configured != reply["source"]["revision"]:
                return blocked("source revision changed")
            topic = self._reply_topic(request_id)
            if topic in self._quarantined_topics:
                return blocked("unresolved quarantined topic conflict")
            retained.append(bytes(reply["raw"]))
        try:
            actions = planner(initial + retained)
        except Exception as exc:
            return blocked(f"planner failed: {exc}")
        if type(actions) is not list:
            return blocked("planner must return an actions list")
        return {"actions": actions, "disposition": "planned", "recipient": recipient,
                "reason": "admitted consultation evidence"}

    def _structured_merge(self, frames: list[dict[str, Any]], *, fixed_steps: set[int] | None = None) -> list[dict[str, Any]]:
        """Admit addressed evidence through the one structured merge path.

        ``same-merge-fixed-steps`` is a schedule for this path, not a second
        implementation that merely filters frames.  Keeping the send loop in
        one helper makes the comparator meaningful while retaining transport
        admission and recipient callbacks for every selected frame.
        """
        result = []
        merged_topics: set[tuple[str, str, str]] = set()
        for frame in frames:
            if fixed_steps is not None and frame.get("step") not in fixed_steps:
                continue
            # Validate every scheduled frame before applying semantic merge
            # policy.  This reuses the transport's sole authoritative
            # admission/diagnostic path, so malformed or replayed repeats are
            # rejected rather than silently policy-suppressed.
            try:
                self._validate(frame)
            except CommunicationError as exc:
                self._diagnose(frame, exc)
                raise
            inner = deserialize_envelope(base64.b64decode(frame["inner"], validate=True))
            topic = (frame["sender"], frame["recipient"], inner["event_id"])
            if topic in merged_topics:
                continue
            merged_topics.add(topic)
            result.append(self.send(frame))
        return result

    def execute_mode(self, mode: str, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if mode == "no-extra-sync":
            return [self.send(frame) for frame in frames]
        if mode == "structured-reconciliation":
            return self._structured_merge(frames)
        if mode == "same-merge-fixed-steps":
            return self._structured_merge(frames, fixed_steps={2, 4})
        if mode == "raw-broadcast":
            result = []
            for frame in frames:
                for recipient in sorted(self.recipients - {frame["sender"]}):
                    copy = dict(frame, recipient=recipient, message_id="pending")
                    copy["message_id"] = _frame_id(copy)
                    copy["request_id"] = copy["message_id"]
                    result.append(self.send(copy))
            return result
        raise CommunicationError("unsupported communication mode")


__all__ = ["CommunicationError", "TransportLimits", "LocalEvidenceTransport", "build_request", "build_reply", "routing_edges", "TRANSPORT_VERSION"]
