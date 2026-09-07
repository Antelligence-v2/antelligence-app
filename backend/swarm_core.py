"""Provider-free swarm research orchestration and scoring kernel.

The module deliberately owns no provider, dataset, persistence, or API concerns.
Callers supply an inference callback and an event sink; every boundary is plain
JSON-compatible data so a parent runtime can store or stream the result.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


PROTOCOLS = ("single", "independent_vote", "peer_review", "signal_board")
_MAX_SEED = 2_147_483_647
_TASK_FIELDS = (
    "task_id",
    "source_id",
    "dataset",
    "domain",
    "split",
    "question",
    "evidence",
    "answer_type",
    "choices",
    "expected_answer",
    "tolerance",
    "source_url",
)
_ANSWER_FIELDS = {"answer", "evidence_ids", "brief"}
_CRITIQUE_FIELDS = {"target_message_id", "assessment", "evidence_ids", "brief"}
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class _PayloadError(ValueError):
    """A response was returned but did not satisfy a strict payload schema."""


class _Execution:
    """Bookkeeping for one returned cell."""

    def __init__(
        self,
        *,
        task: Mapping[str, Any],
        protocol: str,
        variant: str,
        model_keys: list[str],
        settings: Mapping[str, Any],
        infer: Callable[..., Mapping[str, Any]],
        emit: Callable[[dict[str, Any]], Any],
        should_stop: Callable[[], bool],
        expected_calls: int,
    ) -> None:
        self.task = task
        self.task_id = str(task["task_id"])
        self.protocol = protocol
        self.variant = variant
        self.model_keys = list(model_keys)
        self.settings = settings
        self.infer = infer
        self.emit = emit
        self.should_stop = should_stop
        self.expected_calls = expected_calls
        self.events: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.actual_calls = 0
        self.had_error = False
        self.had_invalid = False
        self.stopped = False
        self.dependency_missing = False
        self.usage_complete = True
        self._ordinal = 0

    @property
    def cell_id(self) -> str:
        return f"{self.task_id}:{self.variant}"

    def mark_missing(self, reason: str) -> None:
        self.dependency_missing = True
        self.errors.append(reason)
        self.usage_complete = False

    def _next_message_id(self) -> str:
        self._ordinal += 1
        return f"{self.cell_id}:message-{self._ordinal}"

    @staticmethod
    def _request_hash(
        model_key: str, messages: list[dict[str, str]], settings: Mapping[str, Any]
    ) -> str:
        request = {
            "model_key": model_key,
            "messages": messages,
            "max_tokens": settings["max_tokens"],
            "temperature": settings["temperature"],
            "seed": settings["seed"],
        }
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self.emit(copy.deepcopy(event))

    def call(
        self,
        *,
        model_key: str,
        messages: list[dict[str, str]],
        role: str,
        kind: str,
        round_number: int,
        recipient: str,
        parent_ids: Sequence[str] = (),
        expires_round: int | None = None,
        actor: str,
        parser: Callable[[str], dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Make exactly one bounded callback call, or no call after cancellation."""
        if self.stopped or self.should_stop():
            self.stopped = True
            return None

        message_id = self._next_message_id()
        parent_ids_list = list(parent_ids)
        request_hash = self._request_hash(model_key, messages, self.settings_for(actor, round_number))
        start = time.monotonic()
        self.actual_calls += 1
        raw: Mapping[str, Any] | None = None
        try:
            response = self.infer(
                model_key,
                copy.deepcopy(messages),
                max_tokens=self.settings["max_tokens"],
                temperature=self.settings["temperature"],
                seed=self._seed_for(actor, round_number),
            )
            if not isinstance(response, Mapping):
                raise ValueError("infer returned a non-object response")
            raw = response
        except Exception as exc:
            elapsed = max(0.0, time.monotonic() - start)
            self.had_error = True
            error = str(exc) or exc.__class__.__name__
            self.errors.append(error)
            result = getattr(exc, "result", None)
            metadata = (
                _failed_response_metadata(result, elapsed, model_key)
                if isinstance(result, Mapping)
                else _unknown_failed_metadata(elapsed, model_key)
            )
            if not metadata["usage_complete"]:
                self.usage_complete = False
            self._publish(
                self._event(
                    message_id=message_id,
                    model_key=model_key,
                    role=role,
                    kind=kind,
                    round_number=round_number,
                    recipient=recipient,
                    parent_ids=parent_ids_list,
                    expires_round=expires_round,
                    messages=messages,
                    request_hash=request_hash,
                    content=metadata["content"],
                    payload=None,
                    parse_error=None,
                    response_id=metadata["response_id"],
                    requested_model=metadata["requested_model"],
                    served_model=metadata["served_model"],
                    prompt_tokens=metadata["prompt_tokens"],
                    completion_tokens=metadata["completion_tokens"],
                    elapsed_s=metadata["elapsed_s"],
                    finish_reason=metadata["finish_reason"],
                    usage_complete=metadata["usage_complete"],
                    error=error,
                )
            )
            return {
                "status": "error",
                "event": self.events[-1],
                "payload": None,
                "message_id": message_id,
            }

        wall_elapsed = max(0.0, time.monotonic() - start)
        try:
            metadata = self._response_metadata(raw, wall_elapsed, model_key)
        except ValueError as exc:
            self.had_error = True
            self.usage_complete = False
            error = str(exc)
            self.errors.append(error)
            self._publish(
                self._event(
                    message_id=message_id,
                    model_key=model_key,
                    role=role,
                    kind=kind,
                    round_number=round_number,
                    recipient=recipient,
                    parent_ids=parent_ids_list,
                    expires_round=expires_round,
                    messages=messages,
                    request_hash=request_hash,
                    content=raw.get("content") if isinstance(raw.get("content"), str) else None,
                    payload=None,
                    parse_error=None,
                    response_id=raw.get("response_id") if isinstance(raw.get("response_id"), str) else None,
                    requested_model=raw.get("requested_model") if isinstance(raw.get("requested_model"), str) else model_key,
                    served_model=raw.get("served_model") if isinstance(raw.get("served_model"), str) else None,
                    prompt_tokens=_known_nonnegative_int(raw.get("prompt_tokens")),
                    completion_tokens=_known_nonnegative_int(raw.get("completion_tokens")),
                    elapsed_s=wall_elapsed,
                    finish_reason=raw.get("finish_reason") if isinstance(raw.get("finish_reason"), str) else None,
                    usage_complete=False,
                    error=error,
                )
            )
            return {
                "status": "error",
                "event": self.events[-1],
                "payload": None,
                "message_id": message_id,
            }

        content = metadata["content"]
        payload: dict[str, Any] | None = None
        parse_error: str | None = None
        try:
            payload = parser(content)
        except (ValueError, TypeError, _PayloadError) as exc:
            parse_error = str(exc) or exc.__class__.__name__
            self.had_invalid = True
        event = self._event(
            message_id=message_id,
            model_key=model_key,
            role=role,
            kind=kind,
            round_number=round_number,
            recipient=recipient,
            parent_ids=parent_ids_list,
            expires_round=expires_round,
            messages=messages,
            request_hash=request_hash,
            content=content,
            payload=payload,
            parse_error=parse_error,
            response_id=metadata["response_id"],
            requested_model=metadata["requested_model"],
            served_model=metadata["served_model"],
            prompt_tokens=metadata["prompt_tokens"],
            completion_tokens=metadata["completion_tokens"],
            elapsed_s=metadata["elapsed_s"],
            finish_reason=metadata["finish_reason"],
            usage_complete=metadata["usage_complete"],
            error=None,
        )
        if not metadata["usage_complete"]:
            self.usage_complete = False
        self._publish(event)
        return {
            "status": "invalid" if parse_error else "ok",
            "event": event,
            "payload": payload,
            "message_id": message_id,
        }

    def settings_for(self, actor: str, round_number: int) -> dict[str, Any]:
        """Return request settings used in the hash, including the derived seed."""
        return {
            "max_tokens": self.settings["max_tokens"],
            "temperature": self.settings["temperature"],
            "seed": self._seed_for(actor, round_number),
        }

    def _seed_for(self, actor: str, round_number: int) -> int:
        material = f"{self.task_id}\x1f{self.protocol}\x1f{actor}\x1f{round_number}".encode("utf-8")
        offset = int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % (_MAX_SEED + 1)
        return (self.settings["seed"] + offset) % (_MAX_SEED + 1)

    @staticmethod
    def _response_metadata(
        raw: Mapping[str, Any] | None, wall_elapsed: float, model_key: str
    ) -> dict[str, Any]:
        if raw is None:
            raise ValueError("infer returned no response")
        content = raw.get("content")
        if not isinstance(content, str):
            raise ValueError("infer response content must be a string")
        response_id = raw.get("response_id")
        if not isinstance(response_id, str) or not response_id:
            raise ValueError("infer response_id must be a non-empty string")
        requested = raw.get("requested_model")
        if not isinstance(requested, str) or not requested:
            raise ValueError("infer requested_model must be a non-empty string")
        if requested != model_key:
            raise ValueError("infer requested_model does not match model_key")
        served = raw.get("served_model")
        if not isinstance(served, str) or not served:
            raise ValueError("infer served_model must be a non-empty string")
        finish_reason = raw.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason:
            raise ValueError("infer finish_reason must be a non-empty string")
        if finish_reason in {"length", "max_tokens", "truncated"}:
            raise ValueError("infer response was truncated")

        prompt_tokens = _known_nonnegative_int(raw.get("prompt_tokens"))
        completion_tokens = _known_nonnegative_int(raw.get("completion_tokens"))
        elapsed_value = raw.get("elapsed_s")
        elapsed_valid = _finite_nonnegative_number(elapsed_value)
        elapsed_s = float(elapsed_value) if elapsed_valid else wall_elapsed
        usage_complete = (
            prompt_tokens is not None
            and completion_tokens is not None
            and elapsed_valid
        )
        return {
            "content": content,
            "response_id": response_id,
            "requested_model": requested,
            "served_model": served,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_s": elapsed_s,
            "finish_reason": finish_reason,
            "usage_complete": usage_complete,
        }

    def _event(self, **fields: Any) -> dict[str, Any]:
        return {
            "message_id": fields["message_id"],
            "task_id": self.task_id,
            "protocol": self.protocol,
            "model_key": fields["model_key"],
            "requested_model": fields["requested_model"],
            "served_model": fields["served_model"],
            "role": fields["role"],
            "kind": fields["kind"],
            "round": fields["round_number"],
            "recipient": fields["recipient"],
            "parent_ids": list(fields["parent_ids"]),
            "expires_round": fields["expires_round"],
            "prompt_messages": copy.deepcopy(fields["messages"]),
            "content": fields["content"],
            "payload": copy.deepcopy(fields["payload"]),
            "parse_error": fields["parse_error"],
            "response_id": fields["response_id"],
            "request_hash": fields["request_hash"],
            "prompt_tokens": fields["prompt_tokens"],
            "completion_tokens": fields["completion_tokens"],
            "elapsed_s": fields["elapsed_s"],
            "finish_reason": fields["finish_reason"],
            "usage_complete": fields["usage_complete"],
            "error": fields["error"],
        }



def _failed_response_metadata(
    raw: Mapping[str, Any], wall_elapsed: float, model_key: str
) -> dict[str, Any]:
    """Keep safe public fields from a provider error's returned result."""
    content = raw.get("content") if isinstance(raw.get("content"), str) else None
    requested = raw.get("requested_model") if isinstance(raw.get("requested_model"), str) else model_key
    served = raw.get("served_model") if isinstance(raw.get("served_model"), str) else None
    response_id = raw.get("response_id") if isinstance(raw.get("response_id"), str) else None
    prompt_tokens = _known_nonnegative_int(raw.get("prompt_tokens"))
    completion_tokens = _known_nonnegative_int(raw.get("completion_tokens"))
    elapsed_value = raw.get("elapsed_s")
    elapsed_valid = _finite_nonnegative_number(elapsed_value)
    return {
        "content": content,
        "response_id": response_id,
        "requested_model": requested,
        "served_model": served,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "elapsed_s": float(elapsed_value) if elapsed_valid else wall_elapsed,
        "finish_reason": raw.get("finish_reason") if isinstance(raw.get("finish_reason"), str) else None,
        "usage_complete": prompt_tokens is not None and completion_tokens is not None and elapsed_valid,
    }


def _unknown_failed_metadata(elapsed: float, model_key: str) -> dict[str, Any]:
    return {
        "content": None,
        "response_id": None,
        "requested_model": model_key,
        "served_model": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "elapsed_s": elapsed,
        "finish_reason": None,
        "usage_complete": False,
    }


def public_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the allowlisted model-facing task view without evaluator labels."""
    _validate_task(task)
    return {
        "task_id": task["task_id"],
        "source_id": task["source_id"],
        "dataset": task["dataset"],
        "domain": task["domain"],
        "split": task["split"],
        "question": task["question"],
        "evidence": [
            {"id": evidence["id"], "text": evidence["text"]}
            for evidence in task["evidence"]
        ],
        "answer_type": task["answer_type"],
        "choices": list(task["choices"]),
        "source_url": task["source_url"],
    }


def estimate_calls(task_count: int, model_count: int, protocols: Sequence[str]) -> int:
    """Calculate intended inference calls without contacting any provider."""
    if not _is_int(task_count) or task_count < 0:
        raise ValueError("task_count must be a nonnegative integer")
    if not _is_int(model_count) or model_count < 0:
        raise ValueError("model_count must be a nonnegative integer")
    selected = _validate_protocols(protocols)
    per_task = sum(1 if protocol == "single" else 3 for protocol in selected)
    return task_count * model_count * per_task


def run_task(
    task: Mapping[str, Any],
    model_keys: Sequence[str],
    protocol: str,
    settings: Mapping[str, Any],
    infer: Callable[..., Mapping[str, Any]],
    emit: Callable[[dict[str, Any]], Any],
    should_stop: Callable[[], bool],
) -> list[dict[str, Any]]:
    """Run one task under one protocol using only caller-supplied callbacks."""
    _validate_task(task)
    models = _validate_model_keys(model_keys)
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol: {protocol!r}")
    normalized_settings = _validate_settings(settings)
    if not callable(infer) or not callable(emit) or not callable(should_stop):
        raise ValueError("infer, emit, and should_stop must be callable")

    if protocol == "single":
        return [
            _run_single(
                task,
                model_key,
                normalized_settings,
                infer,
                emit,
                should_stop,
            )
            for model_key in models
        ]

    expected_calls = len(models) * 3
    execution = _Execution(
        task=task,
        protocol=protocol,
        variant=protocol,
        model_keys=models,
        settings=normalized_settings,
        infer=infer,
        emit=emit,
        should_stop=should_stop,
        expected_calls=expected_calls,
    )
    if protocol == "independent_vote":
        answer, _ = _run_independent_vote(execution)
    elif protocol == "peer_review":
        answer, _ = _run_peer_review(execution)
    else:
        answer, _ = _run_signal_board(execution)
    return [_finish_cell(execution, answer)]


def summarize(
    cells: Sequence[Mapping[str, Any]], target_accuracy: float, min_cases: int = 30
) -> list[dict[str, Any]]:
    """Summarize task cells by domain and protocol variant with honest gates."""
    if not _finite_number(target_accuracy) or not 0 <= float(target_accuracy) <= 1:
        raise ValueError("target_accuracy must be a finite number between 0 and 1")
    if not _is_int(min_cases) or min_cases < 1:
        raise ValueError("min_cases must be a positive integer")
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
        raise ValueError("cells must be a sequence")

    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for cell in cells:
        if not isinstance(cell, Mapping):
            raise ValueError("each cell must be an object")
        domain = cell.get("domain")
        variant = cell.get("variant")
        if not isinstance(domain, str) or not isinstance(variant, str):
            raise ValueError("cell domain and variant must be strings")
        groups.setdefault((domain, variant), []).append(cell)

    rows: list[dict[str, Any]] = []
    for (domain, variant), group in sorted(groups.items()):
        task_count = len(group)
        completed_count = sum(cell.get("status") == "completed" for cell in group)
        error_count = sum(cell.get("status") == "error" for cell in group)
        abstained_count = sum(cell.get("status") == "abstained" for cell in group)
        invalid_count = sum(cell.get("status") == "invalid" for cell in group)
        correct_count = sum(cell.get("correct") is True for cell in group)
        valid_answered = sum(
            cell.get("status") == "completed" and cell.get("answer") is not None
            for cell in group
        )
        model_roster: list[str] = []
        for cell in group:
            for model_key in cell.get("model_keys", []):
                if model_key not in model_roster:
                    model_roster.append(model_key)
        coverage = valid_answered / task_count if task_count else None
        task_success_rate = correct_count / task_count if task_count else None
        answered_accuracy = correct_count / valid_answered if valid_answered else None
        wilson = _wilson_lower_95(correct_count, task_count)
        usage_complete = all(cell.get("usage_complete") is True for cell in group)
        if error_count or invalid_count or not valid_answered:
            gate = "unknown"
        elif task_count < min_cases:
            gate = "insufficient_evidence"
        elif wilson is not None and wilson >= float(target_accuracy):
            gate = "meets_sample_target"
        else:
            gate = "below_target"
        first = group[0]
        rows.append(
            {
                "domain": domain,
                "variant": variant,
                "protocol": first.get("protocol"),
                "model_keys": model_roster,
                "task_count": task_count,
                "completed_count": completed_count,
                "correct_count": correct_count,
                "error_count": error_count,
                "abstained_count": abstained_count,
                "invalid_count": invalid_count,
                "coverage": coverage,
                "task_success_rate": task_success_rate,
                "answered_accuracy": answered_accuracy,
                "wilson_lower_95": wilson,
                "gate": gate,
                "target_accuracy": float(target_accuracy),
                "min_cases": min_cases,
                "call_count": sum(_nonnegative_int_or_zero(cell.get("call_count")) for cell in group),
                "prompt_tokens": sum(_nonnegative_int_or_zero(cell.get("prompt_tokens")) for cell in group),
                "completion_tokens": sum(_nonnegative_int_or_zero(cell.get("completion_tokens")) for cell in group),
                "elapsed_s": sum(_finite_nonnegative_or_zero(cell.get("elapsed_s")) for cell in group),
                "usage_complete": usage_complete,
            }
        )
    return rows


def _run_single(
    task: Mapping[str, Any],
    model_key: str,
    settings: Mapping[str, Any],
    infer: Callable[..., Mapping[str, Any]],
    emit: Callable[[dict[str, Any]], Any],
    should_stop: Callable[[], bool],
) -> dict[str, Any]:
    execution = _Execution(
        task=task,
        protocol="single",
        variant=f"single:{model_key}",
        model_keys=[model_key],
        settings=settings,
        infer=infer,
        emit=emit,
        should_stop=should_stop,
        expected_calls=1,
    )
    outcome = execution.call(
        model_key=model_key,
        messages=_answer_messages(task),
        role="solver",
        kind="claim",
        round_number=0,
        recipient="none",
        actor=model_key,
        parser=lambda content: _parse_answer(content, task),
    )
    answer = outcome["payload"]["answer"] if outcome and outcome["status"] == "ok" else None
    return _finish_cell(execution, answer)


def _run_independent_vote(execution: _Execution) -> tuple[str | None, list[dict[str, Any]]]:
    ballots: list[dict[str, Any]] = []
    for model_key in execution.model_keys:
        for sample in range(3):
            if execution.stopped:
                break
            outcome = execution.call(
                model_key=model_key,
                messages=_answer_messages(execution.task),
                role="solver",
                kind="claim",
                round_number=0,
                recipient="none",
                actor=f"{model_key}:sample:{sample}",
                parser=lambda content, task=execution.task: _parse_answer(content, task),
            )
            if outcome is not None:
                ballots.append(outcome)
        if execution.stopped:
            break
    if execution.had_error or execution.dependency_missing or execution.actual_calls < execution.expected_calls:
        if execution.actual_calls < execution.expected_calls:
            execution.mark_missing("required independent ballot was not called")
        return None, ballots
    if execution.had_invalid:
        return None, ballots
    answers = [outcome["payload"]["answer"] for outcome in ballots if outcome["status"] == "ok"]
    return _strict_majority(execution.task, answers, execution.expected_calls), ballots


def _run_peer_review(execution: _Execution) -> tuple[str | None, list[dict[str, Any]]]:
    models = execution.model_keys
    initials: list[dict[str, Any] | None] = []
    for model_key in models:
        if execution.stopped:
            break
        initials.append(
            execution.call(
                model_key=model_key,
                messages=_answer_messages(execution.task),
                role="solver",
                kind="claim",
                round_number=0,
                recipient="none",
                actor=f"{model_key}:initial",
                parser=lambda content, task=execution.task: _parse_answer(content, task),
            )
        )
    while len(initials) < len(models):
        initials.append(None)

    critiques: list[dict[str, Any] | None] = [None] * len(models)
    for index, model_key in enumerate(models):
        target_index = (index + 1) % len(models)
        target = initials[target_index]
        if execution.stopped:
            break
        if target is None or target.get("status") != "ok":
            execution.mark_missing("required peer claim was unavailable for critique")
            continue
        target_event = target["event"]
        target_payload = target["payload"]
        critique_messages = _critique_messages(execution.task, target_event, target_payload)
        critiques[index] = execution.call(
            model_key=model_key,
            messages=critique_messages,
            role="critic",
            kind="critique",
            round_number=1,
            recipient=models[target_index],
            parent_ids=[target_event["message_id"]],
            actor=f"{model_key}:critique:{target_event['message_id']}",
            parser=lambda content, target_id=target_event["message_id"], task=execution.task: _parse_critique(
                content, task, target_id
            ),
        )
    revisions: list[dict[str, Any] | None] = [None] * len(models)
    for index, model_key in enumerate(models):
        if execution.stopped:
            break
        initial = initials[index]
        own_critique = critiques[(index - 1) % len(models)]
        if initial is None or initial.get("status") != "ok":
            execution.mark_missing("required peer claim was unavailable for revision")
            continue
        if own_critique is None or own_critique.get("status") != "ok":
            execution.mark_missing("required critique was unavailable for revision")
            continue
        peer_proposals = []
        for peer_index, proposal in enumerate(initials):
            if peer_index == index or proposal is None or proposal.get("status") != "ok":
                continue
            peer_proposals.append(_proposal_view(models[peer_index], proposal))
        initial_event = initial["event"]
        critique_event = own_critique["event"]
        revision_messages = _revision_messages(
            execution.task,
            _proposal_view(model_key, initial),
            {
                "message_id": critique_event["message_id"],
                "model_key": models[(index - 1) % len(models)],
                "payload": own_critique["payload"],
                "content": critique_event["content"],
            },
            peer_proposals,
        )
        revisions[index] = execution.call(
            model_key=model_key,
            messages=revision_messages,
            role="solver",
            kind="revision",
            round_number=2,
            recipient="none",
            parent_ids=[initial_event["message_id"], critique_event["message_id"]]
            + [proposal["message_id"] for proposal in peer_proposals],
            actor=f"{model_key}:revision",
            parser=lambda content, task=execution.task: _parse_answer(content, task),
        )

    if execution.stopped or execution.actual_calls < execution.expected_calls:
        if execution.actual_calls < execution.expected_calls:
            execution.mark_missing("required peer-review call was not called")
        return None, [outcome for outcome in revisions if outcome is not None]
    if execution.had_error:
        return None, [outcome for outcome in revisions if outcome is not None]
    if execution.had_invalid:
        return None, [outcome for outcome in revisions if outcome is not None]
    final_answers = [outcome["payload"]["answer"] for outcome in revisions if outcome and outcome["status"] == "ok"]
    return _strict_majority(execution.task, final_answers, len(models)), [outcome for outcome in revisions if outcome]


def _run_signal_board(execution: _Execution) -> tuple[str | None, list[dict[str, Any]]]:
    models = execution.model_keys
    board: list[dict[str, Any]] = []
    latest: dict[str, dict[str, Any]] = {}
    revisions: list[dict[str, Any] | None] = [None] * len(models)

    for model_key in models:
        if execution.stopped:
            break
        outcome = execution.call(
            model_key=model_key,
            messages=_answer_messages(execution.task),
            role="solver",
            kind="claim",
            round_number=0,
            recipient="board",
            expires_round=1,
            actor=f"{model_key}:board:0",
            parser=lambda content, task=execution.task: _parse_answer(content, task),
        )
        if outcome and outcome["status"] == "ok":
            signal = _signal_view(model_key, outcome)
            board.append(signal)
            latest[model_key] = signal

    for round_number in (1, 2):
        if execution.stopped:
            break
        # Freeze the previous round before any actor writes this round.  Only
        # one-round-old signals are active; this is the TTL board boundary.
        snapshot = [
            signal
            for signal in board
            if signal["task_id"] == execution.task_id
            and signal["round"] == round_number - 1
            and signal["expires_round"] >= round_number
        ][: len(models)]
        for index, model_key in enumerate(models):
            if execution.stopped:
                break
            previous = latest.get(model_key)
            if previous is None:
                execution.mark_missing("required board signal was unavailable for revision")
                continue
            relevant = [signal for signal in snapshot if signal["model_key"] != model_key][: len(models)]
            messages = _board_messages(execution.task, round_number, relevant)
            parent_ids = [previous["message_id"]] + [signal["message_id"] for signal in relevant]
            outcome = execution.call(
                model_key=model_key,
                messages=messages,
                role="solver",
                kind="revision",
                round_number=round_number,
                recipient="board",
                parent_ids=parent_ids,
                expires_round=round_number + 1,
                actor=f"{model_key}:board:{round_number}",
                parser=lambda content, task=execution.task: _parse_answer(content, task),
            )
            revisions[index] = outcome
            if outcome and outcome["status"] == "ok":
                signal = _signal_view(model_key, outcome)
                board.append(signal)
                latest[model_key] = signal

    if execution.stopped or execution.actual_calls < execution.expected_calls:
        if execution.actual_calls < execution.expected_calls:
            execution.mark_missing("required board call was not called")
        return None, [outcome for outcome in revisions if outcome]
    if execution.had_error:
        return None, [outcome for outcome in revisions if outcome]
    if execution.had_invalid:
        return None, [outcome for outcome in revisions if outcome]
    final_answers = [outcome["payload"]["answer"] for outcome in revisions if outcome and outcome["status"] == "ok"]
    return _strict_majority(execution.task, final_answers, len(models)), [outcome for outcome in revisions if outcome]


def _finish_cell(execution: _Execution, answer: str | None) -> dict[str, Any]:
    missing = execution.actual_calls < execution.expected_calls or execution.dependency_missing
    if execution.had_error or execution.stopped:
        status = "error"
        answer = None
        error = execution.errors[0] if execution.errors else "required call failed"
    elif execution.had_invalid:
        status = "invalid"
        answer = None
        error = next(
            (event["parse_error"] for event in execution.events if event.get("parse_error")),
            "invalid model output",
        )
    elif missing:
        status = "error"
        answer = None
        error = execution.errors[0] if execution.errors else "required call failed"
    elif answer is None:
        status = "abstained"
        error = None
    else:
        status = "completed"
        error = None

    correct = _score_answer(execution.task, answer) if status == "completed" else None
    return {
        "cell_id": execution.cell_id,
        "task_id": execution.task["task_id"],
        "dataset": execution.task["dataset"],
        "domain": execution.task["domain"],
        "variant": execution.variant,
        "protocol": execution.protocol,
        "model_keys": list(execution.model_keys),
        "status": status,
        "answer": answer,
        "expected_answer": execution.task["expected_answer"],
        "correct": correct,
        "instruction_compliant": not execution.had_error and not execution.had_invalid and not missing,
        "call_count": execution.actual_calls,
        "prompt_tokens": sum(
            event["prompt_tokens"] for event in execution.events if isinstance(event["prompt_tokens"], int)
        ),
        "completion_tokens": sum(
            event["completion_tokens"] for event in execution.events if isinstance(event["completion_tokens"], int)
        ),
        "elapsed_s": sum(float(event["elapsed_s"]) for event in execution.events),
        "messages": copy.deepcopy(execution.events),
        "error": error,
        "usage_complete": execution.usage_complete and not missing,
    }


def _answer_messages(task: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {"role": "user", "content": _json_text({"task": public_task(task), "instruction": "Solve independently."})},
    ]


def _critique_messages(
    task: Mapping[str, Any], target_event: Mapping[str, Any], target_payload: Mapping[str, Any]
) -> list[dict[str, str]]:
    target = {
        "message_id": target_event["message_id"],
        "model_key": target_event["model_key"],
        "payload": dict(target_payload),
        "content": target_event["content"],
    }
    return [
        {"role": "system", "content": _CRITIQUE_SYSTEM},
        {
            "role": "user",
            "content": _json_text(
                {
                    "task": public_task(task),
                    "target": target,
                    "instruction": "Assess the named claim using only the supplied task and evidence.",
                }
            ),
        },
    ]


def _revision_messages(
    task: Mapping[str, Any],
    own_initial: Mapping[str, Any],
    own_critique: Mapping[str, Any],
    peer_proposals: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {
            "role": "user",
            "content": _json_text(
                {
                    "task": public_task(task),
                    "own_initial": dict(own_initial),
                    "own_critique": dict(own_critique),
                    "peer_proposals": peer_proposals,
                    "instruction": "Revise your named answer after consuming the named critique and proposals.",
                }
            ),
        },
    ]


def _board_messages(
    task: Mapping[str, Any], round_number: int, signals: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {
            "role": "user",
            "content": _json_text(
                {
                    "task": public_task(task),
                    "round": round_number,
                    "signals": [
                        {
                            "message_id": signal["message_id"],
                            "model_key": signal["model_key"],
                            "kind": signal["kind"],
                            "round": signal["round"],
                            "payload": signal["payload"],
                            "content": signal["content"],
                        }
                        for signal in signals
                    ],
                    "instruction": "Use this bounded snapshot of other-agent signals; then answer independently.",
                }
            ),
        },
    ]


def _proposal_view(model_key: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
    event = outcome["event"]
    return {
        "message_id": event["message_id"],
        "model_key": model_key,
        "payload": dict(outcome["payload"]),
        "content": event["content"],
    }


def _signal_view(model_key: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
    event = outcome["event"]
    return {
        "task_id": event["task_id"],
        "message_id": event["message_id"],
        "model_key": model_key,
        "kind": event["kind"],
        "round": event["round"],
        "expires_round": event["expires_round"],
        "payload": dict(outcome["payload"]),
        "content": event["content"],
    }


def _parse_answer(content: str, task: Mapping[str, Any]) -> dict[str, Any]:
    payload = _strict_object(content, _ANSWER_FIELDS)
    answer = payload["answer"]
    if answer is not None and not isinstance(answer, str):
        raise _PayloadError("answer must be a string or null")
    evidence_ids = payload["evidence_ids"]
    _validate_evidence_ids(evidence_ids, task)
    brief = payload["brief"]
    if not isinstance(brief, str):
        raise _PayloadError("brief must be a string")
    if len(brief) > 500:
        raise _PayloadError("brief exceeds 500 characters")
    if answer is not None:
        if task["answer_type"] == "choice":
            if answer not in task["choices"]:
                raise _PayloadError("choice answer is not one of the provided choices")
        else:
            _parse_decimal_string(answer, "decimal answer")
    return {"answer": answer, "evidence_ids": list(evidence_ids), "brief": brief}


def _parse_critique(content: str, task: Mapping[str, Any], target_id: str) -> dict[str, Any]:
    payload = _strict_object(content, _CRITIQUE_FIELDS)
    if payload["target_message_id"] != target_id:
        raise _PayloadError("critique target_message_id does not name the requested claim")
    if payload["assessment"] not in {"supported", "unsupported", "unclear"}:
        raise _PayloadError("assessment must be supported, unsupported, or unclear")
    _validate_evidence_ids(payload["evidence_ids"], task)
    if not isinstance(payload["brief"], str):
        raise _PayloadError("brief must be a string")
    if len(payload["brief"]) > 500:
        raise _PayloadError("brief exceeds 500 characters")
    return {
        "target_message_id": payload["target_message_id"],
        "assessment": payload["assessment"],
        "evidence_ids": list(payload["evidence_ids"]),
        "brief": payload["brief"],
    }


def _strict_object(content: str, expected_fields: set[str]) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise _PayloadError("response must be a non-empty bare JSON object")
    try:
        parsed = json.loads(
            content.strip(),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON constant: {value}")),
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise _PayloadError(f"response is not strict JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise _PayloadError("response must be a JSON object")
    if set(parsed) != expected_fields:
        missing = sorted(expected_fields - set(parsed))
        extra = sorted(set(parsed) - expected_fields)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("extra " + ", ".join(extra))
        raise _PayloadError("payload fields are not exact: " + "; ".join(details))
    return parsed


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _validate_evidence_ids(value: Any, task: Mapping[str, Any]) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _PayloadError("evidence_ids must be a list of strings")
    if len(set(value)) != len(value):
        raise _PayloadError("evidence_ids must not contain duplicates")
    known = {evidence["id"] for evidence in task["evidence"]}
    foreign = [item for item in value if item not in known]
    if foreign:
        raise _PayloadError("evidence_ids contains a foreign evidence ID")


def _strict_majority(
    task: Mapping[str, Any], answers: Sequence[str | None], expected_ballots: int
) -> str | None:
    counts: dict[tuple[str, Any], int] = {}
    representative: dict[tuple[str, Any], str] = {}
    for answer in answers:
        if answer is None:
            continue
        key = _answer_key(task, answer)
        counts[key] = counts.get(key, 0) + 1
        representative.setdefault(key, answer)
    winners = [key for key, count in counts.items() if count * 2 > expected_ballots]
    if len(winners) != 1:
        return None
    return representative[winners[0]]


def _answer_key(task: Mapping[str, Any], answer: str) -> tuple[str, Any]:
    if task["answer_type"] == "choice":
        return ("choice", answer)
    return ("decimal", _parse_decimal_string(answer, "decimal answer"))


def _score_answer(task: Mapping[str, Any], answer: str | None) -> bool | None:
    if answer is None:
        return None
    if task["answer_type"] == "choice":
        return answer == task["expected_answer"]
    return abs(
        _parse_decimal_string(answer, "decimal answer")
        - _parse_decimal_string(task["expected_answer"], "expected answer")
    ) <= _parse_decimal_string(task["tolerance"], "tolerance")


def _parse_decimal_string(value: Any, label: str) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{label} must be a finite decimal string")
    try:
        decimal = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal string") from exc
    if not decimal.is_finite():
        raise ValueError(f"{label} must be finite")
    return decimal


def _validate_task(task: Mapping[str, Any]) -> None:
    if not isinstance(task, Mapping):
        raise ValueError("task must be an object")
    missing = [field for field in _TASK_FIELDS if field not in task]
    if missing:
        raise ValueError("task missing required fields: " + ", ".join(missing))
    for field in ("task_id", "source_id", "question", "source_url"):
        if not isinstance(task[field], str) or not task[field]:
            raise ValueError(f"task {field} must be a non-empty string")
    dataset = task["dataset"]
    domain = task["domain"]
    if dataset not in {"pubmedqa", "finqa"}:
        raise ValueError("task dataset must be pubmedqa or finqa")
    if domain not in {"medical", "finance"}:
        raise ValueError("task domain must be medical or finance")
    if (dataset, domain) not in {("pubmedqa", "medical"), ("finqa", "finance")}:
        raise ValueError("task dataset and domain do not match")
    if task["split"] not in {"development", "evaluation"}:
        raise ValueError("task split must be development or evaluation")
    if task["answer_type"] not in {"choice", "decimal"}:
        raise ValueError("task answer_type must be choice or decimal")
    if (domain, task["answer_type"]) not in {("medical", "choice"), ("finance", "decimal")}:
        raise ValueError("task answer_type does not match domain")
    evidence = task["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("task evidence must be a list")
    seen_ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, Mapping):
            raise ValueError("each evidence item must be an object")
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("evidence id must be a non-empty string")
        if not isinstance(item.get("text"), str):
            raise ValueError("evidence text must be a string")
        if item["id"] in seen_ids:
            raise ValueError("evidence IDs must be unique")
        seen_ids.add(item["id"])
    choices = task["choices"]
    if not isinstance(choices, list) or any(not isinstance(choice, str) for choice in choices):
        raise ValueError("task choices must be a list of strings")
    if task["answer_type"] == "choice":
        if not choices or len(set(choices)) != len(choices):
            raise ValueError("choice tasks need unique non-empty choices")
        if not isinstance(task["expected_answer"], str) or task["expected_answer"] not in choices:
            raise ValueError("expected choice must be one of choices")
    else:
        if choices:
            raise ValueError("decimal tasks must have an empty choices list")
        _parse_decimal_string(task["expected_answer"], "expected answer")
    _parse_decimal_string(task["tolerance"], "tolerance")
    if _parse_decimal_string(task["tolerance"], "tolerance") < 0:
        raise ValueError("tolerance must be nonnegative")


def _validate_protocols(protocols: Sequence[str]) -> list[str]:
    if not isinstance(protocols, Sequence) or isinstance(protocols, (str, bytes)):
        raise ValueError("protocols must be a sequence")
    selected = list(protocols)
    if len(set(selected)) != len(selected):
        raise ValueError("protocols must not contain duplicates")
    unknown = [protocol for protocol in selected if protocol not in PROTOCOLS]
    if unknown:
        raise ValueError(f"unknown protocol: {unknown[0]!r}")
    return selected


def _validate_model_keys(model_keys: Sequence[str]) -> list[str]:
    if not isinstance(model_keys, Sequence) or isinstance(model_keys, (str, bytes)):
        raise ValueError("model_keys must be a sequence")
    models = list(model_keys)
    if not models or any(not isinstance(model, str) or not model for model in models):
        raise ValueError("model_keys must contain non-empty strings")
    if len(set(models)) != len(models):
        raise ValueError("model_keys must be unique")
    return models


def _validate_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, Mapping):
        raise ValueError("settings must be an object")
    for key in ("temperature", "seed", "max_tokens"):
        if key not in settings:
            raise ValueError(f"settings missing {key}")
    temperature = settings["temperature"]
    if not _finite_number(temperature) or not 0 <= float(temperature) <= 1:
        raise ValueError("temperature must be a finite number between 0 and 1")
    seed = settings["seed"]
    if not _is_int(seed) or not 0 <= seed <= _MAX_SEED:
        raise ValueError("seed must be an integer between 0 and 2147483647")
    max_tokens = settings["max_tokens"]
    if not _is_int(max_tokens) or not 64 <= max_tokens <= 512:
        raise ValueError("max_tokens must be an integer between 64 and 512")
    return {"temperature": float(temperature), "seed": seed, "max_tokens": max_tokens}


def _wilson_lower_95(successes: int, trials: int) -> float | None:
    if trials <= 0:
        return None
    z = 1.6448536269514722
    n = float(trials)
    p = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = p + z2 / (2 * n)
    spread = z * math.sqrt((p * (1 - p) / n) + (z2 / (4 * n * n)))
    return (center - spread) / denominator


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _finite_nonnegative_number(value: Any) -> bool:
    return _finite_number(value) and float(value) >= 0


def _known_nonnegative_int(value: Any) -> int | None:
    return value if _is_int(value) and value >= 0 else None


def _nonnegative_int_or_zero(value: Any) -> int:
    known = _known_nonnegative_int(value)
    return known if known is not None else 0


def _finite_nonnegative_or_zero(value: Any) -> float:
    return float(value) if _finite_nonnegative_number(value) else 0.0


_ANSWER_SYSTEM = (
    "Answer the task using the supplied evidence. Return exactly one bare JSON object "
    "with exactly these fields: answer, evidence_ids, brief. The answer is a literal "
    "choice or a finite decimal string, or null to abstain. evidence_ids must name "
    "only supplied evidence. brief is a short public rationale of at most 500 characters. "
    "Do not use code fences, extra prose, or private chain-of-thought."
)
_CRITIQUE_SYSTEM = (
    "Assess the named peer claim using the supplied task and evidence. Return exactly "
    "one bare JSON object with exactly these fields: target_message_id, assessment, "
    "evidence_ids, brief. assessment must be supported, unsupported, or unclear. "
    "evidence_ids must name only supplied evidence; brief is at most 500 characters. "
    "Do not use code fences, extra prose, or private chain-of-thought."
)


__all__ = ["PROTOCOLS", "estimate_calls", "public_task", "run_task", "summarize"]
