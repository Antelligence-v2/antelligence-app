"""Calibration Gate, serializable split-conformal/threshold escalation Policy, and gated CDM wrapper.

Enforces Harness vNext Invariants #2 and #3:
  - Calibration Gate: raw SLM logprobs are explicitly banned; any confidence/conformal gate must pass
    held-out ECE, Brier, and AURC verification before activation.
  - CDMs gated strictly to <= 20 fixed labels + "other" with seeded option shuffling.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from antelligence.kernel.canonical import canonical_json, content_hash

EPS = 1e-12
MAX_CDM_LABELS = 20


class CalibrationError(ValueError):
    """Raised when calibration inputs are invalid or fail the Calibration Gate."""


class UncalibratedGateError(CalibrationError):
    """Raised when an uncalibrated gate or raw SLM logprobs are used for routing/escalation."""


class CDMGateError(ValueError):
    """Raised when a CDM wrapper is used outside its proven niche (<= 20 labels + 'other')."""


def compute_ece(confidences: Sequence[float], correct: Sequence[Union[bool, int, float]], n_bins: int = 10) -> float:
    """Expected Calibration Error across ``n_bins`` equal-width confidence bins."""
    confs = np.asarray(confidences, dtype=np.float64)
    corr = np.asarray(correct, dtype=np.float64)
    if len(confs) == 0 or len(confs) != len(corr):
        raise CalibrationError("confidences and correct must be non-empty and equal length")
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = float(len(confs))
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (confs >= lo) & (confs <= hi if i == n_bins - 1 else confs < hi)
        if np.any(mask):
            ece += (np.sum(mask) / n) * abs(float(np.mean(corr[mask])) - float(np.mean(confs[mask])))
    return float(ece)


def compute_brier(confidences: Sequence[float], correct: Sequence[Union[bool, int, float]]) -> float:
    """Brier score: mean squared error between predicted confidence and binary correctness."""
    confs = np.asarray(confidences, dtype=np.float64)
    corr = np.asarray(correct, dtype=np.float64)
    if len(confs) == 0 or len(confs) != len(corr):
        raise CalibrationError("confidences and correct must be non-empty and equal length")
    return float(np.mean((confs - corr) ** 2))


def compute_aurc(confidences: Sequence[float], correct: Sequence[Union[bool, int, float]]) -> float:
    """Area Under the Risk-Coverage Curve (lower is better; 0 = perfect selective prediction)."""
    confs = np.asarray(confidences, dtype=np.float64)
    corr = np.asarray(correct, dtype=np.float64)
    if len(confs) == 0 or len(confs) != len(corr):
        raise CalibrationError("confidences and correct must be non-empty and equal length")
    order = np.argsort(-confs, kind="mergesort")
    sorted_err = 1.0 - corr[order]
    n = len(sorted_err)
    cum_err = np.cumsum(sorted_err)
    coverages = np.arange(1, n + 1, dtype=np.float64) / n
    risks = cum_err / np.arange(1, n + 1, dtype=np.float64)
    return float(np.trapz(risks, coverages) if hasattr(np, "trapz") else np.trapezoid(risks, coverages))


@dataclass(frozen=True)
class CalibrationReport:
    n: int
    ece: float
    brier: float
    aurc: float
    passed: bool
    source: str
    max_ece: float = 0.12
    max_brier: float = 0.25
    max_aurc: float = 0.35
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalibrationReport":
        return cls(**dict(data))


class CalibrationGate:
    """Verifies held-out ECE, Brier, and AURC before allowing confidence/conformal gating."""

    def __init__(self, *, max_ece: float = 0.12, max_brier: float = 0.25, max_aurc: float = 0.35) -> None:
        self.max_ece = max_ece
        self.max_brier = max_brier
        self.max_aurc = max_aurc

    def evaluate(
        self,
        confidences: Sequence[float],
        correct: Sequence[Union[bool, int, float]],
        *,
        source: str = "calibrated",
        is_raw_logprobs: bool = False,
    ) -> CalibrationReport:
        if is_raw_logprobs or source.strip().lower() in ("raw_logprobs", "raw_slm_logprobs", "logprobs"):
            raise UncalibratedGateError("raw SLM logprobs are banned from confidence gating")
        ece = compute_ece(confidences, correct)
        brier = compute_brier(confidences, correct)
        aurc = compute_aurc(confidences, correct)
        failures: List[str] = []
        if ece > self.max_ece:
            failures.append(f"ece={ece:.4f}>{self.max_ece}")
        if brier > self.max_brier:
            failures.append(f"brier={brier:.4f}>{self.max_brier}")
        if aurc > self.max_aurc:
            failures.append(f"aurc={aurc:.4f}>{self.max_aurc}")
        return CalibrationReport(
            n=len(confidences),
            ece=round(ece, 6),
            brier=round(brier, 6),
            aurc=round(aurc, 6),
            passed=not failures,
            source=source,
            max_ece=self.max_ece,
            max_brier=self.max_brier,
            max_aurc=self.max_aurc,
            reason="; ".join(failures),
        )


def nonconformity(probs: Mapping[str, float], label: str) -> float:
    if label not in probs:
        raise CalibrationError(f"label {label!r} not in offered labels {sorted(probs)}")
    return 1.0 - float(probs[label])


def conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Split-conformal quantile: ceil((n+1)(1-alpha))-th smallest score; +inf when rank > n."""
    n = len(scores)
    if n == 0:
        raise CalibrationError("no calibration scores")
    if not 0.0 < alpha < 1.0:
        raise CalibrationError("alpha must be in (0, 1)")
    rank = math.ceil((n + 1) * (1.0 - alpha))
    return math.inf if rank > n else sorted(scores)[rank - 1]


def prediction_set(probs: Mapping[str, float], qhat: float) -> Tuple[str, ...]:
    """Labels with ``1 - p(l) <= qhat`` in deterministic key order."""
    return tuple(lbl for lbl in probs if 1.0 - float(probs[lbl]) <= qhat + EPS)


def defers(label_set: Sequence[str]) -> bool:
    """Defer unless the conformal prediction set contains exactly one label."""
    return len(label_set) != 1


@dataclass(frozen=True)
class EscalationDecision:
    escalate: bool
    prediction_set: Tuple[str, ...]
    confidence: float
    reason: str


@dataclass(frozen=True)
class Policy:
    """Serializable escalation policy gated by :class:`CalibrationGate`."""

    kind: str  # "conformal" | "threshold"
    qhat: Optional[float] = None
    alpha: Optional[float] = None
    confidence_threshold: Optional[float] = None
    calibration: Optional[CalibrationReport] = None

    def body(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "qhat": None if (self.qhat is not None and math.isinf(self.qhat)) else self.qhat,
            "alpha": self.alpha,
            "confidence_threshold": self.confidence_threshold,
            "calibration": self.calibration.to_dict() if self.calibration is not None else None,
        }

    @property
    def sha256(self) -> str:
        return content_hash(self.body())

    def save(self, path: Union[str, Path]) -> str:
        Path(path).write_text(canonical_json({"body": self.body(), "sha256": self.sha256}) + "\n", encoding="utf-8")
        return self.sha256

    @classmethod
    def load(cls, path: Union[str, Path], expect_sha256: Optional[str] = None) -> "Policy":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        body = doc["body"]
        if content_hash(body) != doc["sha256"] or (expect_sha256 and doc["sha256"] != expect_sha256):
            raise CalibrationError(f"{path}: policy does not match its sha256")
        cal = CalibrationReport.from_dict(body["calibration"]) if body.get("calibration") else None
        qhat = math.inf if (body["kind"] == "conformal" and body.get("qhat") is None) else body.get("qhat")
        return cls(
            kind=body["kind"],
            qhat=qhat,
            alpha=body.get("alpha"),
            confidence_threshold=body.get("confidence_threshold"),
            calibration=cal,
        )

    @classmethod
    def fit_conformal(
        cls,
        dev_probs: Sequence[Mapping[str, float]],
        dev_labels: Sequence[str],
        *,
        alpha: float = 0.15,
        gate: Optional[CalibrationGate] = None,
        source: str = "calibrated",
        is_raw_logprobs: bool = False,
    ) -> "Policy":
        if not dev_probs or len(dev_probs) != len(dev_labels):
            raise CalibrationError("dev_probs and dev_labels must be non-empty and equal length")
        cal_gate = gate or CalibrationGate()
        confs = [max(float(p) for p in d.values()) for d in dev_probs]
        preds = [max(d, key=lambda k: float(d[k])) for d in dev_probs]
        corr = [p == y for p, y in zip(preds, dev_labels)]
        report = cal_gate.evaluate(confs, corr, source=source, is_raw_logprobs=is_raw_logprobs)
        if not report.passed:
            raise UncalibratedGateError(f"calibration gate blocked policy: {report.reason}")
        scores = [nonconformity(p, y) for p, y in zip(dev_probs, dev_labels)]
        qhat = conformal_quantile(scores, alpha)
        return cls(kind="conformal", qhat=qhat, alpha=alpha, calibration=report)

    @classmethod
    def fit_threshold(
        cls,
        dev_confidences: Sequence[float],
        dev_correct: Sequence[Union[bool, int, float]],
        *,
        confidence_threshold: float = 0.75,
        gate: Optional[CalibrationGate] = None,
        source: str = "calibrated",
        is_raw_logprobs: bool = False,
    ) -> "Policy":
        cal_gate = gate or CalibrationGate()
        report = cal_gate.evaluate(dev_confidences, dev_correct, source=source, is_raw_logprobs=is_raw_logprobs)
        if not report.passed:
            raise UncalibratedGateError(f"calibration gate blocked policy: {report.reason}")
        return cls(kind="threshold", confidence_threshold=confidence_threshold, calibration=report)

    def decide(
        self,
        probs_or_conf: Union[Mapping[str, float], float],
        *,
        is_raw_logprobs: bool = False,
    ) -> EscalationDecision:
        if is_raw_logprobs:
            raise UncalibratedGateError("raw SLM logprobs are banned from escalation decisions")
        if self.calibration is None or not self.calibration.passed:
            raise UncalibratedGateError("policy cannot activate without passing CalibrationGate")
        if self.kind == "conformal":
            if not isinstance(probs_or_conf, Mapping) or self.qhat is None:
                raise CalibrationError("conformal policy requires a label->prob mapping")
            pset = prediction_set(probs_or_conf, self.qhat)
            conf = max((float(v) for v in probs_or_conf.values()), default=0.0)
            esc = defers(pset)
            return EscalationDecision(esc, pset, conf, "conformal_set_size!=1" if esc else "conformal_singleton")
        if self.kind == "threshold":
            conf = max(float(v) for v in probs_or_conf.values()) if isinstance(probs_or_conf, Mapping) else float(probs_or_conf)
            thr = 0.75 if self.confidence_threshold is None else self.confidence_threshold
            esc = conf < thr
            return EscalationDecision(esc, (), conf, f"conf<{thr}" if esc else "conf>=thr")
        raise CalibrationError(f"unknown policy kind: {self.kind!r}")


class CDMWrapper:
    """Constrained Decision Module wrapper gated strictly to <= 20 fixed labels + 'other' with seeded shuffling."""

    def __init__(self, labels: Sequence[str], *, seed: int = 0) -> None:
        unique = tuple(dict.fromkeys(labels))
        if len(unique) < 2 or len(unique) > MAX_CDM_LABELS:
            raise CDMGateError(f"CDM requires 2..{MAX_CDM_LABELS} fixed labels, got {len(unique)}")
        if "other" not in unique:
            raise CDMGateError("CDM requires 'other' in the fixed label set")
        self.labels = unique
        self.seed = seed

    def shuffled_options(self, task_id: str) -> Tuple[str, ...]:
        """Deterministically shuffle options per ``(seed, task_id)`` to eliminate first-option bias."""
        order = list(self.labels)
        rng = random.Random(f"{self.seed}:{task_id}")
        rng.shuffle(order)
        return tuple(order)

    def unshuffle_probs(self, shuffled_probs: Mapping[str, float]) -> Dict[str, float]:
        """Map shuffled option probabilities back to canonical label order."""
        return {lbl: float(shuffled_probs.get(lbl, 0.0)) for lbl in self.labels}
