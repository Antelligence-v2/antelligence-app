"""v4 pilot contract between worlds, framework workers, the queen and the harness.

Each pilot world package (``antelligence.worlds.foraging_sb``,
``antelligence.worlds.graph_coloring``) exposes one object satisfying
:class:`PilotWorld`. The harness only talks to worlds through it; framework
workers and the queen only see :class:`SensedState` text, the board, and the
answers of a :class:`~antelligence.kernel.decision.DecisionBackend`.

Privileged methods (``oracle_action``, ``labelled_questions``) read hidden
world state. They exist for labels and metrics only: no policy or queen may
call them during a run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Mapping, Protocol, Tuple, Union, runtime_checkable

from antelligence.kernel.decision import Question, Sensor
from antelligence.kernel.types import LocalView, Policy, World

CONDITIONS = ("base", "v1", "v2")
QUESTION_KINDS = ("judgement", "move")
MAX_INSTRUCTIONS = 300


@dataclass(frozen=True)
class LabelledQuestion:
    """A question about one agent's situation, with the simulator's true answer.

    ``label`` is a bool for noul questions and an option id for choice
    questions. ``accept`` (choice only) lists every equally good option; it
    defaults to ``(label,)`` and always contains the label. Used for Phase 0
    calibration and for report precision.
    """

    qid: str
    kind: str
    question: Question
    label: Any
    accept: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in QUESTION_KINDS:
            raise ValueError(f"kind must be one of {QUESTION_KINDS}")
        if self.question.type == "noul" and not isinstance(self.label, bool):
            raise ValueError("noul labels are bools")
        if self.question.type == "choice" and self.label not in self.question.options:
            raise ValueError("choice label must be one of the options")
        if self.question.type == "noul" and self.accept:
            raise ValueError("noul questions take no accept set")
        if self.question.type == "choice":
            accept = tuple(self.accept) or (self.label,)
            if self.label not in accept or not set(accept) <= set(self.question.options):
                raise ValueError("accept must contain the label and be a subset of the options")
            object.__setattr__(self, "accept", accept)


@dataclass(frozen=True)
class BoardSummary:
    """What the queen may see besides worker reports: aggregate counts only."""

    tick: int
    counts: Mapping[str, Any] = field(default_factory=dict)  # e.g. deliveries so far, conflicts left


@runtime_checkable
class PilotWorld(Protocol):
    """One pilot task: a seeded world in a condition, its sensor, S and S′, and simulator labels."""

    name: str
    actions: Mapping[str, str]  # every legal action id -> short description (REPORT excluded)
    instructions: str  # the task, in plain words (<= MAX_INSTRUCTIONS chars); identical in every condition

    def make_world(self, seed: int, condition: str) -> World:
        """A fresh deterministic world. ``condition`` is one of CONDITIONS."""
        ...

    def sensor(self) -> Sensor: ...

    def script(self, condition: str, *, adapted: bool) -> Policy:
        """S (``adapted=False``) or S′ for ``condition`` (``adapted=True``, v1/v2 only)."""
        ...

    def score(self, world: World) -> float:
        """The scorer, identical across conditions (deliveries; fraction of properly coloured edges)."""
        ...

    def groups(self, world: World) -> Mapping[str, Tuple[str, ...]]:
        """Fixed worker groups the queen addresses (group id -> agent ids)."""
        ...

    def board_summary(self, world: World, tick: int) -> BoardSummary: ...

    def oracle_action(self, world: World, agent_id: str, tick: int) -> str:
        """Privileged best action for this agent now (labels, report truth). Never shown to policies."""
        ...

    def oracle_actions(self, world: World, agent_id: str, tick: int) -> Tuple[str, ...]:
        """Every equally good action for this agent now (privileged); ``oracle_action`` is the first."""
        ...

    def labelled_questions(self, world: World, view: LocalView, tick: int) -> List[LabelledQuestion]:
        """Up to two judgement nouls plus one move choice for this agent now, with simulator labels."""
        ...

    def describe(self) -> Dict[str, Any]: ...


def report_is_true(oracle: Union[str, Collection[str]], allowed: Collection[str]) -> bool:
    """A "report" is true when none of the simulator's good actions (one str or several) is allowed."""
    good = (oracle,) if isinstance(oracle, str) else tuple(oracle)
    return not any(a in allowed for a in good)
