"""Pure, source-bound arithmetic for the opt-in research policy.

The model proposes only a bounded operation and exact source numeric tokens. This
module owns all source membership checks and Decimal arithmetic; it never reads
labels, tolerances, providers, or network state.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any

SOURCE_CALCULATION_POLICY_ID = "source_calculation_v1"
ALLOWED_OPERATIONS = (
    "identity",
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent_of",
    "percent_change",
    "abstain",
)
SOURCE_CALCULATION_LIMITATIONS = [
    "Source binding proves token membership only; relevance, units, and entailment are unverified."
]
MAX_QUOTE_CHARS = 64
MAX_DIGITS = 24
MAX_DECIMAL_PLACES = 12
MAX_ABS_VALUE = Decimal("1000000000000000000000000")
MAX_BRIEF_CHARS = 160

_GROUPED_NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
_MAGNITUDE = rf"(?:{_GROUPED_NUMBER}(?:\.[0-9]+)?|\.[0-9]+)"
_CURRENCY_MAGNITUDE = rf"(?:\$[ \t]*)?{_MAGNITUDE}(?:[ \t]*%)?"
_NUMERIC_TOKEN_PATTERN = (
    rf"(?:\([ \t]*{_CURRENCY_MAGNITUDE}[ \t]*\)|(?:[+-][ \t]*)?{_CURRENCY_MAGNITUDE})"
)
_NUMERIC_TOKEN_RE = re.compile(rf"^{_NUMERIC_TOKEN_PATTERN}$")
# Scan maximal complete source tokens, rather than asking whether a model's
# chosen substring happens to have plausible immediate neighbours.
_SOURCE_TOKEN_RE = re.compile(
    rf"(?<![\w.,+\-−$(]){_NUMERIC_TOKEN_PATTERN}(?![\w%]|[.,][0-9])"
)


class SourceCalculationError(ValueError):
    """A source calculation plan is malformed, ungrounded, or out of bounds."""


def compute_source_calculation(
    plan: Mapping[str, Any], task: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate a raw plan, bind quotes to evidence, and compute its payload.

    Only ``task['evidence']`` is read. In particular, evaluator fields such as
    ``expected_answer`` and ``tolerance`` are deliberately irrelevant here.
    """
    if not isinstance(plan, Mapping):
        raise SourceCalculationError("source calculation plan must be an object")
    if set(plan) != {"operation", "operands", "brief"}:
        raise SourceCalculationError("source calculation plan fields are not exact")
    operation = plan["operation"]
    if not isinstance(operation, str) or operation not in ALLOWED_OPERATIONS:
        raise SourceCalculationError("unsupported source calculation operation")
    brief = plan["brief"]
    if not isinstance(brief, str):
        raise SourceCalculationError("brief must be a string")
    if len(brief) > MAX_BRIEF_CHARS:
        raise SourceCalculationError("brief exceeds 160 characters")

    operands = plan["operands"]
    if not isinstance(operands, list):
        raise SourceCalculationError("operands must be a list")
    expected_arity = 0 if operation == "abstain" else 1 if operation == "identity" else 2
    if len(operands) != expected_arity:
        raise SourceCalculationError(
            f"operation arity mismatch: {operation} requires {expected_arity} operands"
        )

    evidence = _evidence_index(task)
    bound_operands: list[dict[str, Any]] = []
    values: list[Decimal] = []
    for operand in operands:
        if not isinstance(operand, Mapping) or set(operand) != {"evidence_id", "quote"}:
            raise SourceCalculationError("operand fields are not exact")
        evidence_id = operand["evidence_id"]
        quote = operand["quote"]
        if not isinstance(evidence_id, str) or evidence_id not in evidence:
            raise SourceCalculationError("operand evidence_id is unknown")
        if not isinstance(quote, str):
            raise SourceCalculationError("operand quote must be a string")
        value, offset = _bind_quote(quote, evidence[evidence_id])
        values.append(value)
        bound_operands.append(
            {
                "evidence_id": evidence_id,
                "quote": quote,
                "value": _decimal_text(value),
                "source_offset": offset,
            }
        )

    result = _compute(operation, values)
    result_text = None if result is None else _rounded_text(result)
    return {
        "answer": result_text,
        "evidence_ids": [operand["evidence_id"] for operand in bound_operands],
        "brief": brief,
        "calculation": {
            "operation": operation,
            "operands": bound_operands,
            "result": result_text,
            "limitations": list(SOURCE_CALCULATION_LIMITATIONS),
        },
    }


def source_calculation_response_format(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact strict JSON schema for a raw arithmetic plan."""
    evidence = _evidence_index(task)
    schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": list(ALLOWED_OPERATIONS)},
            "operands": {
                "type": "array",
                "minItems": 0,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "evidence_id": {"type": "string", "enum": list(evidence)},
                        "quote": {"type": "string", "maxLength": MAX_QUOTE_CHARS},
                    },
                    "required": ["evidence_id", "quote"],
                    "additionalProperties": False,
                },
            },
            "brief": {"type": "string", "maxLength": MAX_BRIEF_CHARS},
        },
        "required": ["operation", "operands", "brief"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": SOURCE_CALCULATION_POLICY_ID,
            "strict": True,
            "schema": schema,
        },
    }


def source_calculation_system() -> str:
    """Return the bounded model instruction without evaluator information."""
    return (
        "For a decimal task, return exactly one bare JSON object with exactly these "
        "fields: operation, operands, brief. Choose one allowlisted operation and "
        "ordered operands; each operand must contain exactly evidence_id and the "
        "whole numeric quote copied from supplied evidence. Use abstain with zero "
        "operands when one bounded operation cannot answer the question. Arithmetic "
        "is computed by the host; do not return an answer field, code, expression, "
        "units, percent scaling, or extra prose. Quotes preserve their full sign, "
        "commas, accounting parentheses, and percent notation. "
        "The ordered operands are a then b: identity=a; add=a+b; subtract=a-b; "
        "multiply=a*b; divide=a/b; percent_of=100*a/b; "
        "percent_change=100*(a-b)/b, a=new, b=old. identity takes one operand; "
        "all other calculations take two; abstain takes none. A quote such as "
        "5% represents 5 percentage points, not 0.05. Results round half-up to "
        "two decimals. Unsupported multi-operation or unit-scaling tasks must abstain."
    )


def _evidence_index(task: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(task, Mapping):
        raise SourceCalculationError("task must be an object")
    items = task.get("evidence")
    if not isinstance(items, list):
        raise SourceCalculationError("task evidence must be a list")
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise SourceCalculationError("each evidence item must be an object")
        evidence_id = item.get("id")
        text = item.get("text")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise SourceCalculationError("evidence id must be a non-empty string")
        if evidence_id in result:
            raise SourceCalculationError("evidence IDs must be unique")
        if not isinstance(text, str):
            raise SourceCalculationError("evidence text must be a string")
        result[evidence_id] = text
    return result


def _bind_quote(quote: str, text: str) -> tuple[Decimal, int]:
    if not quote or len(quote) > MAX_QUOTE_CHARS or _NUMERIC_TOKEN_RE.fullmatch(quote) is None:
        raise SourceCalculationError("quote must be one whole numeric token")
    for match in _SOURCE_TOKEN_RE.finditer(text):
        # A spaced sign/parenthesis that the grammar could not consume is not
        # permission to reinterpret its magnitude as a positive number.
        prefix = text[:match.start()].rstrip()
        if prefix.endswith(("-", "+", "−", "(")):
            continue
        if match.group() == quote:
            return _parse_quote(quote), match.start()
    raise SourceCalculationError("quote is not a whole numeric token in cited evidence")


def _parse_quote(quote: str) -> Decimal:
    accounting = quote.startswith("(")
    raw = quote[1:-1] if accounting else quote
    raw = raw.replace("$", "").replace("%", "").replace(" ", "").replace("\t", "")
    unsigned = raw.lstrip("+-")
    digits, _, fraction = unsigned.partition(".")
    if len(digits.replace(",", "")) > MAX_DIGITS or len(fraction) > MAX_DECIMAL_PLACES:
        raise SourceCalculationError("quote exceeds bounded numeric precision")
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise SourceCalculationError("quote must be finite") from exc
    if accounting:
        value = value.copy_negate()
    if not value.is_finite() or value.copy_abs() > MAX_ABS_VALUE:
        raise SourceCalculationError("quote exceeds bounded numeric magnitude")
    return value


def _compute(operation: str, values: list[Decimal]) -> Decimal | None:
    if operation == "abstain":
        return None
    try:
        with localcontext() as context:
            context.prec = 80
            if operation == "identity":
                result = values[0]
            elif operation == "add":
                result = values[0] + values[1]
            elif operation == "subtract":
                result = values[0] - values[1]
            elif operation == "multiply":
                result = values[0] * values[1]
            elif operation == "divide":
                if values[1] == 0:
                    raise SourceCalculationError("division by zero")
                result = values[0] / values[1]
            elif operation == "percent_of":
                if values[1] == 0:
                    raise SourceCalculationError("division by zero")
                result = Decimal(100) * values[0] / values[1]
            elif operation == "percent_change":
                if values[1] == 0:
                    raise SourceCalculationError("division by zero")
                result = Decimal(100) * (values[0] - values[1]) / values[1]
            else:  # pragma: no cover - operation is checked before dispatch
                raise SourceCalculationError("unsupported source calculation operation")
    except SourceCalculationError:
        raise
    except (ArithmeticError, InvalidOperation) as exc:
        raise SourceCalculationError("calculation overflow") from exc
    if not result.is_finite() or result.copy_abs() > MAX_ABS_VALUE:
        raise SourceCalculationError("calculation overflow")
    return result


def _rounded_text(value: Decimal) -> str:
    try:
        with localcontext() as context:
            context.prec = 80
            rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (ArithmeticError, InvalidOperation) as exc:
        raise SourceCalculationError("calculation overflow") from exc
    if not rounded.is_finite() or rounded.copy_abs() > MAX_ABS_VALUE:
        raise SourceCalculationError("calculation overflow")
    return format(rounded, ".2f")


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


# Short aliases keep the pure seam convenient for callers without changing the
# canonical names used by the API/core integration.
calculate = compute_source_calculation
build_response_format = source_calculation_response_format

__all__ = [
    "ALLOWED_OPERATIONS",
    "MAX_ABS_VALUE",
    "MAX_BRIEF_CHARS",
    "MAX_QUOTE_CHARS",
    "SOURCE_CALCULATION_LIMITATIONS",
    "SOURCE_CALCULATION_POLICY_ID",
    "SourceCalculationError",
    "build_response_format",
    "calculate",
    "compute_source_calculation",
    "source_calculation_response_format",
    "source_calculation_system",
]
