"""Three-tier replay interfaces and Tier A :class:`ReplayBox` for $0 DAG recomposition.

* **Tier A** (:class:`ReplayBox`, :class:`RecordingBox`): step-level replay for stateless DAG tools,
  keyed by ``(task_id, tool_name, input_hash)``.
* **Tier B** (:class:`BranchingReplay`): checkpoint-branching counterfactual replay for stateful
  environments with ``supports_checkpoint=True``.
* **Tier C** (:class:`EpisodeReplay`): episode/outcome-level replay for non-checkpointable external
  games and multi-turn agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from antelligence.harness.core import (
    Action,
    Artifact,
    EnvAdapter,
    EnvSnapshot,
    EpisodeOutcome,
    Task,
    ToolSpec,
    input_hash,
)

ReplayKey = Tuple[str, str, str]  # (task_id, tool_name, input_hash)


class ReplayMissError(KeyError):
    """Raised when :class:`ReplayBox` has no recorded artifact for ``(task_id, tool_name, input_hash)``."""


@dataclass(frozen=True)
class ReplayRecord:
    """One serialized Tier A replay entry."""

    task_id: str
    tool: str
    input_hash: str
    artifact: Artifact

    @property
    def key(self) -> ReplayKey:
        return (self.task_id, self.tool, self.input_hash)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tool": self.tool,
            "input_hash": self.input_hash,
            "artifact": self.artifact.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReplayRecord":
        art = Artifact.from_dict(data["artifact"])
        return cls(
            task_id=str(data["task_id"]),
            tool=str(data["tool"]),
            input_hash=str(data["input_hash"]),
            artifact=art,
        )


class ReplayBox:
    """Tier A step-level replay box keyed by ``(task_id, tool_name, input_hash)``.

    Drop-in replacement for :class:`~antelligence.harness.scheduler.LiveBox` in :func:`run_graph`.
    """

    def __init__(self, records: Iterable[ReplayRecord] = ()) -> None:
        self._records: Dict[ReplayKey, Artifact] = {}
        for rec in records:
            self.put(rec.artifact, rec.input_hash)

    def put(self, artifact: Artifact, inp_hash: str) -> None:
        self._records[(artifact.task_id, artifact.tool, inp_hash)] = artifact

    def has(self, task_id: str, tool_name: str, inp_hash: str) -> bool:
        return (task_id, tool_name, inp_hash) in self._records

    def get(self, task_id: str, tool_name: str, inp_hash: str) -> Artifact:
        key = (task_id, tool_name, inp_hash)
        try:
            return self._records[key]
        except KeyError:
            raise ReplayMissError(f"no replay record for {key}") from None

    def __len__(self) -> int:
        return len(self._records)

    async def run(self, spec: ToolSpec, task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        inp_hash = input_hash(spec.input_for(task, deps))
        return self.get(task.id, spec.name, inp_hash)

    def to_jsonl(self, path: Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for (task_id, tool, inp_hash), art in sorted(self._records.items()):
                rec = ReplayRecord(task_id=task_id, tool=tool, input_hash=inp_hash, artifact=art)
                fh.write(json.dumps(rec.to_dict(), sort_keys=True) + "\n")

    @classmethod
    def from_jsonl(cls, path: Path) -> "ReplayBox":
        records = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(ReplayRecord.from_dict(json.loads(line)))
        return cls(records)


class RecordingBox:
    """Wraps a live box (or any box), delegates ``run()``, and records every step for :class:`ReplayBox`."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.records: Dict[ReplayKey, ReplayRecord] = {}

    async def run(self, spec: ToolSpec, task: Task, deps: Mapping[str, Artifact]) -> Artifact:
        inp_hash = input_hash(spec.input_for(task, deps))
        artifact = await self.inner.run(spec, task, deps)
        rec = ReplayRecord(task_id=task.id, tool=spec.name, input_hash=inp_hash, artifact=artifact)
        self.records[rec.key] = rec
        return artifact

    def to_replay_box(self) -> ReplayBox:
        return ReplayBox(self.records.values())


# ------------------------------------------------------------------ Tier B & C interfaces


@dataclass(frozen=True)
class BranchResult:
    """Outcome of one counterfactual branch starting from a Tier B :class:`EnvSnapshot`."""

    variant: str
    start_hash: str
    end_hash: str
    outcome: EpisodeOutcome


@runtime_checkable
class BranchingReplay(Protocol):
    """Tier B: checkpoint-branching counterfactual replay for stateful ``EnvAdapter`` worlds."""

    def branch(
        self,
        env: EnvAdapter,
        snapshot: EnvSnapshot,
        variants: Mapping[str, Callable[[Any], Action]],
        *,
        max_steps: int = 100,
    ) -> Dict[str, BranchResult]:
        """Restore ``snapshot`` (verifying ``state_hash``) and run each variant from the identical state."""
        ...


@dataclass(frozen=True)
class EpisodeRecord:
    """One recorded Tier C episode tuple for policy evaluation over whole-episode outcomes."""

    episode_id: str
    seed: int
    outcomes: Mapping[str, EpisodeOutcome]
    checker_result: Optional[Mapping[str, Any]] = None


@runtime_checkable
class EpisodeReplay(Protocol):
    """Tier C: episode/outcome-level replay for non-checkpointable external games & multi-turn agents."""

    def evaluate_policy(
        self,
        episodes: Sequence[EpisodeRecord],
        policy: Callable[[EpisodeRecord], str],
    ) -> Sequence[EpisodeOutcome]:
        """Select a variant per episode and return the corresponding outcomes without re-running."""
        ...
