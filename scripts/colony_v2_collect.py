#!/usr/bin/env python3
"""Colony-v2 data collection: ``single``-protocol verified-claims replies, N samples per task.

One cell = one (task, sample) of one model, via the research_qa engine world with
``verified_claims_v1`` + lenient parsing + claim verification. Every physical call is
appended to ledger/colony-v2-usage.jsonl; replies are cached by request hash under
cache/colony-v2/<model>.jsonl (both gitignored). Cells go to
docs/research/colony-v2-20261010/cells/<model>-<split>.jsonl and are resumable.
``correct`` is computed here (gold label) and used by analyze only for dev-split reputation
and final scoring; the aggregator never receives it.

Evaluation refuses to run unless PREREGISTRATION.md and the collect/analyze scripts are
committed and unmodified. ``--dry-run`` uses a FakeProvider and touches no network.
"""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import dataclasses
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.providers import (  # noqa: E402
    Budgeted, Cached, ChatRequest, ChatResponse, FakeProvider, OpenAICompatProvider, Provider, ProviderError)
from antelligence.providers.base import BudgetExceeded  # noqa: E402
from antelligence.worlds.research_qa import QAPolicy  # noqa: E402
from antelligence.worlds.research_qa import build as qa_build  # noqa: E402
from scripts.colony_v2_pod import HAIKU_NOUS_ID, POD_MODELS, load_state  # noqa: E402

EXP = ROOT / "docs/research/colony-v2-20261010"
TASKS = ROOT / "backend/research_fixtures/tasks.json"
LEDGER = ROOT / "ledger/colony-v2-usage.jsonl"
CACHE_DIR = ROOT / "cache/colony-v2"
NOUS_URL = "https://inference-api.nousresearch.com/v1"
GATED_FILES = ("docs/research/colony-v2-20261010/PREREGISTRATION.md", "scripts/colony_v2_collect.py",
               "scripts/colony_v2_analyze.py")
HAIKU_MAX_CALLS = 800
RETRIES = 3
MODELS = ("qwen", "phi", "gemma", "haiku")
TEMPERATURE, MAX_TOKENS = 0.7, 512


@dataclass
class CallCtx:
    """Per-cell scratch, set in a contextvar so wrappers can tag ledger rows and collect accounting."""
    split: str
    task_id: str
    sample: int
    responses: List[ChatResponse] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    budget_hit: bool = False
    truncated: bool = False


CTX: contextvars.ContextVar[Optional[CallCtx]] = contextvars.ContextVar("colony_ctx", default=None)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()] if path.exists() else []


def stable_seed(task_id: str, model: str, sample: int) -> int:
    return int(hashlib.sha256(f"{task_id}|{model}|{sample}".encode()).hexdigest()[:8], 16)


# ----------------------------------------------------------------- preflight
def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def check_disjoint(tasks: Sequence[Dict[str, Any]]) -> None:
    """Refuse when development and evaluation share a task_id or a question text."""
    by = {s: [t for t in tasks if t["split"] == s] for s in ("development", "evaluation")}
    ids = {s: {t["task_id"] for t in v} for s, v in by.items()}
    qs = {s: {_norm(t["question"]) for t in v} for s, v in by.items()}
    if ids["development"] & ids["evaluation"] or qs["development"] & qs["evaluation"]:
        raise SystemExit("development and evaluation splits overlap (task_id or question text); refusing to run")


def check_committed(root: Path = ROOT, files: Sequence[str] = GATED_FILES) -> None:
    """Evaluation gate: the preregistration and both scripts must be tracked and unmodified."""
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)

    for f in files:
        if git("ls-files", "--error-unmatch", "--", f).returncode != 0:
            raise SystemExit(f"evaluation refused: {f} is not committed")
    dirty = git("status", "--porcelain", "--", *files).stdout.strip()
    if dirty:
        raise SystemExit(f"evaluation refused: uncommitted changes in gated files:\n{dirty}")


# ------------------------------------------------------------------ providers
class Ledgered:
    """Innermost wrapper: one ledger row per physical call, and the served-model identity check."""

    def __init__(self, inner: Provider, model: str, expected: str, *, prefix: bool, billing: str, ledger: Path) -> None:
        self.inner, self.model, self.expected, self.prefix, self.billing, self.ledger = \
            inner, model, expected, prefix, billing, ledger

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    def _row(self, request: ChatRequest, **extra: Any) -> None:
        ctx = CTX.get()
        append(self.ledger, {"utc": utc(), "model": self.model, "split": ctx and ctx.split,
                             "task_id": ctx and ctx.task_id, "sample": ctx and ctx.sample, "billing": self.billing,
                             "request_hash": request.request_hash, **extra})

    async def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            response = await self.inner.complete(request)
        except Exception as exc:
            self._row(request, ok=False, error=f"{type(exc).__name__}: {exc}"[:240])
            raise
        ok = response.model.startswith(self.expected) if self.prefix else response.model == self.expected
        self._row(request, ok=ok, prompt_tokens=response.prompt_tokens, completion_tokens=response.completion_tokens,
                  latency_s=round(response.elapsed_s, 3), served_model=response.model,
                  **({} if ok else {"error": "served model identity mismatch"}))
        if not ok:
            raise ProviderError(f"served model {response.model!r} is not the expected {self.expected!r}")
        return response


class Tap:
    """Outermost wrapper: retries (same request), truncation -> format failure, per-cell accounting."""

    def __init__(self, inner: Provider, *, backoff_s: float = 2.0) -> None:
        self.inner, self.backoff_s = inner, backoff_s

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def complete(self, request: ChatRequest) -> ChatResponse:
        ctx = CTX.get()
        for attempt in range(RETRIES + 1):
            try:
                response = await self.inner.complete(request)
            except BudgetExceeded:
                if ctx:
                    ctx.budget_hit = True
                raise
            except ProviderError as exc:
                if ctx:
                    ctx.errors.append(f"{type(exc).__name__}: {exc}"[:240])
                if attempt == RETRIES:
                    raise
                await asyncio.sleep(self.backoff_s * (attempt + 1))
                continue
            if ctx:
                ctx.responses.append(response)
            if response.finish_reason == "length":  # cut off = format failure, never a wrong answer
                if ctx:
                    ctx.truncated = True
                return dataclasses.replace(response, content="")
            return response
        raise AssertionError("unreachable")


def haiku_calls_used(ledger: Path) -> int:
    return sum(1 for r in read_jsonl(ledger) if r.get("model") == "haiku")


def nous_key() -> str:
    return json.loads(Path("~/.hermes/auth.json").expanduser().read_text())["providers"]["nous"]["agent_key"]


def build_provider(model: str, concurrency: int, ledger: Path, cache_dir: Path, *, dry_run: bool):
    """Returns (provider, request model name, deployment info)."""
    if model == "haiku":
        served, prefix, billing, deployment = HAIKU_NOUS_ID, True, "nous-credits", {}
    else:
        spec = POD_MODELS[model]
        served, prefix, billing = spec["served"], False, "runpod"
        deployment = {"hf": spec["hf"], "revision": spec["revision"]}
    if dry_run:
        raw: Provider = FakeProvider(fake_responder, model=served)
    else:
        if model == "haiku":
            base, key = NOUS_URL, nous_key()
        else:
            state = load_state()
            if not state or state["model"] != model:
                raise SystemExit(f"no running pod for {model!r}; run scripts/colony_v2_pod.py up --model {model}")
            base, key = state["base_url"], state["api_secret"]
            deployment = {"hf": state["hf"], "revision": state["revision"], "image": state["image"], "gpu": state["gpu"]}
        raw = OpenAICompatProvider(base, api_key=key, allowed_models=[served], timeout_s=300.0,
                                   max_concurrency=concurrency, require_model_match=False, require_stop=False)
    inner: Provider = Ledgered(raw, model, served, prefix=prefix, billing=billing, ledger=ledger)
    max_calls = None
    if model == "haiku":
        max_calls = max(0, HAIKU_MAX_CALLS - haiku_calls_used(ledger))
    budgeted = Budgeted(inner, max_calls=max_calls)
    cached = Cached(budgeted, cache_dir / f"{model}{'-dryrun' if dry_run else ''}.jsonl")
    return Tap(cached, backoff_s=0.0 if dry_run else 2.0), served, deployment


def fake_responder(request: ChatRequest) -> str:
    """Deterministic offline reply: a seeded answer with a verbatim quote from the first passage."""
    body = json.loads(request.messages[-1]["content"])
    task = body["task"]
    h = int(request.request_hash[:8], 16)
    first = task["evidence"][0]
    quote = " ".join(first["text"].split())[:40]
    answer = task["choices"][h % len(task["choices"])] if task["answer_type"] == "choice" else f"{h % 100}.00"
    return json.dumps({"answer": answer, "evidence_ids": [first["id"]], "brief": "dry run",
                       "quotes": [{"evidence_id": first["id"], "text": quote}]})


# ---------------------------------------------------------------------- cells
async def run_cell(task: Dict[str, Any], model: str, sample: int, provider: Provider, served: str,
                   deployment: Dict[str, Any], split: str) -> Optional[Dict[str, Any]]:
    ctx = CallCtx(split, task["task_id"], sample)
    CTX.set(ctx)
    run_id = f"colony-v2-{model}-{split}-s{sample}-" + "".join(c if c.isalnum() else "_" for c in task["task_id"])
    scheduler = qa_build(task, "single", lambda agent: QAPolicy(
        provider, served, claims="verified_claims_v1", lenient=True, temperature=TEMPERATURE, max_tokens=MAX_TOKENS),
        seed=stable_seed(task["task_id"], model, sample), run_id=run_id, lenient=True, verify=True)
    result = await scheduler.arun()
    if ctx.budget_hit:
        return None  # budget stop: not a result, so the cell stays resumable
    m, world = result.metrics, scheduler.world
    verdict = world.verdicts["worker-1"].get(0)
    last = ctx.responses[-1] if ctx.responses else None
    return {"task_id": task["task_id"], "domain": task["domain"], "split": split, "model": model, "sample": sample,
            "answer": m["answer"], "status": m["status"],
            "verification": None if verdict is None else {"status": verdict.status, "reason": verdict.reason},
            "format_failure": m["status"] == "invalid", "truncated": ctx.truncated,
            "correct": m["correct"] is True,  # evaluator-owned; the aggregator never sees it
            "usage": {"calls": len(ctx.responses), "prompt_tokens": sum(r.prompt_tokens for r in ctx.responses),
                      "completion_tokens": sum(r.completion_tokens for r in ctx.responses),
                      "latency_s": round(sum(r.elapsed_s for r in ctx.responses), 3)},
            "served_model": last.model if last else None, "errors": ctx.errors[:3], "deployment": deployment,
            "trace_hash": result.trace_hash, "config_hash": result.config_hash}


async def collect(args: argparse.Namespace) -> Dict[str, Any]:
    tasks_doc = json.loads(TASKS.read_text())
    tasks = tasks_doc["tasks"]
    check_disjoint(tasks)
    if args.split == "evaluation" and not args.dry_run:
        check_committed()
    out = Path(args.out_dir) if args.out_dir else (EXP / "cells" if not args.dry_run else CACHE_DIR / "dryrun-cells")
    ledger = Path(args.ledger) if args.ledger else (LEDGER if not args.dry_run else CACHE_DIR / "dryrun-ledger.jsonl")
    cache_dir = Path(args.cache_dir) if args.cache_dir else CACHE_DIR
    cells_path = out / f"{args.model}-{args.split}.jsonl"
    samples = args.samples + (1 if args.extra_sample_for_best and args.split == "evaluation" else 0)
    concurrency = args.concurrency or (8 if args.model == "haiku" else 16)
    provider, served, deployment = build_provider(args.model, concurrency, ledger, cache_dir, dry_run=args.dry_run)
    todo_tasks = [t for t in tasks if t["split"] == args.split]
    if args.limit:
        todo_tasks = todo_tasks[: args.limit]
    done = {(r["task_id"], r["sample"]) for r in read_jsonl(cells_path)}
    jobs = [(t, s) for t in todo_tasks for s in range(1, samples + 1) if (t["task_id"], s) not in done]
    append(out / "run-log.jsonl", {"utc": utc(), "event": "start", "model": args.model, "split": args.split,
                                   "tasks_sha256": hashlib.sha256(TASKS.read_bytes()).hexdigest(),
                                   "planned": len(jobs), "already_done": len(done), "dry_run": args.dry_run,
                                   "argv": sys.argv[1:]})
    gate = asyncio.Semaphore(concurrency)
    counts = {"written": 0, "budget_stop": 0, "errors": 0}

    async def one(task: Dict[str, Any], sample: int) -> None:
        async with gate:
            cell = await run_cell(task, args.model, sample, provider, served, deployment, args.split)
        if cell is None:
            counts["budget_stop"] += 1
            return
        append(cells_path, cell)
        counts["written"] += 1
        counts["errors"] += cell["status"] == "error"

    await asyncio.gather(*(one(t, s) for t, s in jobs))
    append(out / "run-log.jsonl", {"utc": utc(), "event": "end", "model": args.model, "split": args.split, **counts})
    return {"model": args.model, "split": args.split, "cells_path": str(cells_path), **counts}


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, choices=MODELS)
    p.add_argument("--split", required=True, choices=("development", "evaluation"))
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--extra-sample-for-best", action="store_true",
                   help="evaluation only: a 4th sample, for the model chosen as a colony's best member")
    p.add_argument("--dry-run", action="store_true", help="FakeProvider, no network, outputs under cache/")
    p.add_argument("--concurrency", type=int, default=0)
    p.add_argument("--limit", type=int, default=0, help="first N tasks of the split (smoke runs)")
    p.add_argument("--out-dir"), p.add_argument("--ledger"), p.add_argument("--cache-dir")
    summary = asyncio.run(collect(p.parse_args(argv)))
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main()
