"""Focused contract tests for the provider-free swarm research kernel."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from backend.swarm_core import (
    PROTOCOLS,
    build_response_format,
    estimate_calls,
    public_task,
    run_task,
    summarize,
)


SETTINGS = {"temperature": 0.2, "seed": 17, "max_tokens": 128}


def task(*, expected: str = "A", answer_type: str = "choice", domain: str = "medical") -> dict[str, Any]:
    return {
        "task_id": "task-1",
        "source_id": "source-1",
        "dataset": "pubmedqa" if domain == "medical" else "finqa",
        "domain": domain,
        "split": "development",
        "question": "Which option is supported?" if answer_type == "choice" else "What is the result in dollars?",
        "evidence": [{"id": "e1", "text": "The evidence supports option A."}],
        "answer_type": answer_type,
        "choices": ["A", "B"] if answer_type == "choice" else [],
        "expected_answer": expected,
        "tolerance": "0.01",
        "source_url": "https://example.test/source-1",
    }


def response(model: str, content: str, *, seed: int, elapsed: float = 0.01) -> dict[str, Any]:
    return {
        "content": content,
        "response_id": f"resp-{model}-{seed}",
        "requested_model": model,
        "served_model": model,
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "elapsed_s": elapsed,
        "finish_reason": "stop",
    }


def test_public_task_excludes_evaluator_labels_and_call_budget_is_equalized():
    safe = public_task(task())

    assert "expected_answer" not in safe
    assert "tolerance" not in safe
    assert safe["question"] == task()["question"]
    assert set(PROTOCOLS) == {"single", "independent_vote", "peer_review", "signal_board", "evidence_exchange", "evidence_isolated", "solo_refine", "evidence_sources"}
    assert estimate_calls(2, 2, PROTOCOLS) == 136


def test_single_uses_explicit_settings_and_never_sends_gold():
    calls: list[tuple[str, list[dict[str, str]], dict[str, Any]]] = []
    emitted: list[dict[str, Any]] = []

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        calls.append((model, messages, kwargs))
        return response(model, '{"answer":"A","evidence_ids":["e1"],"brief":"supported"}', seed=kwargs["seed"])

    cells = run_task(task(), ["m1"], "single", SETTINGS, infer, emitted.append, lambda: False)

    assert len(cells) == 1
    assert cells[0]["status"] == "completed"
    assert cells[0]["correct"] is True
    assert cells[0]["usage_complete"] is True
    assert calls[0][2]["max_tokens"] == SETTINGS["max_tokens"]
    assert calls[0][2]["temperature"] == SETTINGS["temperature"]
    assert isinstance(calls[0][2]["seed"], int)
    prompt = json.dumps(calls[0][1])
    assert "expected_answer" not in prompt
    assert "tolerance" not in prompt
    assert emitted == cells[0]["messages"]


def test_constrained_short_binds_a_role_local_schema_to_the_sent_prompt_and_event():
    calls: list[tuple[str, list[dict[str, str]], dict[str, Any]]] = []

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        calls.append((model, messages, kwargs))
        return response(model, '{"answer":"A","evidence_ids":["e1"],"brief":"supported"}', seed=kwargs["seed"])

    constrained = run_task(
        task(),
        ["m1"],
        "single",
        SETTINGS,
        infer,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]

    response_format = calls[0][2]["response_format"]
    schema = response_format["json_schema"]["schema"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "swarm_reply"
    assert response_format["json_schema"]["strict"] is True
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["answer", "evidence_ids", "brief"]
    assert schema["properties"]["answer"]["enum"] == ["A", "B", None]
    assert schema["properties"]["evidence_ids"]["items"]["enum"] == ["e1"]
    assert schema["properties"]["evidence_ids"]["maxItems"] == 3
    assert "uniqueItems" not in schema["properties"]["evidence_ids"]
    assert schema["properties"]["brief"]["maxLength"] == 160
    assert "160" in calls[0][1][0]["content"]
    assert "3" in calls[0][1][0]["content"]
    event = constrained["messages"][0]
    assert event["output_policy"] == "constrained_short_v1"
    assert event["response_format"] == response_format
    assert event["prompt_messages"] == calls[0][1]
    assert event["request_hash"]

    prompt_only = run_task(task(), ["m1"], "single", SETTINGS, infer, lambda event: None, lambda: False)[0]
    assert "response_format" not in calls[1][2]
    assert prompt_only["messages"][0]["output_policy"] == "prompt_only"
    assert prompt_only["messages"][0]["response_format"] is None
    assert prompt_only["messages"][0]["request_hash"] != event["request_hash"]


def test_constrained_short_schema_types_decimal_answers_and_peer_critiques_exactly():
    decimal_schema = build_response_format(
        task(expected="100.00", answer_type="decimal", domain="finance"),
        kind="claim",
        output_policy="constrained_short_v1",
    )["json_schema"]["schema"]
    decimal_answer = decimal_schema["properties"]["answer"]
    assert decimal_answer["type"] == ["string", "null"]
    assert decimal_answer["maxLength"] == 26
    assert decimal_answer["pattern"] == r"^[+-]?[0-9]{1,16}(\.[0-9]{1,8})?$"
    assert "expected_answer" not in json.dumps(decimal_schema)
    assert "tolerance" not in json.dumps(decimal_schema)

    critique_schema = build_response_format(
        task(),
        kind="critique",
        target_message_id="task-1:message-1",
        output_policy="constrained_short_v1",
    )["json_schema"]["schema"]
    assert "answer" not in critique_schema["properties"]
    assert critique_schema["properties"]["target_message_id"]["enum"] == ["task-1:message-1"]
    assert critique_schema["properties"]["assessment"]["enum"] == ["supported", "unsupported", "unclear"]
    assert critique_schema["additionalProperties"] is False


@pytest.mark.parametrize("answer", ["12345678901234567", "1.123456789", ".123"])
def test_constrained_short_rejects_decimal_outside_bounded_grammar(answer: str):
    decimal_task = task(expected="100.00", answer_type="decimal", domain="finance")

    def ignores_numeric_schema(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(
            model,
            json.dumps({"answer": answer, "evidence_ids": ["e1"], "brief": "bounded"}),
            seed=kwargs["seed"],
        )

    cell = run_task(
        decimal_task,
        ["m1"],
        "single",
        SETTINGS,
        ignores_numeric_schema,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]
    assert cell["status"] == "invalid"
    assert cell["answer"] is None
    assert "decimal answer" in cell["error"]


def test_constrained_short_rejects_provider_output_that_ignores_bounds():
    constrained_task = {
        **task(),
        "evidence": [{"id": f"e{i}", "text": "evidence"} for i in range(1, 5)],
    }

    def ignores_schema(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(
            model,
            json.dumps(
                {
                    "answer": "A",
                    "evidence_ids": ["e1", "e2", "e3", "e4"],
                    "brief": "x" * 161,
                }
            ),
            seed=kwargs["seed"],
        )

    cell = run_task(
        constrained_task,
        ["m1"],
        "single",
        SETTINGS,
        ignores_schema,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]
    assert cell["status"] == "invalid"
    assert cell["correct"] is None
    assert cell["messages"][0]["payload"] is None
    assert "brief" in cell["error"] or "evidence_ids" in cell["error"]


def test_constrained_short_keeps_truncation_and_unsupported_schema_failures_as_errors():
    response_format_errors: list[dict[str, Any]] = []

    class ProviderFailure(RuntimeError):
        def __init__(self, result: dict[str, Any]):
            super().__init__("truncated")
            self.result = result

    def truncated(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        assert kwargs["response_format"]["type"] == "json_schema"
        result = response(model, "{", seed=kwargs["seed"])
        result.update(content="{", completion_tokens=128, finish_reason="length")
        raise ProviderFailure(result)

    truncated_cell = run_task(
        task(),
        ["m1"],
        "single",
        SETTINGS,
        truncated,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]
    assert truncated_cell["status"] == "error"
    assert truncated_cell["messages"][0]["content"] == "{"
    assert truncated_cell["messages"][0]["completion_tokens"] == 128

    def unsupported(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        response_format_errors.append(kwargs["response_format"])
        raise RuntimeError("endpoint refused response_format")

    unsupported_cell = run_task(
        task(),
        ["m1"],
        "single",
        SETTINGS,
        unsupported,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]
    assert unsupported_cell["status"] == "error"
    assert unsupported_cell["messages"][0]["response_format"] == response_format_errors[0]
    assert len(response_format_errors) == 1


def test_constrained_invalid_signal_is_not_consumed_as_a_board_message():
    prompts: list[list[dict[str, str]]] = []
    calls = 0

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        prompts.append(messages)
        brief = "x" * 161 if calls == 1 else "valid"
        return response(
            model,
            json.dumps({"answer": "A", "evidence_ids": ["e1"], "brief": brief}),
            seed=kwargs["seed"],
        )

    cell = run_task(
        task(),
        ["m1", "m2"],
        "signal_board",
        SETTINGS,
        infer,
        lambda event: None,
        lambda: False,
        output_policy="constrained_short_v1",
    )[0]
    invalid_id = cell["messages"][0]["message_id"]
    assert cell["status"] == "invalid"
    assert cell["answer"] is None
    assert cell["messages"][0]["payload"] is None
    assert all(invalid_id not in json.dumps(messages[1:]) for messages in prompts[1:])


def test_independent_vote_requires_strict_majority_of_all_ballots():
    calls = 0

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        answer = "A" if calls < 3 else "B"
        return response(model, json.dumps({"answer": answer, "evidence_ids": ["e1"], "brief": "brief"}), seed=kwargs["seed"])

    cell = run_task(task(), ["m1"], "independent_vote", SETTINGS, infer, lambda event: None, lambda: False)[0]

    assert calls == 3
    assert cell["status"] == "completed"
    assert cell["answer"] == "A"
    assert cell["call_count"] == 3


def test_peer_review_revision_consumes_own_typed_critique():
    prompts: list[str] = []

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        prompts.append(json.dumps(messages))
        if len(prompts) <= 2:
            answer = "A" if model == "m1" else "B"
            content = json.dumps({"answer": answer, "evidence_ids": ["e1"], "brief": "initial"})
        elif len(prompts) <= 4:
            target = json.loads(messages[-1]["content"])["target"]["message_id"]
            content = json.dumps({"target_message_id": target, "assessment": "supported", "evidence_ids": ["e1"], "brief": "ok"})
        else:
            content = json.dumps({"answer": "A", "evidence_ids": ["e1"], "brief": "revised"})
        return response(model, content, seed=kwargs["seed"])

    cell = run_task(task(), ["m1", "m2"], "peer_review", SETTINGS, infer, lambda event: None, lambda: False)[0]

    assert cell["call_count"] == 6
    assert cell["status"] == "completed"
    revision_prompts = prompts[4:]
    assert revision_prompts
    assert all("target_message_id" in prompt for prompt in revision_prompts)
    assert all("expected_answer" not in prompt and "tolerance" not in prompt for prompt in prompts)


def test_signal_board_snapshots_are_round_isolated_and_ttl_bound():
    prompts: list[tuple[str, str]] = []
    counter = 0

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        prompts.append((model, json.dumps(messages)))
        return response(model, json.dumps({"answer": "A", "evidence_ids": ["e1"], "brief": "signal"}), seed=kwargs["seed"])

    cell = run_task(task(), ["m1", "m2"], "signal_board", SETTINGS, infer, lambda event: None, lambda: False)[0]

    assert cell["call_count"] == 6
    round_one = [payload for _, payload in prompts[2:4]]
    round_two = [payload for _, payload in prompts[4:6]]
    assert all('\\"round\\":0' in payload for payload in round_one)
    assert all('\\"round\\":1' in payload for payload in round_two)
    assert all(payload.count("message_id") <= 3 for payload in round_one)
    assert cell["status"] == "completed"


def test_invalid_output_and_missing_required_call_cannot_be_consensus():
    stop = False

    def invalid(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(model, "not-json", seed=kwargs["seed"])

    invalid_cell = run_task(task(), ["m1"], "single", SETTINGS, invalid, lambda event: None, lambda: False)[0]
    assert invalid_cell["status"] == "invalid"
    assert invalid_cell["correct"] is None

    def stopping() -> bool:
        return True

    missing_cell = run_task(task(), ["m1"], "independent_vote", SETTINGS, invalid, lambda event: None, stopping)[0]
    assert missing_cell["status"] == "error"
    assert missing_cell["answer"] is None
    assert missing_cell["usage_complete"] is False


def test_finance_numeric_scoring_is_strict_about_units_and_uses_tolerance():
    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(model, '{"answer":"100.005","evidence_ids":["e1"],"brief":"calculation"}', seed=kwargs["seed"])

    cell = run_task(task(expected="100.00", answer_type="decimal", domain="finance"), ["m1"], "single", SETTINGS, infer, lambda event: None, lambda: False)[0]
    assert cell["correct"] is True

    def bad_units(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(model, '{"answer":"100.00 USD","evidence_ids":["e1"],"brief":"calculation"}', seed=kwargs["seed"])

    bad = run_task(task(expected="100.00", answer_type="decimal", domain="finance"), ["m1"], "single", SETTINGS, bad_units, lambda event: None, lambda: False)[0]
    assert bad["status"] == "invalid"


def test_summary_keeps_failures_in_denominators_and_gates_evidence_honestly():
    cells = [
        {
            "domain": "medical", "variant": "single:m1", "protocol": "single", "model_keys": ["m1"],
            "status": "error", "answer": None, "correct": None, "call_count": 1,
            "prompt_tokens": 0, "completion_tokens": 0, "elapsed_s": 0.2, "usage_complete": False,
        },
        {
            "domain": "medical", "variant": "single:m1", "protocol": "single", "model_keys": ["m1"],
            "status": "completed", "answer": "A", "correct": True, "call_count": 1,
            "prompt_tokens": 11, "completion_tokens": 7, "elapsed_s": 0.1, "usage_complete": True,
        },
    ]

    row = summarize(cells, 0.8, min_cases=30)[0]

    assert row["task_count"] == 2
    assert row["coverage"] == 0.5
    assert row["task_success_rate"] == 0.5
    assert row["answered_accuracy"] == 1.0
    assert row["gate"] == "unknown"
    assert row["usage_complete"] is False


def test_validation_rejects_nonfinite_gold_and_bad_settings():
    with pytest.raises(ValueError):
        public_task({**task(answer_type="decimal", domain="finance"), "expected_answer": "NaN"})
    with pytest.raises(ValueError):
        run_task(task(), ["m1"], "single", {**SETTINGS, "temperature": 2.0}, lambda *args, **kwargs: {}, lambda _: None, lambda: False)
    with pytest.raises(ValueError):
        estimate_calls(1, 1, ["unknown"])


def test_roster_key_is_not_served_identity_but_substitution_is_rejected():
    def infer(model,messages,**kwargs):
        return response('actual-model-version', '{"answer":"A","evidence_ids":["e1"],"brief":"public"}',seed=kwargs['seed'])
    cell=run_task(task(),['handle'],'single',SETTINGS,infer,lambda e:None,lambda:False)[0]
    assert cell['status']=='completed' and cell['correct'] is True
    def wrong(model,messages,**kwargs):
        result=infer(model,messages,**kwargs);result['served_model']='substitution';return result
    cell=run_task(task(),['handle'],'single',SETTINGS,wrong,lambda e:None,lambda:False)[0]
    assert cell['status']=='error' and cell['correct'] is None


def test_failed_call_without_usage_is_marked_incomplete_and_emits_error():
    events: list[dict[str, Any]] = []

    def fail(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("transport down")

    cell = run_task(task(), ["m1"], "single", SETTINGS, fail, events.append, lambda: False)[0]

    assert cell["status"] == "error"
    assert cell["usage_complete"] is False
    assert cell["prompt_tokens"] == 0
    assert events[0]["content"] is None
    assert events[0]["usage_complete"] is False
    assert events[0]["error"] == "transport down"


def test_failed_identity_result_retains_public_content_and_usage_without_reasoning():
    events: list[dict[str, Any]] = []

    class ProviderFailure(RuntimeError):
        def __init__(self, result: dict[str, Any]):
            super().__init__("identity mismatch")
            self.result = result

    def fail(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        result = response(model, '{"answer":"A","evidence_ids":["e1"],"brief":"public"}', seed=kwargs["seed"])
        result["reasoning_content"] = "private chain of thought must not be retained"
        raise ProviderFailure(result)

    cell = run_task(task(), ["m1"], "single", SETTINGS, fail, events.append, lambda: False)[0]

    assert cell["status"] == "error"
    assert cell["usage_complete"] is True
    assert cell["prompt_tokens"] == 11
    assert cell["completion_tokens"] == 7
    assert events[0]["content"].startswith('{"answer"')
    assert events[0]["prompt_tokens"] == 11
    assert events[0]["completion_tokens"] == 7
    assert "reasoning_content" not in json.dumps(events[0])
