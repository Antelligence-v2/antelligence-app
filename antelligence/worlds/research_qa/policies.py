"""Research QA agent brains.

:class:`QAPolicy` is an LLM worker speaking the Research Workbench's answer
contract (same system prompts and parser as ``backend.swarm_core``). A reply
that cannot be parsed becomes a ``malformed`` action, which the world scores
as *invalid* — exactly as swarm_core does — rather than being silently
dropped. Provider failures raise, so the cell becomes *error*.

When the protocol uses the board, the answer is also posted as a ``claim``
signal (topic = task id, ttl = 1 round) with a short public brief.

``claims="verified_claims_v1"`` asks for source-grounded claims (``quotes`` or a
``calculation`` next to the usual fields; see :mod:`.verify`) and marks each
board claim with its verification status. ``lenient=True`` truncates extra
citations and drops unknown keys, recording ``format_violations`` instead of
returning ``malformed``; a reply that is not a JSON object is still malformed.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Mapping, Optional

from backend.swarm_core import (
    _CONSTRAINED_DECIMAL_PATTERN,
    _PayloadError,
    _answer_system,
    _object_without_duplicate_keys,
    _parse_answer,
    _validate_output_policy,
)
from backend.source_calculation import ALLOWED_OPERATIONS, SOURCE_CALCULATION_POLICY_ID

from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import Intent, LocalView
from antelligence.providers.base import ChatRequest, Provider
from antelligence.worlds.research_qa.verify import verify_claim
from antelligence.worlds.research_qa.world import ABSTAIN, ANSWER, MALFORMED, MAX_CITED

BOARD_BRIEF_CHARS = 160
VERIFIED_CLAIMS = "verified_claims_v1"
_CLAIM_EXTRAS = ("quotes", "calculation")
_ANSWER_KEYS = frozenset({"answer", "evidence_ids", "brief"})

VERIFIED_CLAIMS_SYSTEM = (
    "Answer the task using the supplied evidence. Reply with one bare JSON object, no code fences, "
    "extra prose or private chain-of-thought. Cite AT MOST 3 evidence IDs in evidence_ids. "
    "The host checks every claim against the cited passages; unsupported claims are allowed but carry "
    "less weight than claims whose support checks out."
)
_CHOICE_CLAIM = (
    " Fields: answer, evidence_ids, brief, quotes. quotes is a list of at most 3 objects "
    '{"evidence_id", "text"}; each text is 8 to 240 characters copied verbatim from the passage you cite '
    "(same characters, whitespace may differ) and its evidence_id must be one of your evidence_ids."
)
_DECIMAL_CLAIM = (
    " Fields: answer, evidence_ids, brief, calculation. calculation is "
    '{"operation", "operands": [{"evidence_id", "quote"}]} with operation one of '
    + ", ".join(o for o in ALLOWED_OPERATIONS if o != "abstain")
    + "; each quote is the exact source numeric token copied from the cited passage, with its sign, commas, "
    "parentheses and percent notation. Operands are a then b: identity=a; add=a+b; subtract=a-b; "
    "multiply=a*b; divide=a/b; percent_of=100*a/b; percent_change=100*(a-b)/b. The host recomputes the "
    "result and rounds half-up to two decimals; answer must equal it."
)


def verified_claims_system(task: Mapping[str, Any]) -> str:
    """Prompt for the verified-claims contract, shaped by the task's answer type (never its label)."""
    if task["answer_type"] == "choice":
        rule = "answer must be exactly one of " + json.dumps(task["choices"], ensure_ascii=False,
                                                              separators=(",", ":")) + " or null"
    else:
        rule = f"answer must match the bounded decimal pattern {_CONSTRAINED_DECIMAL_PATTERN!r} or null"
    shape = _CHOICE_CLAIM if task["answer_type"] == "choice" else _DECIMAL_CLAIM
    return VERIFIED_CLAIMS_SYSTEM + shape + f" {rule}; brief must be at most {BOARD_BRIEF_CHARS} characters."


def _check_options(claims: Optional[str]) -> None:
    if claims not in (None, VERIFIED_CLAIMS):
        raise ValueError(f"unknown claims contract {claims!r}")


def parse_reply(content: str, task: Mapping[str, Any], claims: Optional[str], lenient: bool) -> Dict[str, Any]:
    """Parse a reply to {answer, evidence_ids, brief} plus, under ``claims``, quotes/calculation.

    With both options off this is exactly swarm_core's strict parser."""
    if claims is None and not lenient:
        return _parse_answer(content, _parse_view(task))
    try:
        obj = json.loads(content.strip(), object_pairs_hook=_object_without_duplicate_keys,
                         parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise _PayloadError(f"response is not strict JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise _PayloadError("response must be a JSON object")
    extras = {k: obj.pop(k) for k in _CLAIM_EXTRAS if claims and k in obj}
    violations: List[str] = []
    if lenient:
        unknown = sorted(set(obj) - _ANSWER_KEYS)
        if unknown:
            violations.append("unknown_keys:" + ",".join(unknown))
            obj = {k: v for k, v in obj.items() if k in _ANSWER_KEYS}
        ids = obj.get("evidence_ids")
        if isinstance(ids, list) and all(isinstance(i, str) for i in ids):
            unique = list(dict.fromkeys(ids))
            if len(unique) > MAX_CITED:
                violations.append("evidence_ids_truncated")
            elif len(unique) != len(ids):
                violations.append("evidence_ids_deduplicated")
            obj["evidence_ids"] = unique[:MAX_CITED]
    parsed = _parse_answer(json.dumps(obj), _parse_view(task))
    parsed.update(extras)
    if violations:
        parsed["format_violations"] = violations
    return parsed


def board_view(view: LocalView) -> List[Dict[str, Any]]:
    return [{"message_id": s.id[:16], "model_key": s.sender, "kind": s.kind, "round": s.emitted_at - 1,
             "payload": dict(s.payload)} for s in view.signals]


def intent_from_answer(view: LocalView, parsed: Mapping[str, Any], meta: Mapping[str, Any], *,
                       mark: bool = False) -> Intent:
    obs = view.observation
    emit = ()
    if obs.get("post_to_board"):
        payload = {"answer": parsed["answer"], "evidence_ids": list(parsed["evidence_ids"]),
                   "brief": parsed["brief"][:BOARD_BRIEF_CHARS]}
        verdict = verify_claim(parsed, obs["task"]) if mark else None
        if verdict is not None:
            payload["verification"] = verdict.status
        emit = (SignalDraft(kind="claim", topic=obs["task"]["task_id"], ttl=1, payload=payload),)
    action = ABSTAIN if parsed["answer"] is None else ANSWER
    return Intent(action, dict(parsed), emit=emit, rationale=parsed["brief"][:300] or None, meta=meta)


class QAPolicy:
    def __init__(self, provider: Provider, model: str, *, output_policy: str = "prompt_only",
                 max_tokens: int = 512, temperature: float = 0.0, claims: Optional[str] = None,
                 lenient: bool = False) -> None:
        _validate_output_policy(output_policy)
        _check_options(claims)
        if claims and output_policy == SOURCE_CALCULATION_POLICY_ID:
            raise ValueError("claims and the source_calculation_v1 output policy are exclusive")
        self.claims = claims
        self.lenient = lenient
        self.provider = provider
        self.model = model
        self.output_policy = output_policy
        self.max_tokens = max_tokens
        self.temperature = temperature

    def describe(self) -> Dict[str, Any]:
        out = {"policy": "qa_llm", "model": self.model, "provider": self.provider.describe(),
               "output_policy": self.output_policy, "max_tokens": self.max_tokens, "temperature": self.temperature}
        return {**out, **_option_description(self.claims, self.lenient)}

    def messages(self, view: LocalView) -> List[Dict[str, str]]:
        obs = view.observation
        task = obs["task"]
        system_task = dict(task, expected_answer="", tolerance="0")  # labels are never present; shape only
        body: Dict[str, Any] = {"task": task, "agent_id": view.agent_id, "round": obs["round"],
                                "instruction": obs["instruction"]}
        if obs.get("own_previous") is not None:
            body["own_previous"] = obs["own_previous"]
        if view.signals:
            body["signals"] = board_view(view)
        system = verified_claims_system(system_task) if self.claims else _answer_system(system_task, self.output_policy)
        return [{"role": "system", "content": system},
                {"role": "user", "content": canonical_json(body)}]

    async def decide(self, view: LocalView) -> Intent:
        request = ChatRequest(model=self.model, messages=tuple(self.messages(view)), max_tokens=self.max_tokens,
                              temperature=self.temperature, seed=view.seed % 2_147_483_647)
        response = await self.provider.complete(request)
        meta = {"policy": "qa_llm", **response.accounting()}
        task = dict(view.observation["task"], expected_answer="", tolerance="0")
        try:
            parsed = parse_reply(response.content, task, self.claims, self.lenient)
        except (_PayloadError, ValueError) as exc:
            return Intent(MALFORMED, {"error": str(exc)[:200]}, meta=meta)
        return intent_from_answer(view, parsed, meta, mark=bool(self.claims))


def _parse_view(task: Mapping[str, Any]) -> Dict[str, Any]:
    """swarm_core's parser validates evidence ids and answer shape against the visible task."""
    return {"answer_type": task["answer_type"], "choices": task["choices"], "evidence": task["evidence"]}


def _option_description(claims: Optional[str], lenient: bool) -> Dict[str, Any]:
    return {**({"claims": claims} if claims else {}), **({"lenient": True} if lenient else {})}


Replier = Callable[[LocalView], Mapping[str, Any]]


class ScriptedQAPolicy:
    """Offline worker: ``reply(view)`` returns {answer, evidence_ids, brief} (+ quotes/calculation under ``claims``)."""

    def __init__(self, reply: Replier, name: str = "scripted", *, claims: Optional[str] = None,
                 lenient: bool = False) -> None:
        _check_options(claims)
        self.reply = reply
        self.name = name
        self.claims = claims
        self.lenient = lenient

    def describe(self) -> Dict[str, Any]:
        return {"policy": "qa_scripted", "name": self.name, **_option_description(self.claims, self.lenient)}

    def decide(self, view: LocalView) -> Intent:
        task = view.observation["task"]
        try:
            parsed = parse_reply(canonical_json(dict(self.reply(view))), task, self.claims, self.lenient)
        except (_PayloadError, ValueError) as exc:
            return Intent(MALFORMED, {"error": str(exc)[:200]})
        return intent_from_answer(view, parsed, {}, mark=bool(self.claims))
