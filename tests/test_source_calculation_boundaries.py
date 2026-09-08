"""Parent-discovered source-binding regressions, independent of benchmark labels."""
import pytest
from backend.source_calculation import compute_source_calculation


def identity(text, quote):
    return compute_source_calculation(
        {"operation": "identity", "operands": [{"evidence_id": "e", "quote": quote}], "brief": "source"},
        {"evidence": [{"id": "e", "text": text}]},
    )


@pytest.mark.parametrize("text,quote", [
    ("loss - 50 dollars", "50"),
    ("loss ( 50 ) dollars", "50"),
    ("loss −50 dollars", "50"),
    ("value .6 dollars", "6"),
    ("value 1e3 dollars", "1"),
    ("value abc50 dollars", "50"),
    ("value 50 %", "50"),
    ("value 1,500 dollars", "500"),
    ("value - 1,500.5%", "1,500.5"),
])
def test_partial_or_sign_stripped_source_quote_is_rejected(text, quote):
    with pytest.raises(ValueError, match="whole numeric token"):
        identity(text, quote)


@pytest.mark.parametrize("quote,answer", [
    ("- 50", "-50.00"), ("( 50 )", "-50.00"), (".6", "0.60"),
    ("$ 1,500.25", "1500.25"), ("(5%)", "-5.00"), ("50 %", "50.00"),
])
def test_supported_whole_source_notation_preserves_its_value(quote, answer):
    assert identity(f"Reported {quote} dollars.", quote)["answer"] == answer


@pytest.mark.parametrize("quote,expected", [
    ("-123456789012345678901234.004999", "-123456789012345678901234.00"),
    ("(123456789012345678901234.004999)", "-123456789012345678901234.00"),
    ("123456789012345678901234.005", "123456789012345678901234.01"),
])
def test_numeric_precision_does_not_depend_on_ambient_decimal_context(quote, expected):
    from decimal import Decimal, localcontext
    for precision in (6, 28, 80):
        with localcontext() as context:
            context.prec = precision
            payload = identity(quote, quote)
            assert payload["answer"] == expected
            normalized = Decimal(quote.strip("()")).copy_negate() if quote.startswith("(") else Decimal(quote)
            assert Decimal(payload["calculation"]["operands"][0]["value"]) == normalized


def test_model_instruction_defines_every_operation_and_operand_order():
    from backend.source_calculation import source_calculation_system
    prompt = source_calculation_system()
    for rule in ("identity=a", "add=a+b", "subtract=a-b", "multiply=a*b", "divide=a/b",
                 "percent_of=100*a/b", "percent_change=100*(a-b)/b", "a=new, b=old",
                 "percentage points", "abstain"):
        assert rule in prompt


def test_gold_labels_cannot_change_host_computation():
    plan = {"operation": "subtract", "operands": [{"evidence_id": "e", "quote": "20"}, {"evidence_id": "e", "quote": "50"}], "brief": "source"}
    task = {"evidence": [{"id": "e", "text": "20 versus 50"}]}
    first = compute_source_calculation(plan, {**task, "expected_answer": "-30", "tolerance": "0.01"})
    second = compute_source_calculation(plan, {**task, "expected_answer": "777", "tolerance": "999"})
    assert first == second
    assert first["answer"] == "-30.00"
