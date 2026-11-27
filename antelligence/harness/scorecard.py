"""Domain-agnostic scorecard: honest per-task billing and numpy-vectorized paired bootstrap comparison.

Every task run produces an :class:`Outcome` with its answer, ``format_ok`` flag, optional capability ``score``,
and full resource bill (``tokens_in``, ``tokens_out``, ``fresh_tokens``, ``seconds``, ``cost_usd``, ``calls``).
"""

from __future__ import annotations

import json
import statistics as st
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from antelligence.harness.core import Artifact, Task


@dataclass(frozen=True)
class Outcome:
    """One task's result and full honest bill for one harness variant."""

    task: str
    kind: str
    variant: str
    answer: Any = None
    score: Optional[float] = None
    format_ok: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    fresh_tokens: Optional[int] = None
    seconds: float = 0.0
    cost_usd: float = 0.0
    calls: int = 0
    tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Outcome":
        return cls(**dict(data))


def bill(
    task: Task,
    variant: str,
    answer: Any,
    artifacts: Sequence[Artifact],
    *,
    score: Optional[float] = None,
    format_ok: Optional[bool] = None,
    fresh_tokens: Optional[int] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Outcome:
    """Aggregate a sequence of :class:`Artifact` steps into one :class:`Outcome`."""
    fmt_ok = all(a.format_ok for a in artifacts) if format_ok is None else format_ok
    return Outcome(
        task=task.id,
        kind=task.kind,
        variant=variant,
        answer=answer,
        score=score,
        format_ok=fmt_ok,
        tokens_in=sum(a.tokens_in for a in artifacts),
        tokens_out=sum(a.tokens_out for a in artifacts),
        fresh_tokens=fresh_tokens,
        seconds=round(sum(a.latency_s for a in artifacts), 4),
        cost_usd=round(sum(a.cost_usd for a in artifacts), 6),
        calls=sum(a.calls for a in artifacts),
        tools=[a.tool for a in artifacts],
        metadata=dict(metadata or {}),
    )


class OutcomeLog:
    """Append-only JSON-lines log of :class:`Outcome` records."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def add(self, outcome: Outcome) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(outcome.to_json(), sort_keys=True) + "\n")

    def read(self) -> List[Outcome]:
        if not self.path.exists():
            return []
        return [
            Outcome.from_json(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


# ------------------------------------------------------------------ prefix-cache fresh_in


def _lcp(a: str, b: str) -> int:
    """Length of the longest common prefix (binary search on slices)."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def fresh_in(
    artifacts: Sequence[Artifact],
    prompt_texts: Mapping[str, str],
    model_for_tool: Callable[[str], Optional[str]],
    rate: Mapping[str, float],
    *,
    measured: bool = False,
    min_prefix_chars: int = 40,
) -> List[int]:
    """For each step, estimate the prompt tokens its model had to read fresh (excluding shared prefix cache).

    Ported from ``borrowed.py:fresh_in`` and made domain-agnostic: callers supply ``prompt_texts``
    (tool_name -> rendered prompt) and ``model_for_tool`` (tool_name -> model_key or None).
    """
    seen: Dict[str, List[str]] = {}
    shared_cache: Dict[Tuple[str, str], int] = {}
    out: List[int] = []
    for art in artifacts:
        cached: Optional[float] = None
        if measured and isinstance(art.payload.get("cached_in"), int):
            cached = float(art.payload["cached_in"])
        model = model_for_tool(art.tool)
        text = prompt_texts.get(art.tool) if model else None
        if cached is None and text is not None and model is not None:
            r = rate.get(model, 0.0)
            prev = 0
            for t in seen.get(model, ()):
                k = (art.tool, t) if art.tool <= t else (t, art.tool)
                if k not in shared_cache:
                    other = prompt_texts.get(t)
                    shared_cache[k] = _lcp(text, other) if other else 0
                if shared_cache[k] > prev:
                    prev = shared_cache[k]
            cached = prev * r if prev >= min_prefix_chars else 0.0
            if art.calls >= 2:
                cached += len(text) * r
        if text is not None and model is not None:
            seen.setdefault(model, []).append(art.tool)
        out.append(max(0, art.tokens_in - int(round(min(cached or 0.0, float(art.tokens_in))))))
    return out


# ------------------------------------------------------------------ numpy-vectorized bootstrap & summary


def paired_bootstrap(
    diffs: Sequence[float],
    reps: int = 10000,
    seed: int = 20261029,
) -> Tuple[float, float, float]:
    """Vectorized paired bootstrap for ``(mean, ci95_lo, ci95_hi)``."""
    arr = np.asarray(diffs, dtype=np.float64)
    n = int(arr.size)
    if n == 0:
        raise ValueError("diffs must be non-empty")
    if reps < 1:
        raise ValueError("reps must be positive")
    rng = np.random.default_rng(seed)
    idx_dtype = np.int16 if n < 32768 else np.int32
    means = np.empty(reps, dtype=np.float64)
    # Chunk rows so index/gather buffers stay in L2 cache without large allocations
    step = max(1, min(reps, 250_000 // max(1, n)))
    for start in range(0, reps, step):
        k = min(step, reps - start)
        idx = rng.integers(0, n, size=(k, n), dtype=idx_dtype)
        means[start : start + k] = arr[idx].mean(axis=1)
    means.sort()
    lo_idx = int(0.025 * reps)
    hi_idx = max(0, int(0.975 * reps) - 1)
    return float(arr.mean()), float(means[lo_idx]), float(means[hi_idx])


def ratio_ranges(
    pairs: Sequence[Tuple[Outcome, Outcome]],
    reps: int = 2000,
    seed: int = 20261102,
) -> Dict[str, List[float]]:
    """Vectorized 95% bootstrap ranges for tokens and seconds ratios (ours / baseline)."""
    if not pairs:
        return {"tokens_ratio_ci95": [1.0, 1.0], "seconds_ratio_ci95": [1.0, 1.0]}
    n = len(pairs)
    tp_arr = np.fromiter((o.tokens for o, _ in pairs), dtype=np.float64, count=n)
    tb_arr = np.fromiter((b.tokens for _, b in pairs), dtype=np.float64, count=n)
    sp_arr = np.fromiter((o.seconds for o, _ in pairs), dtype=np.float64, count=n)
    sb_arr = np.fromiter((b.seconds for _, b in pairs), dtype=np.float64, count=n)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(reps, n))

    tb_sum = tb_arr[idx].sum(axis=1)
    tp_sum = tp_arr[idx].sum(axis=1)
    tok = np.where(tb_sum != 0, tp_sum / np.where(tb_sum != 0, tb_sum, 1.0), 1.0)
    tok.sort()

    sb_sum = sb_arr[idx].sum(axis=1)
    sp_sum = sp_arr[idx].sum(axis=1)
    sec = np.where(sb_sum != 0, sp_sum / np.where(sb_sum != 0, sb_sum, 1.0), 1.0)
    sec.sort()

    lo = int(0.025 * reps)
    hi = max(0, int(0.975 * reps) - 1)
    return {
        "tokens_ratio_ci95": [round(float(tok[lo]), 3), round(float(tok[hi]), 3)],
        "seconds_ratio_ci95": [round(float(sec[lo]), 3), round(float(sec[hi]), 3)],
    }


def _mean(xs: Iterable[float]) -> float:
    vals = list(xs)
    return st.mean(vals) if vals else 0.0


def totals(outs: Sequence[Outcome]) -> Dict[str, Any]:
    scored = [o.score for o in outs if o.score is not None]
    fmt_rate = _mean(1.0 if o.format_ok else 0.0 for o in outs) if outs else None
    return {
        "n": len(outs),
        "score": round(_mean(scored), 4) if scored else None,
        "format_ok_rate": round(fmt_rate, 4) if fmt_rate is not None else None,
        "tokens": round(_mean(o.tokens for o in outs), 1),
        "seconds": round(_mean(o.seconds for o in outs), 3),
        "cost_usd": round(sum(o.cost_usd for o in outs), 6),
        "calls": round(_mean(o.calls for o in outs), 2),
    }


def verdict(lo: float, hi: float, tokens_ratio: float, seconds_ratio: float) -> str:
    cheaper = tokens_ratio < 1.0 and seconds_ratio < 1.0
    if lo > 0 and cheaper:
        return "beats it on all three"
    if lo > 0:
        return "more accurate, but not cheaper on both tokens and time"
    if hi < 0:
        return "less accurate"
    if cheaper:
        return "ties it on accuracy, and is cheaper on both"
    return "ties it on accuracy, not cheaper on both"


def compare(
    outs: Sequence[Outcome],
    base: Sequence[Outcome],
    *,
    ranges: bool = True,
    reps: int = 4000,
    seed: int = 20261029,
) -> Dict[str, Any]:
    """Paired comparison on tasks present and scored in both ``outs`` and ``base``."""
    b = {o.task: o for o in base}
    pairs = [
        (o, b[o.task])
        for o in outs
        if o.task in b and o.score is not None and b[o.task].score is not None
    ]
    if not pairs:
        return {"n": 0}
    gain, lo, hi = paired_bootstrap(
        [o.score - p.score for o, p in pairs if o.score is not None and p.score is not None],
        reps=reps,
        seed=seed,
    )
    tb, tp = _mean(p.tokens for _, p in pairs), _mean(o.tokens for o, _ in pairs)
    sb, sp = _mean(p.seconds for _, p in pairs), _mean(o.seconds for o, _ in pairs)
    cb, cp = _mean(p.cost_usd for _, p in pairs), _mean(o.cost_usd for o, _ in pairs)
    tok_ratio = tp / tb if tb else 1.0
    sec_ratio = sp / sb if sb else 1.0
    return {
        "n": len(pairs),
        "score_gain": round(gain, 4),
        "score_ci95": [round(lo, 4), round(hi, 4)],
        "tokens_ratio": round(tok_ratio, 3) if tb else None,
        "seconds_ratio": round(sec_ratio, 3) if sb else None,
        "cost_ratio": round(cp / cb, 3) if cb else None,
        "verdict": verdict(lo, hi, tok_ratio, sec_ratio),
        **(ratio_ranges(pairs) if ranges else {}),
    }


def summary(outs: Sequence[Outcome], baseline: str = "baseline") -> Dict[str, Any]:
    """Per-variant totals and paired comparison against ``baseline``."""
    by: Dict[str, List[Outcome]] = {}
    for o in outs:
        by.setdefault(o.variant, []).append(o)
    base = by.get(baseline, [])
    return {
        name: {**totals(rs), f"vs_{baseline}": compare(rs, base) if name != baseline and base else None}
        for name, rs in sorted(by.items())
    }


def pareto(table: Mapping[str, Mapping[str, Any]]) -> List[str]:
    """Variants that no other variant dominates on ``(score, -tokens, -seconds)``."""
    rows = {k: v for k, v in table.items() if v.get("score") is not None}
    out = []
    for k, v in rows.items():
        dominated = any(
            w["score"] >= v["score"]
            and w["tokens"] <= v["tokens"]
            and w["seconds"] <= v["seconds"]
            and (w["score"], -w["tokens"], -w["seconds"]) != (v["score"], -v["tokens"], -v["seconds"])
            for j, w in rows.items()
            if j != k
        )
        if not dominated:
            out.append(k)
    return sorted(out, key=lambda k: -rows[k]["score"])
