"""Outer self-improvement governance loop with immutable guardrails, taint review, and canary gates (PR 6).

Pipeline:
  1. Hard deterministic L1 / guardrail / step-cap / taint / canary checks FIRST (never voted on).
  2. Blind commit-reveal trust-weighted quorum over ``"keep_original"`` vs surviving candidates.
  3. ``"keep_original"`` wins on any hard failure, regression, token blowup, or ``ABSTAIN`` / no-quorum.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence

from antelligence.harness.consensus import (
    ONE,
    ZERO,
    TallyResult,
    TrustLedger,
    tally_round,
)

KEEP_ORIGINAL_ID = "keep_original"

IMMUTABLE_GUARDRAIL_PATHS: tuple[str, ...] = (
    "antelligence/record/l1_gate.py",
    "antelligence/record/l0.py",
    "antelligence/kernel/",
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_POISON_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"(?:bypass|disable|skip)\s+(?:l1|guardrail|canary|verifier)", re.IGNORECASE),
    re.compile(r"override\s+(?:system|safety|budget|cap)", re.IGNORECASE),
    re.compile(r"exfiltrate|rm\s+-rf|<script", re.IGNORECASE),
)
_BLOCKED_TAGS = frozenset({"unverified_note", "untrusted", "poisoned"})


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def check_guardrail_lock(
    touched_paths: Sequence[str],
    *,
    repo_root: str | None = None,
    pinned_hashes: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    """Reject any diff touching immutable L1/guardrail/kernel paths or violating pinned file hashes."""
    for raw in touched_paths:
        norm = _norm_path(raw)
        for locked in IMMUTABLE_GUARDRAIL_PATHS:
            if locked.endswith("/"):
                if norm.startswith(locked) or norm == locked.rstrip("/"):
                    return False, f"immutable_guardrail_path:{norm}"
            elif norm == locked:
                return False, f"immutable_guardrail_path:{norm}"

    if pinned_hashes and repo_root is not None:
        for rel_path, expected_sha in sorted(pinned_hashes.items()):
            norm = _norm_path(rel_path)
            full = os.path.join(repo_root, norm)
            if not os.path.isfile(full):
                return False, f"pinned_hash_missing:{norm}"
            with open(full, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            if actual != expected_sha:
                return False, f"pinned_hash_mismatch:{norm}"
    return True, "ok"


def dynamic_step_cap(base_steps: int, headroom_steps: int, hard_l1_max_steps: int) -> int:
    """Compute allowed dynamic step cap clamped inside the hard L1 ceiling."""
    if base_steps < 0 or headroom_steps < 0 or hard_l1_max_steps <= 0:
        raise ValueError("step caps must be non-negative and hard_l1_max_steps > 0")
    return min(base_steps + headroom_steps, hard_l1_max_steps)


@dataclass(frozen=True)
class ProposedMemoryEntry:
    entry_id: str
    content: str
    verified: bool
    provenance_sha256: str
    tag: str = "verified"
    source_path: str = "library_proposed/entry.json"


def review_library_proposed(entries: Sequence[ProposedMemoryEntry]) -> tuple[bool, str]:
    """Quarantine check for ``library_proposed/``: blocks unverified, untrusted, or poisoned lines."""
    for entry in entries:
        if not entry.verified:
            return False, f"unverified_memory:{entry.entry_id}"
        if entry.tag in _BLOCKED_TAGS:
            return False, f"blocked_memory_tag:{entry.entry_id}:{entry.tag}"
        if not _HEX64_RE.fullmatch(entry.provenance_sha256):
            return False, f"missing_provenance:{entry.entry_id}"
        for pat in _POISON_PATTERNS:
            if pat.search(entry.content):
                return False, f"poisoned_memory:{entry.entry_id}"
    return True, "ok"


@dataclass(frozen=True)
class CanaryMetrics:
    score: Decimal
    tokens: int
    spend_microusd: int


def check_canary(
    candidate: CanaryMetrics,
    baseline: CanaryMetrics,
    *,
    max_regression: Decimal = ZERO,
    max_token_multiplier: Decimal = Decimal("1.5"),
    hard_l1_spend_microusd: int | None = None,
) -> tuple[bool, str]:
    """Deterministic cross-task canary check rejecting regression, token blowup, or L1 spend breach."""
    if candidate.score < baseline.score - max_regression:
        return False, "canary_regression"
    if baseline.tokens > 0 and Decimal(candidate.tokens) > Decimal(baseline.tokens) * max_token_multiplier:
        return False, "canary_token_blowup"
    if hard_l1_spend_microusd is not None and candidate.spend_microusd > hard_l1_spend_microusd:
        return False, "hard_l1_spend_exceeded"
    return True, "ok"


@dataclass(frozen=True)
class EvolutionCandidate:
    candidate_id: str
    diff_sha256: str
    touched_paths: tuple[str, ...]
    proposed_step_cap: int
    canary: CanaryMetrics
    memory_entries: tuple[ProposedMemoryEntry, ...] = ()


@dataclass(frozen=True)
class EvolutionDecision:
    winner_id: str
    promoted: bool
    reason: str
    hard_rejections: dict[str, str] = field(default_factory=dict)
    tallies: dict[str, TallyResult] = field(default_factory=dict)


def evaluate_evolution(
    candidates: Sequence[EvolutionCandidate],
    baseline_canary: CanaryMetrics,
    *,
    ledger: TrustLedger,
    roster: Sequence[str],
    reveals_by_candidate: Mapping[str, Mapping[str, Mapping[str, object]]],
    hard_l1_max_steps: int,
    base_steps: int,
    headroom_steps: int,
    hard_l1_spend_microusd: int | None = None,
    max_regression: Decimal = ZERO,
    max_token_multiplier: Decimal = Decimal("1.5"),
    repo_root: str | None = None,
    pinned_hashes: Mapping[str, str] | None = None,
    require_past_probation: bool = False,
) -> EvolutionDecision:
    """Run hard L1/guardrail/taint/canary checks first, then blind quorum over survivors."""
    allowed_steps = dynamic_step_cap(base_steps, headroom_steps, hard_l1_max_steps)
    hard_rejections: dict[str, str] = {}
    survivors: list[EvolutionCandidate] = []

    for cand in candidates:
        if cand.candidate_id == KEEP_ORIGINAL_ID:
            continue
        ok, reason = check_guardrail_lock(cand.touched_paths, repo_root=repo_root, pinned_hashes=pinned_hashes)
        if not ok:
            hard_rejections[cand.candidate_id] = reason
            continue
        if cand.proposed_step_cap <= 0 or cand.proposed_step_cap > allowed_steps or cand.proposed_step_cap > hard_l1_max_steps:
            hard_rejections[cand.candidate_id] = "step_cap_exceeded"
            continue
        ok, reason = review_library_proposed(cand.memory_entries)
        if not ok:
            hard_rejections[cand.candidate_id] = reason
            continue
        ok, reason = check_canary(
            cand.canary,
            baseline_canary,
            max_regression=max_regression,
            max_token_multiplier=max_token_multiplier,
            hard_l1_spend_microusd=hard_l1_spend_microusd,
        )
        if not ok:
            hard_rejections[cand.candidate_id] = reason
            continue
        survivors.append(cand)

    if not survivors:
        return EvolutionDecision(
            winner_id=KEEP_ORIGINAL_ID,
            promoted=False,
            reason="all_candidates_failed_hard_checks",
            hard_rejections=hard_rejections,
        )

    tallies: dict[str, TallyResult] = {}
    promoted_pool: list[tuple[Decimal, int, str, EvolutionCandidate]] = []
    for cand in survivors:
        res = tally_round(
            round_id=f"evolve-{cand.candidate_id}",
            ledger=ledger,
            roster=roster,
            valid_reveals=reveals_by_candidate.get(cand.candidate_id, {}),
            hard_checks_passed=True,
            require_past_probation=require_past_probation,
        )
        tallies[cand.candidate_id] = res
        if res.decision == "PROMOTE" and res.w_part > ZERO:
            share = res.w_promote / res.w_part
            promoted_pool.append((-share, cand.canary.spend_microusd, cand.diff_sha256, cand))

    if not promoted_pool:
        return EvolutionDecision(
            winner_id=KEEP_ORIGINAL_ID,
            promoted=False,
            reason="abstain_or_no_quorum",
            hard_rejections=hard_rejections,
            tallies=tallies,
        )

    promoted_pool.sort(key=lambda item: (item[0], item[1], item[2]))
    best = promoted_pool[0][3]
    return EvolutionDecision(
        winner_id=best.candidate_id,
        promoted=True,
        reason="supermajority_promote",
        hard_rejections=hard_rejections,
        tallies=tallies,
    )
