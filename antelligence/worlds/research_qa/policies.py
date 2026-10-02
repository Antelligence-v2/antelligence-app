"""Research QA agent brains.

:class:`QAPolicy` is an LLM worker speaking the Research Workbench's answer
contract (same system prompts and parser as ``backend.swarm_core``). A reply
that cannot be parsed becomes a ``malformed`` action, which the world scores
as *invalid* — exactly as swarm_core does — rather than being silently
dropped. Provider failures raise, so the cell becomes *error*.

When the protocol uses the board, the answer is also posted as a ``claim``
signal (topic = task id, ttl = 1 round) with a short public brief.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping

from backend.swarm_core import _PayloadError, _answer_system, _parse_answer, _validate_output_policy

from antelligence.kernel.canonical import canonical_json
from antelligence.kernel.signal import SignalDraft
from antelligence.kernel.types import Intent, LocalView
from antelligence.providers.base import ChatRequest, Provider
from antelligence.worlds.research_qa.world import ABSTAIN, ANSWER, MALFORMED

BOARD_BRIEF_CHARS = 160


def board_view(view: LocalView) -> List[Dict[str, Any]]:
    return [{"message_id": s.id[:16], "model_key": s.sender, "kind": s.kind, "round": s.emitted_at - 1,
             "payload": dict(s.payload)} for s in view.signals]


def intent_from_answer(view: LocalView, parsed: Mapping[str, Any], meta: Mapping[str, Any]) -> Intent:
    obs = view.observation
    emit = ()
    if obs.get("post_to_board"):
        emit = (SignalDraft(kind="claim", topic=obs["task"]["task_id"], ttl=1,
                            payload={"answer": parsed["answer"], "evidence_ids": list(parsed["evidence_ids"]),
                                     "brief": parsed["brief"][:BOARD_BRIEF_CHARS]}),)
    action = ABSTAIN if parsed["answer"] is None else ANSWER
    return Intent(action, dict(parsed), emit=emit, rationale=parsed["brief"][:300] or None, meta=meta)


class QAPolicy:
    def __init__(self, provider: Provider, model: str, *, output_policy: str = "prompt_only",
                 max_tokens: int = 512, temperature: float = 0.0) -> None:
        _validate_output_policy(output_policy)
        self.provider = provider
        self.model = model
        self.output_policy = output_policy
        self.max_tokens = max_tokens
        self.temperature = temperature

    def describe(self) -> Dict[str, Any]:
        return {"policy": "qa_llm", "model": self.model, "provider": self.provider.describe(),
                "output_policy": self.output_policy, "max_tokens": self.max_tokens, "temperature": self.temperature}

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
        return [{"role": "system", "content": _answer_system(system_task, self.output_policy)},
                {"role": "user", "content": canonical_json(body)}]

    async def decide(self, view: LocalView) -> Intent:
        request = ChatRequest(model=self.model, messages=tuple(self.messages(view)), max_tokens=self.max_tokens,
                              temperature=self.temperature, seed=view.seed % 2_147_483_647)
        response = await self.provider.complete(request)
        meta = {"policy": "qa_llm", **response.accounting()}
        task = dict(view.observation["task"], expected_answer="", tolerance="0")
        try:
            parsed = _parse_answer(response.content, _parse_view(task))
        except (_PayloadError, ValueError) as exc:
            return Intent(MALFORMED, {"error": str(exc)[:200]}, meta=meta)
        return intent_from_answer(view, parsed, meta)


def _parse_view(task: Mapping[str, Any]) -> Dict[str, Any]:
    """swarm_core's parser validates evidence ids and answer shape against the visible task."""
    return {"answer_type": task["answer_type"], "choices": task["choices"], "evidence": task["evidence"]}


Replier = Callable[[LocalView], Mapping[str, Any]]


class ScriptedQAPolicy:
    """Offline worker: ``reply(view)`` returns {answer, evidence_ids, brief}."""

    def __init__(self, reply: Replier, name: str = "scripted") -> None:
        self.reply = reply
        self.name = name

    def describe(self) -> Dict[str, Any]:
        return {"policy": "qa_scripted", "name": self.name}

    def decide(self, view: LocalView) -> Intent:
        task = view.observation["task"]
        try:
            parsed = _parse_answer(canonical_json(dict(self.reply(view))), _parse_view(task))
        except (_PayloadError, ValueError) as exc:
            return Intent(MALFORMED, {"error": str(exc)[:200]})
        return intent_from_answer(view, parsed, {})
