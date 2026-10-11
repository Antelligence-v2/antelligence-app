"""HiveWorld: wrap any World with a queen and a queen/worker board.

The wrapper adds one scheduler agent, ``"queen"``, and routes board sensing:

* workers keep their inner observation data but sense ``topic="board"``,
  ``kinds={"queen"}`` -- they hear the queen and nothing else on the board;
* the queen observes only ``{"tick", "counts"}`` and senses ``topic="board"``,
  ``kinds={"report"}`` -- worker reports plus aggregate counts, never hidden state;
* ``apply("queen", ...)`` is always accepted (her work is the signals she emits);
* everything else delegates to the inner world. ``snapshot``/``scene`` exist on the
  wrapper only if the inner world has them.

``summary_fn(world, tick)`` is injected by the harness (``PilotWorld.board_summary``).
It may return any object with a ``.counts`` mapping (e.g. ``BoardSummary``) or a
plain mapping of counts; the kernel never imports the experiments package.
With ``queen=False`` the wrapper is a pure pass-through (the no-queen ablation).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import Intent, Observation, Outcome, World

QUEEN = "queen"
BOARD = "board"
SummaryFn = Callable[[World, int], Any]


def _counts(summary: Any) -> Dict[str, Any]:
    counts = summary.counts if hasattr(summary, "counts") else summary
    if not isinstance(counts, Mapping):
        raise TypeError("summary_fn must return a mapping or an object with a .counts mapping")
    return dict(counts)


class HiveWorld:
    def __init__(self, inner: World, summary_fn: SummaryFn, *, queen: bool = True) -> None:
        if queen and QUEEN in inner.agents():
            raise ValueError(f"inner world already has an agent named {QUEEN!r}")
        self.inner = inner
        self.summary_fn = summary_fn
        self.queen = queen

    @property
    def revision(self) -> int:
        return self.inner.revision

    def agents(self) -> List[str]:
        return self.inner.agents() + ([QUEEN] if self.queen else [])

    def observe(self, agent_id: str, tick: int) -> Observation:
        if not self.queen:
            return self.inner.observe(agent_id, tick)
        if agent_id == QUEEN:
            data = {"tick": tick, "counts": _counts(self.summary_fn(self.inner, tick))}
            return Observation(data=data, sense=SenseQuery(topic=BOARD, kinds=frozenset({"report"})))
        observed = self.inner.observe(agent_id, tick)
        return replace(observed, sense=SenseQuery(topic=BOARD, kinds=frozenset({"queen"})))

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if self.queen and agent_id == QUEEN:
            return Outcome(True)
        return self.inner.apply(agent_id, intent, tick)

    def step_environment(self, tick: int) -> None:
        self.inner.step_environment(tick)

    def metrics(self) -> Dict[str, Any]:
        return self.inner.metrics()

    def done(self, tick: int) -> bool:
        return self.inner.done(tick)

    def describe(self) -> Dict[str, Any]:
        return {"world": "hive", "queen": self.queen, "board_topic": BOARD, "inner": self.inner.describe()}

    def __getattr__(self, name: str) -> Any:
        # Only the optional visualization hooks fall through, so hasattr() mirrors the inner world.
        if name in ("snapshot", "scene"):
            return getattr(self.inner, name)
        raise AttributeError(name)
