"""Task adapters and Eval Hygiene Gate for Harness vNext."""

from antelligence.harness.adapters.curated_real import (
    CANONICAL_LABELS,
    CuratedRealTriageAdapter,
    EvalHygieneError,
    EvalHygieneReport,
    HoldoutGuard,
    TFIDFBaseline,
    eval_hygiene_gate,
    load_gh_archive_jsonl,
    parse_gh_archive_event,
)
from antelligence.harness.adapters.mcq_compat import MCQCompatAdapter

__all__ = [
    "CANONICAL_LABELS",
    "CuratedRealTriageAdapter",
    "EvalHygieneError",
    "EvalHygieneReport",
    "HoldoutGuard",
    "MCQCompatAdapter",
    "TFIDFBaseline",
    "eval_hygiene_gate",
    "load_gh_archive_jsonl",
    "parse_gh_archive_event",
]
