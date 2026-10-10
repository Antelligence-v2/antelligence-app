"""Source-grounding checks for research-QA claims (verified claim admission).

``verify_claim`` is a pure function of a claim and the evidence an agent could
see. It reads ``view_task["evidence"]``, ``answer_type`` and ``choices`` only,
never ``expected_answer`` or ``tolerance``, so a verdict cannot depend on the
evaluator's label.

Verification proves source grounding, not correctness: a VERIFIED claim quotes
text that really is in the cited passage, or computes its number from tokens
that really are in it. Relevance, units and entailment stay unchecked (see
``SOURCE_CALCULATION_LIMITATIONS``: "Source binding proves token membership
only; relevance, units, and entailment are unverified."). A wrong answer can be
VERIFIED; the verdict is evidence for a downstream weight, not a correctness
label.

Abstentions (``answer is None``) have nothing to verify: ``verify_claim``
returns ``None`` for them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Tuple

from backend.source_calculation import (
    _SOURCE_TOKEN_RE,
    SourceCalculationError,
    _rounded_text,
    compute_source_calculation,
)

from antelligence.kernel.aggregate import FAILED, UNVERIFIED, VERIFIED

MAX_QUOTES = 3
MIN_QUOTE_CHARS = 20  # short fragments ("patients") would ground anything
MAX_QUOTE_CHARS = 240

PASS, NONE = "pass", "none"
_Check = Tuple[str, str]  # (PASS | NONE | "fail", reason)


@dataclass(frozen=True)
class ClaimVerdict:
    status: str
    reason: str
    checks: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "checks": dict(self.checks)}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _check_quotes(claim: Mapping[str, Any], passages: Mapping[str, str]) -> _Check:
    quotes = claim.get("quotes")
    if quotes is None or quotes == []:
        return NONE, "no quotes"
    if not isinstance(quotes, list):
        return "fail", "quotes must be a list"
    if len(quotes) > MAX_QUOTES:
        return "fail", f"more than {MAX_QUOTES} quotes"
    cited = claim.get("evidence_ids") or []
    for i, quote in enumerate(quotes):
        if not isinstance(quote, Mapping) or set(quote) != {"evidence_id", "text"} \
                or not isinstance(quote["evidence_id"], str) or not isinstance(quote["text"], str):
            return "fail", f"quote {i}: fields must be exactly evidence_id and text"
        text, evidence_id = _squash(quote["text"]), quote["evidence_id"]
        if not MIN_QUOTE_CHARS <= len(text) <= MAX_QUOTE_CHARS:
            return "fail", f"quote {i}: length outside {MIN_QUOTE_CHARS}..{MAX_QUOTE_CHARS}"
        if evidence_id not in passages:
            return "fail", f"quote {i}: evidence not visible"
        if evidence_id not in cited:
            return "fail", f"quote {i}: evidence not cited by the claim"
        if text not in _squash(passages[evidence_id]):
            return "fail", f"quote {i}: text not found verbatim in {evidence_id}"
    return PASS, "all quotes verbatim"


def _with_currency(plan: Mapping[str, Any], passages: Mapping[str, str]) -> Mapping[str, Any]:
    """Restore a dropped currency sign: an operand ``644.2`` binds to the source token ``$ 644.2``.

    Tables write amounts as ``$ 644.2``; models often quote the number alone. The sign does not change
    the value, so the operand is rewritten to the unique source token in the same passage that is that
    number plus a ``$`` prefix. Anything else (percent signs, signs, parentheses) must still match exactly.
    """
    operands = plan.get("operands")
    if not isinstance(operands, list):
        return plan
    fixed = []
    for operand in operands:
        quote, text = (operand.get("quote"), passages.get(operand.get("evidence_id"))) \
            if isinstance(operand, Mapping) else (None, None)
        if isinstance(quote, str) and isinstance(text, str) and not quote.lstrip().startswith("$"):
            tokens = {m.group() for m in _SOURCE_TOKEN_RE.finditer(text)}
            if quote not in tokens:
                dollar = {t for t in tokens if t.startswith("$") and t[1:].strip() == quote.strip()}
                if len(dollar) == 1:
                    operand = {**operand, "quote": dollar.pop()}
        fixed.append(operand)
    return {**plan, "operands": fixed}


def _check_calculation(claim: Mapping[str, Any], evidence: List[Mapping[str, Any]]) -> _Check:
    plan = claim.get("calculation")
    if plan is None:
        return NONE, "no calculation"
    if not isinstance(plan, Mapping):
        return "fail", "calculation must be an object"
    try:
        plan = _with_currency(plan, {e["id"]: e["text"] for e in evidence})
        computed = compute_source_calculation({**plan, "brief": ""}, {"evidence": evidence})["answer"]
        if computed is None:
            return "fail", "calculation abstains"
        claimed = _rounded_text(Decimal(claim["answer"]))
        if Decimal(claimed) != Decimal(computed):
            return "fail", f"calculation gives {computed}, claim says {claimed}"
    except (SourceCalculationError, InvalidOperation, TypeError) as exc:
        return "fail", f"calculation invalid: {exc}"[:160]
    return PASS, "calculation reproduces the answer"


def verify_claim(claim: Mapping[str, Any], view_task: Mapping[str, Any]) -> Optional[ClaimVerdict]:
    """Verdict for a parsed answer dict (plus optional ``quotes``/``calculation``), or None for an abstention."""
    if not isinstance(claim, Mapping):
        return ClaimVerdict(FAILED, "claim must be an object")
    if claim.get("answer") is None:
        return None
    evidence = list(view_task["evidence"])
    passages = {e["id"]: e["text"] for e in evidence}
    checks = {"quotes": _check_quotes(claim, passages)}
    if view_task["answer_type"] == "decimal":
        checks["calculation"] = _check_calculation(claim, evidence)
    summary = {name: state if state != "fail" else f"fail: {why}" for name, (state, why) in checks.items()}
    for name, (state, why) in checks.items():
        if state == "fail":
            return ClaimVerdict(FAILED, f"{name}: {why}", summary)
    if view_task["answer_type"] == "decimal":
        grounded = checks["calculation"][0] == PASS
    else:
        grounded = checks["quotes"][0] == PASS
    if grounded:
        return ClaimVerdict(VERIFIED, "source grounded", summary)
    return ClaimVerdict(UNVERIFIED, "no checkable grounding supplied", summary)
