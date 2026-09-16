"""RED/GREEN contract tests for source-backed arithmetic."""
from __future__ import annotations

import json
from typing import Any

import pytest

from backend.source_calculation import (
    ALLOWED_OPERATIONS,
    compute_source_calculation,
    source_calculation_response_format,
)
from backend.swarm_core import run_task


SETTINGS = {"temperature": 0.2, "seed": 17, "max_tokens": 128}


def source_task(evidence: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "task_id": "finqa:dev-source",
        "evidence": evidence
        or [{"id": "table_0", "text": "Revenue increased from 200 to 250. Values: 0 and 9999999999999999999999999 and 1."}],
    }


def response(model: str, content: str, *, seed: int) -> dict[str, Any]:
    return {
        "content": content,
        "response_id": f"resp-{model}-{seed}",
        "requested_model": model,
        "served_model": model,
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "elapsed_s": 0.01,
        "finish_reason": "stop",
    }


def test_percent_change_is_decimal_and_source_trace_is_computed_payload():
    payload = compute_source_calculation(
        {
            "operation": "percent_change",
            "operands": [
                {"evidence_id": "table_0", "quote": "200"},
                {"evidence_id": "table_0", "quote": "250"},
            ],
            "brief": "new versus old",
        },
        source_task(),
    )

    assert payload["answer"] == "-20.00"
    assert payload["evidence_ids"] == ["table_0", "table_0"]
    assert payload["brief"] == "new versus old"
    assert payload["calculation"] == {
        "operation": "percent_change",
        "operands": [
            {"evidence_id": "table_0", "quote": "200", "value": "200", "source_offset": 23},
            {"evidence_id": "table_0", "quote": "250", "value": "250", "source_offset": 30},
        ],
        "result": "-20.00",
        "limitations": [
            "Source binding proves token membership only; relevance, units, and entailment are unverified."
        ],
    }


def test_source_calculation_wire_schema_is_exact_and_bounded():
    schema = source_calculation_response_format(source_task())["json_schema"]["schema"]

    assert set(schema["properties"]) == {"operation", "operands", "brief"}
    assert schema["required"] == ["operation", "operands", "brief"]
    assert schema["additionalProperties"] is False
    operand_schema = schema["properties"]["operands"]["items"]
    assert operand_schema["required"] == ["evidence_id", "quote"]
    assert operand_schema["additionalProperties"] is False
    assert schema["properties"]["operation"]["enum"] == list(ALLOWED_OPERATIONS)


@pytest.mark.parametrize(
    "plan, error",
    [
        (
            {"operation": "add", "operands": [{"evidence_id": "table_0", "quote": "50"}], "brief": "x"},
            "arity",
        ),
        (
            {"operation": "divide", "operands": [{"evidence_id": "table_0", "quote": "200"}, {"evidence_id": "table_0", "quote": "0"}], "brief": "x"},
            "zero",
        ),
        (
            {"operation": "add", "operands": [{"evidence_id": "table_0", "quote": "9999999999999999999999999"}, {"evidence_id": "table_0", "quote": "1"}], "brief": "x"},
            "bounded",
        ),
        (
            {"operation": "abstain", "operands": [], "brief": "unsupported"},
            None,
        ),
    ],
)
def test_source_calculation_rejects_invalid_operations_and_supports_abstention(plan, error):
    if error is None:
        assert compute_source_calculation(plan, source_task())["answer"] is None
    else:
        with pytest.raises(ValueError, match=error):
            compute_source_calculation(plan, source_task())


@pytest.mark.parametrize("quote", ["50", "-50", "(50)"])
def test_quote_must_be_a_whole_signed_source_token(quote: str):
    task = source_task([{"id": "table_0", "text": "The reported value is 150."}])
    with pytest.raises(ValueError, match="whole numeric token"):
        compute_source_calculation(
            {"operation": "identity", "operands": [{"evidence_id": "table_0", "quote": quote}], "brief": "x"},
            task,
        )


def test_computed_payload_replaces_raw_plan_and_trace_reaches_peer_messages():
    plans = [
        json.dumps(
            {
                "operation": "percent_change",
                "operands": [
                    {"evidence_id": "e1", "quote": "200"},
                    {"evidence_id": "e1", "quote": "250"},
                ],
                "brief": "initial",
            }
        ),
        json.dumps(
            {
                "operation": "percent_change",
                "operands": [
                    {"evidence_id": "e1", "quote": "200"},
                    {"evidence_id": "e1", "quote": "250"},
                ],
                "brief": "revision",
            }
        ),
    ]
    prompts: list[list[dict[str, str]]] = []
    calls = 0

    task = {
        "task_id": "task-source",
        "source_id": "source-1",
        "dataset": "finqa",
        "domain": "finance",
        "split": "development",
        "question": "What is the percentage change?",
        "evidence": [{"id": "e1", "text": "Revenue was 200 and then 250."}],
        "answer_type": "decimal",
        "choices": [],
        "expected_answer": "-20.00",
        "tolerance": "0.01",
        "source_url": "https://example.test/source-1",
    }

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        prompts.append(messages)
        if calls <= 2:
            content = plans[0]
        elif calls <= 4:
            target = json.loads(messages[-1]["content"])["target"]["message_id"]
            content = json.dumps(
                {
                    "target_message_id": target,
                    "assessment": "supported",
                    "evidence_ids": ["e1"],
                    "brief": "trace checked",
                }
            )
        else:
            content = plans[1]
        return response(model, content, seed=kwargs["seed"])

    cell = run_task(
        task,
        ["m1", "m2"],
        "peer_review",
        SETTINGS,
        infer,
        lambda event: None,
        lambda: False,
        output_policy="source_calculation_v1",
    )[0]

    assert cell["status"] == "completed"
    assert cell["answer"] == "-20.00"
    assert cell["messages"][0]["payload"]["calculation"]["result"] == "-20.00"
    assert "calculation" in json.dumps(prompts[2:])
    assert "percent_change" in prompts[2][1]["content"]
    assert '"operation": "percent_change"' in cell["messages"][0]["content"]
    assert "expected_answer" not in json.dumps(prompts)
    assert "tolerance" not in json.dumps(prompts)


def test_source_policy_keeps_choice_schema_behavior_and_rejects_invalid_plan_consensus():
    choice_task = {
        "task_id": "task-choice",
        "source_id": "source-1",
        "dataset": "pubmedqa",
        "domain": "medical",
        "split": "development",
        "question": "Which option?",
        "evidence": [{"id": "e1", "text": "Option A."}],
        "answer_type": "choice",
        "choices": ["A", "B"],
        "expected_answer": "A",
        "tolerance": "0",
        "source_url": "https://example.test/source-1",
    }

    def infer(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(model, '{"answer":"A","evidence_ids":["e1"],"brief":"choice"}', seed=kwargs["seed"])

    cell = run_task(
        choice_task,
        ["m1"],
        "single",
        SETTINGS,
        infer,
        lambda event: None,
        lambda: False,
        output_policy="source_calculation_v1",
    )[0]
    assert cell["status"] == "completed"
    assert cell["messages"][0]["response_format"]["json_schema"]["schema"]["required"] == [
        "answer",
        "evidence_ids",
        "brief",
    ]

    def invalid_plan(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return response(
            model,
            '{"operation":"identity","operands":[{"evidence_id":"e1","quote":"50"}],"brief":"bad"}',
            seed=kwargs["seed"],
        )

    decimal_task = {
        **choice_task,
        "task_id": "task-decimal",
        "dataset": "finqa",
        "domain": "finance",
        "question": "What value?",
        "answer_type": "decimal",
        "choices": [],
        "expected_answer": "0",
        "tolerance": "0.01",
    }
    invalid = run_task(
        decimal_task,
        ["m1"],
        "independent_vote",
        SETTINGS,
        invalid_plan,
        lambda event: None,
        lambda: False,
        output_policy="source_calculation_v1",
    )[0]
    assert invalid["status"] == "invalid"
    assert invalid["answer"] is None
    assert invalid["correct"] is None
