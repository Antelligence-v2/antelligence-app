"""Deterministic verifiers, AST-restricted Python sandbox, and cross-family Checker.

Enforces Harness vNext Invariant #1:
  Cheap Maker -> Free Deterministic Verifier -> Independent Cross-Family Checker (never self-check) -> Escalation.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Tuple

from antelligence.harness.core import Artifact, Task

ALLOWED_MODULES = frozenset({
    "itertools", "math", "fractions", "collections", "functools",
    "re", "string", "json", "decimal", "operator", "statistics",
})
BANNED_NAMES = frozenset({
    "open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "breakpoint", "exit", "quit", "help", "memoryview",
    "classmethod", "staticmethod", "super", "type", "object",
})
MAX_CODE_CHARS = 12_000
MAX_OUTPUT_CHARS = 4_000

DEFAULT_BOILERPLATE_PREFIXES = (
    "### describe the bug",
    "### to reproduce",
    "### expected behavior",
    "### environment",
    "### additional context",
    "**describe the bug**",
    "**is your feature request related",
)


class Refused(ValueError):
    """The program uses something the AST sandbox does not allow."""


class SelfCheckError(ValueError):
    """Raised when a Checker shares the Maker's model family (self-check is banned)."""


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    stdout: str
    error: str
    seconds: float


Result = SandboxResult


def check_code(code: str) -> None:
    """Raise :class:`Refused` when ``code`` uses disallowed imports, names, or dunder attributes."""
    if len(code) > MAX_CODE_CHARS:
        raise Refused(f"the program is longer than {MAX_CODE_CHARS} characters")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise Refused(f"syntax error on line {exc.lineno}: {exc.msg}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_MODULES:
                    raise Refused(f"import of {alias.name!r} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_MODULES:
                raise Refused(f"import from {node.module!r} is not allowed")
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES or (node.id.startswith("_") and node.id not in ("_", "__name__")):
                raise Refused(f"the name {node.id!r} is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise Refused(f"the attribute {node.attr!r} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise Refused("global and nonlocal are not allowed")


check = check_code

_RUNNER = """\
import sys
try:
    import resource
    cpu, mem = int(sys.argv[2]), int(sys.argv[3])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (mem << 20, mem << 20))
except (ImportError, ValueError, OSError):
    pass
with open(sys.argv[1]) as fh:
    source = fh.read()
exec(compile(source, "prog.py", "exec"), {"__name__": "__main__"})
"""


def run_sandbox(code: str, *, timeout_s: float = 20.0, mem_mb: int = 1024,
                python: Optional[str] = None) -> SandboxResult:
    """AST-check and execute ``code`` in an isolated ``python -I -S`` subprocess."""
    try:
        check_code(code)
    except Refused as exc:
        return SandboxResult(False, "", f"refused: {exc}", 0.0)
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="harness-sbx-") as tmpdir:
        path = os.path.join(tmpdir, "prog.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        try:
            proc = subprocess.run(
                [python or sys.executable, "-I", "-S", "-c", _RUNNER, path, str(int(timeout_s) + 1), str(mem_mb)],
                cwd=tmpdir, env={}, capture_output=True, text=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(False, "", f"it ran longer than {timeout_s:.0f} seconds", time.monotonic() - start)
    secs = time.monotonic() - start
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        return SandboxResult(False, proc.stdout[:MAX_OUTPUT_CHARS], "it crashed: " + " | ".join(tail)[:500], secs)
    return SandboxResult(True, proc.stdout[:MAX_OUTPUT_CHARS], "", secs)


run = run_sandbox


def model_family(model_name: str) -> str:
    """Infer model family for cross-family Checker enforcement."""
    low = model_name.strip().lower()
    if "/" in low:
        prefix = low.split("/", 1)[0]
        if prefix in ("anthropic", "openai", "google", "meta", "qwen", "mistral", "deepseek"):
            return prefix
        low = low.split("/", 1)[1]
    for fam, prefixes in (
        ("anthropic", ("claude",)),
        ("openai", ("gpt-", "o1", "o3", "o4")),
        ("google", ("gemini", "gemma")),
        ("qwen", ("qwen",)),
        ("meta", ("llama",)),
        ("mistral", ("mistral", "mixtral")),
        ("deepseek", ("deepseek",)),
    ):
        if any(low.startswith(p) for p in prefixes):
            return fam
    return low.split("-", 1)[0] if "-" in low else low


def check_json_schema(
    raw_or_obj: Any,
    required_keys: Sequence[str] = ("label", "confidence", "evidence_span", "rationale"),
    field_types: Optional[Mapping[str, type]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate JSON object structure and required keys."""
    if isinstance(raw_or_obj, str):
        text = raw_or_obj.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            return False, None, f"invalid_json: {exc.msg}"
    elif isinstance(raw_or_obj, Mapping):
        obj = dict(raw_or_obj)
    else:
        return False, None, f"expected JSON string or mapping, got {type(raw_or_obj).__name__}"

    if not isinstance(obj, dict):
        return False, None, "json_root_not_object"
    missing = [k for k in required_keys if k not in obj]
    if missing:
        return False, obj, f"missing_keys: {missing}"
    if field_types:
        for k, expected in field_types.items():
            if k in obj and not isinstance(obj[k], expected):
                return False, obj, f"bad_type:{k}:{type(obj[k]).__name__}"
    return True, obj, ""


def check_closed_label(label: Any, allowed_labels: Collection[str]) -> Tuple[bool, str]:
    """Verify ``label`` belongs to the closed label set."""
    if not isinstance(label, str) or label not in allowed_labels:
        return False, f"invalid_label:{label!r}"
    return True, ""


def _strip_boilerplate(text: str, prefixes: Sequence[str] = DEFAULT_BOILERPLATE_PREFIXES) -> str:
    lines = [ln for ln in text.splitlines() if not any(ln.strip().lower().startswith(p) for p in prefixes)]
    return "\n".join(lines)


def _norm_ws(text: str) -> str:
    return " ".join(text.split()).lower()


def check_span_containment(
    span: Any,
    source_text: str,
    *,
    strict: bool = True,
    min_len: int = 12,
    boilerplate_prefixes: Sequence[str] = DEFAULT_BOILERPLATE_PREFIXES,
) -> Tuple[bool, str]:
    """Check whether ``span`` is a verbatim (strict) or whitespace-normalized (lenient) substring."""
    if not isinstance(span, str) or not span.strip():
        return False, "empty_span"
    if len(span.strip()) < min_len:
        return False, f"span_too_short:{len(span.strip())}<{min_len}"
    if any(span.strip().lower().startswith(p) for p in boilerplate_prefixes):
        return False, "span_is_boilerplate"
    cleaned_source = _strip_boilerplate(source_text, boilerplate_prefixes)
    if strict:
        if span in cleaned_source:
            return True, ""
        return False, "phantom_span_strict"
    if _norm_ws(span) in _norm_ws(cleaned_source):
        return True, ""
    return False, "phantom_span_lenient"


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    format_ok: bool
    strict_ok: bool
    lenient_ok: bool
    reasons: Tuple[str, ...] = ()
    escalate: bool = False
    checker_artifact: Optional[Artifact] = None


class Verifier:
    """Deterministic-first verifier paired with an independent cross-family Checker."""

    def __init__(
        self,
        *,
        allowed_labels: Optional[Collection[str]] = None,
        required_keys: Sequence[str] = ("label", "confidence", "evidence_span", "rationale"),
        min_span_len: int = 12,
    ) -> None:
        self.allowed_labels = frozenset(allowed_labels) if allowed_labels is not None else None
        self.required_keys = tuple(required_keys)
        self.min_span_len = min_span_len

    def verify_deterministic(
        self,
        raw_or_obj: Any,
        *,
        source_text: Optional[str] = None,
        code: Optional[str] = None,
    ) -> VerificationResult:
        reasons: List[str] = []
        ok_json, obj, err_json = check_json_schema(raw_or_obj, self.required_keys)
        if not ok_json or obj is None:
            return VerificationResult(False, False, False, False, (err_json,), escalate=True)

        if self.allowed_labels is not None:
            ok_lbl, err_lbl = check_closed_label(obj.get("label"), self.allowed_labels)
            if not ok_lbl:
                reasons.append(err_lbl)

        strict_ok = True
        lenient_ok = True
        if source_text is not None:
            strict_ok, err_s = check_span_containment(
                obj.get("evidence_span"), source_text, strict=True, min_len=self.min_span_len
            )
            lenient_ok, err_l = check_span_containment(
                obj.get("evidence_span"), source_text, strict=False, min_len=self.min_span_len
            )
            if not strict_ok:
                reasons.append(err_s)

        if code is not None:
            sbx = run_sandbox(code)
            if not sbx.ok:
                reasons.append(f"sandbox:{sbx.error}")

        passed = not reasons
        return VerificationResult(
            ok=passed,
            format_ok=True,
            strict_ok=passed and strict_ok,
            lenient_ok=(not [r for r in reasons if not r.startswith("phantom_span_")]) and lenient_ok,
            reasons=tuple(reasons),
            escalate=not passed,
        )

    async def verify_with_checker(
        self,
        task: Task,
        maker_artifact: Artifact,
        *,
        maker_model: str,
        checker_model: str,
        checker_fn: Optional[Callable[[Task, Artifact], Awaitable[Artifact]]] = None,
        maker_family: Optional[str] = None,
        checker_family: Optional[str] = None,
        source_text: Optional[str] = None,
    ) -> VerificationResult:
        """Run free deterministic checks first; invoke cross-family Checker only if deterministic checks pass."""
        m_fam = (maker_family or model_family(maker_model)).lower()
        c_fam = (checker_family or model_family(checker_model)).lower()
        if m_fam == c_fam:
            raise SelfCheckError(
                f"self-check banned: maker ({maker_model}, family={m_fam}) and "
                f"checker ({checker_model}, family={c_fam}) share model family"
            )

        det = self.verify_deterministic(
            maker_artifact.payload if maker_artifact.payload else maker_artifact.answer,
            source_text=source_text,
        )
        if not det.ok or checker_fn is None:
            return det

        checker_art = await checker_fn(task, maker_artifact)
        agreed = checker_art.format_ok and (checker_art.answer == maker_artifact.answer)
        reasons = () if agreed else ("checker_disagreed",)
        return VerificationResult(
            ok=agreed,
            format_ok=det.format_ok,
            strict_ok=det.strict_ok and agreed,
            lenient_ok=det.lenient_ok and agreed,
            reasons=reasons,
            escalate=not agreed,
            checker_artifact=checker_art,
        )
