"""Legacy MCQ compatibility adapter ($0 night-run / AGIEval parity) + surface/syllogism shortcut audit."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional, Sequence

from antelligence.harness.core import Artifact, Task

_LETTER_RE = re.compile(r"\b([A-E])\b")
_SYLLOGISM_CUES = ("all ", "some ", "none ", "no ", "therefore", "thus", "must be true", "cannot be")


class MCQCompatAdapter:
    """``TaskAdapter`` for legacy MCQ / AGIEval / night-run fixtures."""

    def format_input(self, task: Task) -> str:
        q = task.payload.get("question") or task.payload.get("prompt") or ""
        opts = task.payload.get("options") or task.payload.get("choices") or {}
        if isinstance(opts, Mapping):
            lines = [f"{k}) {v}" for k, v in opts.items()]
        else:
            lines = [f"{chr(65 + i)}) {v}" for i, v in enumerate(opts)]
        return f"{q}\n" + "\n".join(lines)

    def parse_output(self, task: Task, raw: str, *, tool: str = "mcq_compat") -> Artifact:
        text = raw.strip()
        answer: Optional[str] = None
        format_ok = False
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and isinstance(obj.get("answer"), str):
                answer = obj["answer"].strip().upper()
                format_ok = len(answer) == 1 and answer in "ABCDE"
        except json.JSONDecodeError:
            m = _LETTER_RE.search(text.upper())
            if m:
                answer = m.group(1)
                format_ok = True
        return Artifact(
            task_id=task.id,
            tool=tool,
            answer=answer,
            format_ok=format_ok,
            error=None if format_ok else "unparsed_mcq_answer",
            payload={"raw": raw, "lenient_ok": format_ok},
        )

    def score(self, task: Task, artifact: Artifact) -> Optional[float]:
        if not artifact.format_ok:
            return 0.0
        gold = str(task.payload.get("answer") or task.payload.get("gold") or "").strip().upper()
        return 1.0 if str(artifact.answer or "").strip().upper() == gold else 0.0

    def audit_shortcuts(self, tasks: Sequence[Task]) -> Dict[str, Any]:
        """Flag surface/syllogism shortcuts (e.g. option-length or syllogism-cue heuristic >= 50%)."""
        if not tasks:
            return {"n": 0, "chance": 0.25, "shortcut_rate": 0.0, "shortcut_flagged": False}
        hits = 0
        n_opts_total = 0
        for t in tasks:
            opts = t.payload.get("options") or t.payload.get("choices") or {}
            if isinstance(opts, Mapping):
                items = list(opts.items())
            else:
                items = [(chr(65 + i), str(v)) for i, v in enumerate(opts)]
            if not items:
                continue
            n_opts_total += len(items)
            # Surface/syllogism heuristic: longest option or option containing syllogism cue words
            def _cue_score(kv: tuple) -> tuple:
                text = str(kv[1]).lower()
                cues = sum(1 for c in _SYLLOGISM_CUES if c in text)
                return (cues, len(text))

            guess = max(items, key=_cue_score)[0]
            gold = str(t.payload.get("answer") or t.payload.get("gold") or "").strip().upper()
            if str(guess).strip().upper() == gold:
                hits += 1
        chance = 1.0 / max(2, round(n_opts_total / max(1, len(tasks))))
        rate = hits / len(tasks)
        return {
            "n": len(tasks),
            "chance": round(chance, 4),
            "shortcut_rate": round(rate, 4),
            "shortcut_flagged": rate >= max(0.50, chance + 0.20),
        }
