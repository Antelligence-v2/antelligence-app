"""Curated real-world adapter: GitHub Issue Triage (K=8 closed labels + verbatim evidence span).

Includes:
  - Offline GH Archive JSONL / .jsonl.gz parser (IssuesEvent, bot/self-label filtered, PII-stripped).
  - Pure-numpy TF-IDF hashing + L2 LogisticRegression strong scripted baseline `S`.
  - Eval Hygiene Gate (S baseline check, shortcut/blind audit, strict vs lenient format_ok, holdout double-peek).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from antelligence.harness.core import Artifact, Task, TaskAdapter
from antelligence.harness.verifiers import Verifier

CANONICAL_LABELS: Tuple[str, ...] = (
    "bug",
    "feature_enhancement",
    "documentation",
    "question_support",
    "build_ci_packaging",
    "performance",
    "security",
    "other",
)

LABEL_ALIASES: Mapping[str, str] = {
    "bug": "bug",
    "defect": "bug",
    "crash": "bug",
    "regression": "bug",
    "feature": "feature_enhancement",
    "enhancement": "feature_enhancement",
    "feature_enhancement": "feature_enhancement",
    "feature-request": "feature_enhancement",
    "docs": "documentation",
    "documentation": "documentation",
    "question": "question_support",
    "support": "question_support",
    "question_support": "question_support",
    "help wanted": "question_support",
    "build": "build_ci_packaging",
    "ci": "build_ci_packaging",
    "packaging": "build_ci_packaging",
    "build_ci_packaging": "build_ci_packaging",
    "performance": "performance",
    "perf": "performance",
    "security": "security",
    "vulnerability": "security",
    "cve": "security",
    "other": "other",
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


class EvalHygieneError(ValueError):
    """Raised when an evaluation fails the Eval Hygiene Gate (e.g., holdout double-peek)."""


def strip_pii(text: str) -> str:
    return _EMAIL_RE.sub("[EMAIL]", text)


def map_github_label(raw_label: str) -> Optional[str]:
    norm = raw_label.strip().lower()
    if norm in LABEL_ALIASES:
        return LABEL_ALIASES[norm]
    for key, canonical in LABEL_ALIASES.items():
        if key in norm:
            return canonical
    return None


def parse_gh_archive_event(event: Mapping[str, Any]) -> Optional[Task]:
    """Parse one GH Archive ``IssuesEvent`` into a ``Task``, filtering bots, self-labeling, and multi-comment issues."""
    if event.get("type") != "IssuesEvent":
        return None
    payload = event.get("payload") or {}
    if payload.get("action") != "labeled":
        return None
    issue = payload.get("issue") or {}
    if int(issue.get("comments") or 0) != 0:
        return None
    actor = str((event.get("actor") or {}).get("login") or "")
    author = str((issue.get("user") or {}).get("login") or "")
    if not actor or actor.endswith("[bot]") or actor == author:
        return None

    raw_lbl = str((payload.get("label") or {}).get("name") or "")
    canonical = map_github_label(raw_lbl)
    if canonical is None:
        return None

    title = strip_pii(str(issue.get("title") or "").strip())
    body = strip_pii(str(issue.get("body") or "").strip())
    if not title and not body:
        return None
    repo = str((event.get("repo") or {}).get("name") or "")
    issue_id = str(event.get("id") or issue.get("id") or hashlib.sha256(f"{repo}:{title}".encode()).hexdigest()[:12])
    return Task(
        id=f"gh-{issue_id}",
        kind="gh_issue_triage",
        payload={"title": title, "body": body, "label": canonical, "raw_label": raw_lbl, "repo": repo},
        created_at=event.get("created_at") or issue.get("created_at"),
    )


def load_gh_archive_jsonl(path: Union[str, Path]) -> List[Task]:
    """Load and filter GH Archive events from a local ``.jsonl`` or ``.jsonl.gz`` file."""
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    tasks: List[Task] = []
    with opener(p, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            task = parse_gh_archive_event(json.loads(line))
            if task is not None:
                tasks.append(task)
    return tasks


def _task_source_text(task: Task) -> str:
    title = str(task.payload.get("title") or "")
    body = str(task.payload.get("body") or "")
    return f"{title}\n{body}".strip()


def _tokenize(text: str) -> List[str]:
    toks = _TOKEN_RE.findall(text.lower())
    bigrams = [f"{toks[i]}_{toks[i + 1]}" for i in range(len(toks) - 1)]
    return toks + bigrams


class TFIDFBaseline:
    """Pure-numpy feature-hashed TF-IDF + L2-regularized Multinomial Logistic Regression (scripted `S`)."""

    def __init__(self, labels: Sequence[str] = CANONICAL_LABELS, *, n_features: int = 512,
                 reg: float = 1e-3, lr: float = 0.8, epochs: int = 120) -> None:
        self.labels = tuple(labels)
        self._lbl_to_idx = {l: i for i, l in enumerate(self.labels)}
        self.n_features = n_features
        self.reg = reg
        self.lr = lr
        self.epochs = epochs
        self.idf: Optional[np.ndarray] = None
        self.weights: Optional[np.ndarray] = None
        self.bias: Optional[np.ndarray] = None

    def _tf_vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.n_features, dtype=np.float64)
        for tok in _tokenize(text):
            idx = zlib.crc32(tok.encode("utf-8")) % self.n_features
            vec[idx] += 1.0
        return vec

    def _featurize(self, texts: Sequence[str], *, fit_idf: bool = False) -> np.ndarray:
        tf = np.vstack([self._tf_vector(t) for t in texts])
        if fit_idf or self.idf is None:
            df = np.sum(tf > 0, axis=0)
            self.idf = np.log((1.0 + len(texts)) / (1.0 + df)) + 1.0
        x = tf * self.idf
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return x / norms

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        shifted = logits - np.max(logits, axis=1, keepdims=True)
        exp = np.exp(shifted)
        return exp / np.sum(exp, axis=1, keepdims=True)

    def fit(self, tasks: Sequence[Task]) -> "TFIDFBaseline":
        texts = [_task_source_text(t) for t in tasks]
        y_idx = np.array([self._lbl_to_idx[str(t.payload["label"])] for t in tasks], dtype=np.int64)
        x = self._featurize(texts, fit_idf=True)
        n, d = x.shape
        k = len(self.labels)
        w = np.zeros((d, k), dtype=np.float64)
        b = np.zeros(k, dtype=np.float64)
        y_onehot = np.eye(k, dtype=np.float64)[y_idx]
        for _ in range(self.epochs):
            probs = self._softmax(x @ w + b)
            grad = (probs - y_onehot) / n
            w -= self.lr * (x.T @ grad + self.reg * w)
            b -= self.lr * np.sum(grad, axis=0)
        self.weights = w
        self.bias = b
        return self

    def _best_evidence_span(self, source: str, min_len: int = 12) -> str:
        assert self.idf is not None
        candidates = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source) if len(s.strip()) >= min_len]
        if not candidates:
            return source[:max(min_len, min(80, len(source)))].strip()
        best_span = candidates[0]
        best_score = -1.0
        for cand in candidates:
            score = float(np.sum(self._tf_vector(cand) * self.idf))
            if score > best_score:
                best_score = score
                best_span = cand
        return best_span

    def predict(self, task: Task) -> Tuple[str, float, str, Dict[str, float]]:
        if self.weights is None or self.bias is None:
            raise RuntimeError("TFIDFBaseline must be fit before calling predict")
        src = _task_source_text(task)
        x = self._featurize([src], fit_idf=False)
        probs_arr = self._softmax(x @ self.weights + self.bias)[0]
        best_i = int(np.argmax(probs_arr))
        label = self.labels[best_i]
        conf = float(probs_arr[best_i])
        probs = {lbl: float(probs_arr[i]) for i, lbl in enumerate(self.labels)}
        span = self._best_evidence_span(src)
        return label, conf, span, probs

    def predict_artifact(self, task: Task) -> Artifact:
        label, conf, span, probs = self.predict(task)
        return Artifact(
            task_id=task.id,
            tool="S_tfidf_logreg",
            answer=label,
            format_ok=True,
            cost_usd=0.0,
            calls=0,
            payload={
                "label": label,
                "confidence": conf,
                "evidence_span": span,
                "rationale": "tfidf_logreg",
                "probs": probs,
            },
        )


class CuratedRealTriageAdapter:
    """``TaskAdapter`` for GitHub Issue Triage (K=8 closed labels + verbatim evidence span)."""

    def __init__(self, labels: Sequence[str] = CANONICAL_LABELS, *, min_span_len: int = 12) -> None:
        self.labels = tuple(labels)
        self.verifier = Verifier(allowed_labels=self.labels, min_span_len=min_span_len)

    def format_input(self, task: Task) -> str:
        return (
            f"Classify this GitHub issue into one of {list(self.labels)} and quote a verbatim "
            f"evidence_span (>=12 chars) from the text.\n\nTitle: {task.payload.get('title', '')}\n"
            f"Body: {task.payload.get('body', '')}"
        )

    def parse_output(self, task: Task, raw: str, *, tool: str = "maker") -> Artifact:
        src = _task_source_text(task)
        res = self.verifier.verify_deterministic(raw, source_text=src)
        try:
            obj = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            obj = {}
        return Artifact(
            task_id=task.id,
            tool=tool,
            answer=obj.get("label") if isinstance(obj, dict) else None,
            format_ok=res.strict_ok,
            error=";".join(res.reasons) if res.reasons else None,
            payload={
                **(obj if isinstance(obj, dict) else {}),
                "strict_ok": res.strict_ok,
                "lenient_ok": res.lenient_ok,
            },
        )

    def score(self, task: Task, artifact: Artifact) -> Optional[float]:
        if not artifact.format_ok:
            return 0.0
        return 1.0 if artifact.answer == task.payload.get("label") else 0.0

    def audit_shortcuts(self, tasks: Sequence[Task]) -> Dict[str, Any]:
        """Measure majority-class and title-keyword surface heuristic accuracy vs chance."""
        if not tasks:
            return {"n": 0, "chance": 0.0, "majority_rate": 0.0, "shortcut_rate": 0.0, "shortcut_flagged": False}
        labels = [str(t.payload.get("label", "other")) for t in tasks]
        majority_rate = Counter(labels).most_common(1)[0][1] / len(tasks)
        chance = 1.0 / len(self.labels)
        # Surface heuristic: single-word title cue check
        cue_hits = 0
        for t in tasks:
            title = str(t.payload.get("title") or "").lower()
            guess = "other"
            for lbl in self.labels:
                if lbl.split("_")[0] in title:
                    guess = lbl
                    break
            if guess == t.payload.get("label"):
                cue_hits += 1
        shortcut_rate = max(majority_rate, cue_hits / len(tasks))
        return {
            "n": len(tasks),
            "chance": round(chance, 4),
            "majority_rate": round(majority_rate, 4),
            "shortcut_rate": round(shortcut_rate, 4),
            "shortcut_flagged": shortcut_rate > max(0.50, chance + 0.30),
        }


class HoldoutGuard:
    """Prevents holdout double-peeking by recording evaluated holdout dataset hashes."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def check_and_record(self, tasks: Sequence[Task], *, split: str) -> str:
        digest = hashlib.sha256(
            json.dumps([t.id for t in tasks], separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if split == "holdout":
            if digest in self._seen:
                raise EvalHygieneError(f"holdout double-peek detected for split digest {digest[:12]}")
            self._seen.add(digest)
        return digest


@dataclass(frozen=True)
class EvalHygieneReport:
    passed: bool
    s_baseline_score: float
    shortcut_rate: float
    shortcut_flagged: bool
    strict_format_rate: float
    lenient_format_rate: float
    holdout_digest: str
    reasons: Tuple[str, ...] = ()


def eval_hygiene_gate(
    adapter: TaskAdapter,
    tasks: Sequence[Task],
    artifacts: Sequence[Artifact],
    *,
    s_baseline_score: Optional[float] = None,
    split: str = "dev",
    holdout_guard: Optional[HoldoutGuard] = None,
    max_shortcut_rate: float = 0.55,
) -> EvalHygieneReport:
    """Enforce Eval Hygiene Gate: S baseline, shortcut/blind audit, strict vs lenient format_ok, holdout lock."""
    guard = holdout_guard or HoldoutGuard()
    digest = guard.check_and_record(tasks, split=split)
    audit = adapter.audit_shortcuts(tasks)
    shortcut_rate = float(audit.get("shortcut_rate", 0.0))
    shortcut_flagged = bool(audit.get("shortcut_flagged", False)) or (shortcut_rate > max_shortcut_rate)

    strict_ok = sum(1 for a in artifacts if a.format_ok) / max(1, len(artifacts))
    lenient_ok = sum(1 for a in artifacts if a.payload.get("lenient_ok", a.format_ok)) / max(1, len(artifacts))

    reasons: List[str] = []
    if s_baseline_score is None:
        reasons.append("missing_s_baseline")
    if shortcut_flagged:
        reasons.append(f"shortcut_flagged:{shortcut_rate:.3f}")
    passed = not reasons
    return EvalHygieneReport(
        passed=passed,
        s_baseline_score=0.0 if s_baseline_score is None else float(s_baseline_score),
        shortcut_rate=shortcut_rate,
        shortcut_flagged=shortcut_flagged,
        strict_format_rate=round(strict_ok, 4),
        lenient_format_rate=round(lenient_ok, 4),
        holdout_digest=digest,
        reasons=tuple(reasons),
    )
