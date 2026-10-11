"""Typed decisions: the worker contract shared by Jev, Laya, an SLM and fakes.

A worker does not write free text. It reads a short ``state`` written in words
and answers typed questions, each returning probabilities:

* ``noul``   -- yes/no; the answer is P(yes).
* ``choice`` -- one option from a fixed list; a distribution plus confidence.
* ``score``  -- an ordered rubric; a probability-weighted level plus confidence.

The request mirrors the TypeSafe Jev wire protocol (``POST /v1/systemone``,
https://docs.typesafe.ai/api.md) so one :class:`DecisionRequest` can be sent to
any :class:`DecisionBackend` unchanged. Backends live outside the kernel.

The world side of the contract is :class:`SensedState` and :class:`Sensor`: a
world turns one agent's :class:`LocalView` into a short word string, the
structured fields it was rendered from, and the legal actions. Every model arm
and every script see the same ``SensedState``. The kernel never imports a world.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple, runtime_checkable

from antelligence.kernel.canonical import content_hash, plain
from antelligence.kernel.types import LocalView

QUESTION_TYPES = ("noul", "choice", "score")
REPORT = "report"  # the worker's escape option: "my local evidence disagrees"
MAX_STATE_CHARS = 1200  # ~300 tokens; Laya's hard limit is 1,024 tokens


class DecisionError(RuntimeError):
    """A backend failed or returned an answer that breaks the contract."""


@dataclass(frozen=True)
class Question:
    """One typed question.

    ``options`` are the choice option ids (choice) or the ordered level
    descriptions (score); empty for noul. ``criteria`` optionally describes
    options (choice: option -> text) or the yes/no meaning (noul: "true"/"false").
    """

    type: str
    instructions: str
    options: Tuple[str, ...] = ()
    criteria: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in QUESTION_TYPES:
            raise ValueError(f"question type must be one of {QUESTION_TYPES}")
        if not self.instructions:
            raise ValueError("instructions are required")
        options = tuple(self.options)
        if self.type == "noul" and options:
            raise ValueError("noul questions take no options")
        if self.type in ("choice", "score") and len(options) < 2:
            raise ValueError(f"{self.type} questions need at least two options")
        if len(set(options)) != len(options):
            raise ValueError("options must be unique")
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "criteria", plain(dict(self.criteria)))

    def shuffled(self, rng: random.Random) -> "Question":
        """Choice options in a seeded order (Jev favours the first option)."""
        if self.type != "choice":
            return self
        order = list(self.options)
        rng.shuffle(order)
        return Question(self.type, self.instructions, tuple(order), self.criteria)

    def wire(self) -> Dict[str, Any]:
        """The Jev wire form of this question."""
        body: Dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.type == "noul":
            if self.criteria:
                body["criteria"] = {k: self.criteria[k] for k in ("true", "false") if k in self.criteria}
        elif self.type == "choice":
            body["criteria"] = {o: self.criteria.get(o) for o in self.options}
        else:
            body["criteria"] = list(self.options)
        return body


@dataclass(frozen=True)
class DecisionRequest:
    """A state plus named questions. ``model`` is the backend's pinned model id."""

    model: str
    state: str
    questions: Mapping[str, Question]
    seed: int = 0

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model is required")
        if not self.state or len(self.state) > MAX_STATE_CHARS:
            raise ValueError(f"state must be 1..{MAX_STATE_CHARS} characters")
        if not self.questions:
            raise ValueError("at least one question is required")
        questions = dict(self.questions)
        if not all(isinstance(q, Question) for q in questions.values()):
            raise ValueError("questions must be Question objects")
        object.__setattr__(self, "questions", questions)

    @classmethod
    def build(cls, model: str, state: str, questions: Mapping[str, Question], seed: int) -> "DecisionRequest":
        """Build a request with choice options shuffled by ``seed`` (order is recorded in the payload)."""
        rng = random.Random(seed)
        return cls(model, state, {qid: questions[qid].shuffled(rng) for qid in sorted(questions)}, seed)

    def payload(self) -> Dict[str, Any]:
        """Exactly what goes on the wire (Jev / laya-serve)."""
        return {"model": self.model, "state": self.state,
                "questions": {qid: q.wire() for qid, q in self.questions.items()}}

    @property
    def request_hash(self) -> str:
        return content_hash(self.payload())


@dataclass(frozen=True)
class Answer:
    """One typed answer.

    noul: ``value`` = P(yes), ``probabilities`` = {"yes": p, "no": 1-p}.
    choice: ``value`` = chosen option, ``probabilities`` over options.
    score: ``value`` = probability-weighted level index, ``probabilities`` over
    level indices as strings ("0", "1", ...).
    ``confidence`` is the backend's own number for choice/score; None for noul.
    """

    type: str
    value: Any
    probabilities: Mapping[str, float]
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if self.type not in QUESTION_TYPES:
            raise ValueError("bad answer type")
        probs = {str(k): float(v) for k, v in dict(self.probabilities).items()}
        if not probs or any(not 0.0 <= p <= 1.0 for p in probs.values()):
            raise ValueError("probabilities must be in [0, 1]")
        if abs(sum(probs.values()) - 1.0) > 0.02:
            raise ValueError("probabilities must sum to 1")
        object.__setattr__(self, "probabilities", probs)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    @property
    def p_yes(self) -> float:
        if self.type != "noul":
            raise ValueError("p_yes is only defined for noul answers")
        return float(self.value)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "value": self.value, "probabilities": dict(self.probabilities),
                "confidence": self.confidence}


def check_answers(request: DecisionRequest, answers: Mapping[str, Answer]) -> None:
    """Refuse answers that do not match the questions asked."""
    if set(answers) != set(request.questions):
        raise DecisionError("answers do not match the question ids")
    for qid, question in request.questions.items():
        answer = answers[qid]
        if answer.type != question.type:
            raise DecisionError(f"{qid}: answer type {answer.type} != question type {question.type}")
        if question.type == "choice" and (answer.value not in question.options
                                          or set(answer.probabilities) != set(question.options)):
            raise DecisionError(f"{qid}: choice outside the offered options")
        if question.type == "score" and set(answer.probabilities) != {str(i) for i in range(len(question.options))}:
            raise DecisionError(f"{qid}: score levels do not match")


@dataclass(frozen=True)
class DecisionResponse:
    """Answers plus accounting. ``served_model`` is what the provider says it ran."""

    answers: Mapping[str, Answer]
    served_model: str
    request_hash: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    cached: bool = False
    escalated: Tuple[str, ...] = ()  # question ids answered by an escalation backend

    def accounting(self) -> Dict[str, Any]:
        """Provenance for the hashed event log (no wall-clock, no cache flag, so replays hash equal)."""
        return {"model": self.served_model, "request_hash": self.request_hash,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "escalated": list(self.escalated)}


@runtime_checkable
class DecisionBackend(Protocol):
    """Jev, Laya, an SLM on vLLM, or a fake. Must call :func:`check_answers` before returning."""

    async def decide(self, request: DecisionRequest) -> DecisionResponse: ...

    def describe(self) -> Dict[str, Any]: ...


# --- world side ------------------------------------------------------------


@dataclass(frozen=True)
class SensedState:
    """What one agent knows, in words, plus the fields it was rendered from.

    ``text`` is the decision-model state (short, words not raw numbers, no
    counting left to the model). ``fields`` holds the same facts in structured
    form for scripts and the harness. ``actions`` maps legal action ids to a
    short description; the move question offers a subset of these plus REPORT.
    """

    text: str
    fields: Mapping[str, Any]
    actions: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.text or len(self.text) > MAX_STATE_CHARS:
            raise ValueError(f"text must be 1..{MAX_STATE_CHARS} characters")
        if not self.actions or REPORT in self.actions:
            raise ValueError(f"actions must be non-empty and must not contain {REPORT!r}")
        object.__setattr__(self, "fields", plain(dict(self.fields)))
        object.__setattr__(self, "actions", dict(self.actions))


@runtime_checkable
class Sensor(Protocol):
    """A world's sensing layer: LocalView -> SensedState. Deterministic, no RNG draws."""

    def sense(self, view: LocalView) -> SensedState: ...

    def describe(self) -> Dict[str, Any]: ...
