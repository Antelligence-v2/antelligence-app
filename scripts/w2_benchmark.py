#!/usr/bin/env python3
"""W2 benchmark harness: small local models vs frontier models on the Antelligence engine.

Runs the *engine* worlds (``antelligence.worlds.research_qa``, ``task_dag`` (E15),
``foraging`` (E13)) with existing protocols/arms only, and writes append-only
evidence:

* ``cells/<model>.jsonl``  one line per (world, arm, seed, task) cell, incl. failures
* ``bundles/<model>.jsonl`` engine provenance bundle per cell (hash-chained trace hash)
* ``raw/<model>-<world>.jsonl`` every model response (request-hash keyed; enables offline replay)
* ``ledger/goal-2026-10-08-usage.jsonl`` one line per physical model call

Design is fixed by ``docs/research/slm-vs-frontier-20261008/PREREGISTRATION.md``.
Credentials are read at runtime (Nous agent key from ~/.hermes/auth.json) and never
written anywhere. Local endpoints are loopback llama.cpp servers pinned in
``backend/research_models.py``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.kernel.policies import LLMPolicy  # noqa: E402
from antelligence.kernel.verifier import classify_episode  # noqa: E402
from antelligence.provenance.bundle import build_bundle  # noqa: E402
from antelligence.providers import Cached, ChatRequest, ChatResponse, ProviderError  # noqa: E402
from antelligence.worlds.research_qa import PROTOCOLS, QAPolicy  # noqa: E402
from antelligence.worlds.research_qa import build as qa_build  # noqa: E402
from backend.research_models import MODELS as LOCAL_MODELS, OPTIONS as LOCAL_OPTIONS  # noqa: E402

OUT = ROOT / "docs/research/slm-vs-frontier-20261008"
LEDGER = ROOT / "ledger/goal-2026-10-08-usage.jsonl"
NOUS_URL = "https://inference-api.nousresearch.com/v1"

# model key -> how to reach it. Tier and billing are recorded on every call.
ROSTER: Dict[str, Dict[str, Any]] = {
    "qwen38-27b-q3k": {"tier": "small", "billing": "local", "base_url": "http://127.0.0.1:8301/v1",
                       "model": LOCAL_MODELS["qwen"]["model_id"], "concurrency": 3},
    "phi4-mini-finance-f16": {"tier": "small", "billing": "local", "base_url": "http://127.0.0.1:18302/v1",
                              "model": LOCAL_MODELS["phi4"]["model_id"], "concurrency": 3},
    "claude-haiku-5.5": {"tier": "frontier", "billing": "nous-credits", "base_url": NOUS_URL,
                         "model": "anthropic/claude-haiku-5.5", "concurrency": 8},
    "claude-sonnet-5.5": {"tier": "frontier", "billing": "nous-credits", "base_url": NOUS_URL,
                          "model": "anthropic/claude-sonnet-5.5", "concurrency": 8},
}
QA_ARMS = ("single", "independent_vote", "signal_board", "evidence_exchange", "evidence_isolated", "solo_refine")
QA_TEMPERATURE = 0.7
QA_MAX_TOKENS = 512
RUN = {"split": None, "smoke": None, "variant": "prereg"}  # set once in main_async; stamped on every ledger row


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def safe(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)


class FrontierSpend:
    """Process-wide frontier spend tracker enforcing the preregistered hard cap."""

    def __init__(self, cap_usd: float, prior_usd: float) -> None:
        self.cap_usd = cap_usd
        self.spent = prior_usd

    def check(self) -> None:
        if self.spent >= self.cap_usd:
            raise ProviderError(f"preregistered frontier cap ${self.cap_usd:.2f} reached (spent ${self.spent:.4f})")


class HTTPProvider:
    """OpenAI-compatible provider that keeps provider-reported cost (``usage.cost``).

    Same strictness as ``antelligence.providers.OpenAICompatProvider`` (served model
    must equal requested, finish_reason must be ``stop``, integer usage required),
    plus cost capture, which the engine provider drops.
    """

    def __init__(self, key: str, spend: Optional[FrontierSpend]) -> None:
        spec = ROSTER[key]
        self.key = key
        self.spec = spec
        self.base_url = spec["base_url"]
        self.semaphore = asyncio.Semaphore(spec["concurrency"])
        self.spend = spend
        self.extra_body: Dict[str, Any] = {}
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if spec["billing"] == "local":
            self.extra_body = {k: v for k, v in LOCAL_OPTIONS.items() if k != "stream"}
        else:
            auth = json.loads(Path("~/.hermes/auth.json").expanduser().read_text())
            self.headers["Authorization"] = "Bearer " + auth["providers"]["nous"]["agent_key"]
        self.client = httpx.AsyncClient(timeout=300.0, follow_redirects=False, trust_env=False)

    def describe(self) -> Dict[str, Any]:
        return {"provider": "local-llama.cpp" if self.spec["billing"] == "local" else "nous",
                "base_url": self.base_url, "model": self.spec["model"]}

    async def complete(self, request: ChatRequest) -> ChatResponse:
        if request.model != self.spec["model"]:
            raise ProviderError(f"model {request.model!r} not allowlisted for {self.key}")
        if self.spend is not None:
            self.spend.check()
        body = {**self.extra_body, **request.payload()}
        async with self.semaphore:
            start = time.monotonic()
            try:
                response = await self.client.post(f"{self.base_url}/chat/completions", json=body, headers=self.headers)
            except httpx.HTTPError as exc:
                raise ProviderError(f"transport error: {type(exc).__name__}: {exc}") from exc
            elapsed = time.monotonic() - start
        if response.status_code != 200:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:200]}")
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage = data["usage"]
            prompt_tokens, completion_tokens = usage["prompt_tokens"], usage["completion_tokens"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"malformed response: {exc}") from exc
        served = data.get("model") or ""
        if served != request.model:
            raise ProviderError(f"served model {served!r} differs from requested {request.model!r}")
        finish = choice.get("finish_reason") or "unknown"
        if finish != "stop":
            raise ProviderError(f"generation did not finish normally ({finish})")
        if not isinstance(content, str):
            raise ProviderError("missing message content")
        cost = float(usage.get("cost") or 0.0) if self.spec["billing"] != "local" else 0.0
        if self.spend is not None:
            self.spend.spent += cost
        return ChatResponse(content=content, model=served, request_hash=request.request_hash,
                            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, finish_reason=finish,
                            response_id=data.get("id"), elapsed_s=elapsed,
                            extra={"cost_usd": cost, "system_fingerprint": data.get("system_fingerprint")})


class Meter:
    """Per-cell accounting wrapper; writes one ledger line per physical call."""

    def __init__(self, inner: Any, key: str, world: str) -> None:
        self.inner = inner
        self.key = key
        self.world = world
        self.calls = self.cached_calls = self.failed_calls = 0
        self.prompt_tokens = self.completion_tokens = 0
        self.cost_usd = 0.0
        self.latency_s = 0.0
        self.errors: List[str] = []

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def complete(self, request: ChatRequest) -> ChatResponse:
        spec = ROSTER[self.key]
        try:
            response = await self.inner.complete(request)
        except Exception as exc:
            self.failed_calls += 1
            self.errors.append(f"{type(exc).__name__}: {exc}"[:240])
            append(LEDGER, {"timestamp_utc": utc(), "workstream": "W2", "world": self.world, "tier": spec["tier"],
                            "split": RUN["split"], "smoke": RUN["smoke"], "variant": RUN["variant"],
                            "billing": spec["billing"], "model_key": self.key, "model_requested": request.model,
                            "model_served": None, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:240],
                            "request_hash": request.request_hash})
            raise
        # Logical accounting: a cached response still counts toward this cell's
        # tokens/cost/latency (it is what the arm would cost run alone). Only
        # physical calls go to the ledger and to `physical_calls`.
        cost = float((response.extra or {}).get("cost_usd") or 0.0)
        self.calls += 1
        self.prompt_tokens += response.prompt_tokens
        self.completion_tokens += response.completion_tokens
        self.cost_usd += cost
        self.latency_s += response.elapsed_s
        if response.cached:
            self.cached_calls += 1
            return response
        append(LEDGER, {"timestamp_utc": utc(), "workstream": "W2", "world": self.world, "tier": spec["tier"],
                        "split": RUN["split"], "smoke": RUN["smoke"], "variant": RUN["variant"],
                        "billing": spec["billing"], "model_key": self.key, "model_requested": request.model,
                        "model_served": response.model, "ok": True, "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens, "latency_s": round(response.elapsed_s, 3),
                        "cost_usd": cost, "request_hash": request.request_hash, "response_id": response.response_id})
        return response

    def usage(self) -> Dict[str, Any]:
        return {"calls": self.calls, "cached_calls": self.cached_calls,
                "physical_calls": self.calls - self.cached_calls, "failed_calls": self.failed_calls,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cost_usd": round(self.cost_usd, 8), "latency_s": round(self.latency_s, 3)}


def done_keys(cells_path: Path) -> set:
    keys = set()
    if cells_path.exists():
        for line in cells_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                keys.add((row["world"], row["arm"], row["seed"], row["task_id"]))
    return keys


async def run_cell(key: str, world: str, arm: str, seed: int, task: Dict[str, Any], cache: Cached,
                   cells_path: Path, bundles_path: Path, max_tokens: int = QA_MAX_TOKENS) -> Dict[str, Any]:
    spec = ROSTER[key]
    meter = Meter(cache, key, world)
    model = spec["model"]
    started = time.monotonic()
    if world == "research_qa":
        task_id = task["task_id"]
        run_id = f"w2-{safe(key)}-{arm}-s{seed}-{safe(task_id)}"
        scheduler = qa_build(task, arm, lambda agent: QAPolicy(meter, model, temperature=QA_TEMPERATURE,
                                                                max_tokens=max_tokens), seed=seed, run_id=run_id)
        domain = task["domain"]
    elif world == "task_dag":
        from antelligence.worlds.task_dag import LLMPlanner, build as dag_build
        task_id = f"e15-fixture-{task['fixture']}"
        run_id = f"w2-{safe(key)}-{arm}-{task['fixture']}"
        scheduler = dag_build(arm, task["fixture"], run_id=run_id,
                              policy_factory=lambda a: LLMPlanner(meter, model))
        domain = "task_dag"
    elif world == "foraging":
        from antelligence.worlds.foraging import LLM_ACTIONS, LLM_SIGNAL_KINDS, build as forage_build
        task_id = f"e13-seed-{task['fixture']}"
        run_id = f"w2-{safe(key)}-{arm}-{task['fixture']}"
        scheduler = forage_build(arm, task["fixture"], run_id=run_id, max_steps=task["max_steps"],
                                 policy_factory=lambda a: LLMPolicy(meter, model, actions=LLM_ACTIONS,
                                                                    signal_kinds=LLM_SIGNAL_KINDS))
        domain = "foraging"
    else:
        raise ValueError(world)
    result = await scheduler.arun()
    wall = time.monotonic() - started
    m = result.metrics
    if world == "research_qa":
        # World-owned status: completed | abstained | invalid | error (error = a required
        # call produced no answer: transport failure, truncation, refusal by the provider).
        status, correct = m["status"], m["correct"] is True
    else:
        # Verifier/world-owned success. Failed calls do not erase a success the world
        # verified, but they are counted and the cell is flagged.
        correct = bool(m.get("success"))
        status = "completed_with_failures" if (meter.failed_calls or result.policy_failures) else "completed"
    verdict = classify_episode(scheduler.log, goal_reached=correct).to_dict()
    spec_dict = {"world": world, "arm": arm, "case": seed, "params": {"task_id": task_id, "model_key": key,
                                                                      "model": model}}
    bundle = build_bundle(result, spec_dict, world_description=scheduler.world.describe(),
                          extra={"verdict": verdict, "usage": meter.usage(), "tier": spec["tier"]})
    cell = {"timestamp_utc": utc(), "model_key": key, "model": model, "tier": spec["tier"],
            "billing": spec["billing"], "world": world, "domain": domain, "arm": arm, "seed": seed,
            "task_id": task_id, "status": status, "correct": correct, "answer": m.get("answer"),
            "final_answers": m.get("final_answers"), "metrics": m if world != "research_qa" else None,
            "policy_failures": result.policy_failures, "errors": meter.errors[:5], **meter.usage(),
            "wall_s": round(wall, 3), "trace_hash": result.trace_hash, "config_hash": result.config_hash,
            "bundle_hash": bundle["bundle_hash"], "run_id": run_id}
    append(cells_path, cell)
    append(bundles_path, bundle)
    return cell


def plan(args: argparse.Namespace) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    if args.world == "research_qa":
        fixture = json.loads((ROOT / "backend/research_fixtures/tasks.json").read_text())
        split = "development" if args.smoke else "evaluation"
        tasks = []
        for domain in ("medical", "finance"):
            tasks += [t for t in fixture["tasks"] if t["split"] == split and t["domain"] == domain][: args.per_domain]
        # seed -> task -> arm: an interrupted run leaves complete paired task rows.
        for seed in args.seeds:
            for task in tasks:
                for arm in args.arms:
                    jobs.append({"arm": arm, "seed": seed, "task": task})
    else:
        from antelligence.worlds.foraging import ARMS as FORAGE_ARMS
        from antelligence.worlds.task_dag import ARMS as DAG_ARMS, SEEDS as DAG_SEEDS
        arms = args.arms or (DAG_ARMS if args.world == "task_dag" else FORAGE_ARMS)
        fixtures = args.fixtures or list(DAG_SEEDS)
        for arm in arms:
            for fixture in fixtures:
                jobs.append({"arm": arm, "seed": fixture,
                             "task": {"fixture": fixture, "max_steps": args.max_steps}})
    return jobs


def resolve_out(out_dir: Optional[str]) -> Path:
    """Output dir for cells/bundles/raw/run-log; default is the preregistered OUT."""
    if not out_dir:
        return OUT
    path = Path(out_dir)
    return path if path.is_absolute() else ROOT / path


def variant_name(max_tokens: int) -> str:
    """Ledger variant tag: preregistered run vs a max_tokens sensitivity run."""
    return "prereg" if max_tokens == QA_MAX_TOKENS else f"sens-maxtok{max_tokens}"


def prior_frontier_spend() -> float:
    total = 0.0
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("workstream") == "W2" and row.get("billing") == "nous-credits":
                    total += float(row.get("cost_usd") or 0.0)
    return total


async def main_async(args: argparse.Namespace) -> None:
    key = args.model
    spec = ROSTER[key]
    tag = "smoke-" if args.smoke else ""
    if args.world == "research_qa":
        RUN["split"] = "development" if args.smoke else "evaluation"
    else:
        RUN["split"] = f"fixtures:{','.join(map(str, args.fixtures or []))or 'default'}"
    RUN["smoke"] = bool(args.smoke)
    out = resolve_out(args.out_dir)
    RUN["variant"] = variant_name(args.max_tokens)
    cells_path = out / "cells" / f"{tag}{key}.jsonl"
    bundles_path = out / "bundles" / f"{tag}{key}.jsonl"
    raw_path = out / "raw" / f"{tag}{key}-{args.world}.jsonl"
    spend = FrontierSpend(args.frontier_cap_usd, prior_frontier_spend()) if spec["billing"] != "local" else None
    provider = HTTPProvider(key, spend)
    cache = Cached(provider, raw_path)
    jobs = plan(args)
    finished = done_keys(cells_path)
    todo = [j for j in jobs if (args.world, j["arm"], j["seed"],
                                j["task"].get("task_id") or (f"e15-fixture-{j['task']['fixture']}" if args.world == "task_dag"
                                                             else f"e13-seed-{j['task']['fixture']}")) not in finished]
    run_log = out / "run-log.jsonl"
    append(run_log, {"timestamp_utc": utc(), "event": "start", "model_key": key, "world": args.world,
                     "smoke": args.smoke, "max_tokens": args.max_tokens, "planned": len(jobs), "already_done": len(jobs) - len(todo),
                     "resumed": len(jobs) != len(todo), "argv": sys.argv[1:],
                     "frontier_spent_before": None if spend is None else round(spend.spent, 6)})
    semaphore = asyncio.Semaphore(args.cell_concurrency)
    counter = {"done": 0, "fail": 0}

    async def worker(job: Dict[str, Any]) -> None:
        async with semaphore:
            if spend is not None and spend.spent >= spend.cap_usd:
                # Preregistered stop rule: do not start new cells once the frontier cap is hit.
                counter["skipped_cap"] = counter.get("skipped_cap", 0) + 1
                return
            try:
                cell = await run_cell(key, args.world, job["arm"], job["seed"], job["task"], cache,
                                      cells_path, bundles_path, args.max_tokens)
                counter["done"] += 1
                counter["fail"] += cell["status"] in ("error", "completed_with_failures")
            except Exception as exc:  # harness fault: record, never drop silently
                counter["fail"] += 1
                append(run_log, {"timestamp_utc": utc(), "event": "harness_error", "model_key": key,
                                 "arm": job["arm"], "seed": job["seed"], "error": f"{type(exc).__name__}: {exc}"[:400]})
            if counter["done"] % 20 == 0:
                print(f"{utc()} {key} {args.world}: {counter['done']}/{len(todo)} done, {counter['fail']} failures,"
                      f" spend={None if spend is None else round(spend.spent, 4)}", flush=True)

    await asyncio.gather(*(worker(j) for j in todo))
    await provider.client.aclose()
    append(run_log, {"timestamp_utc": utc(), "event": "end", "model_key": key, "world": args.world,
                     "smoke": args.smoke, "completed_cells": counter["done"], "failure_cells": counter["fail"], "skipped_after_cap": counter.get("skipped_cap", 0),
                     "frontier_spent_after": None if spend is None else round(spend.spent, 6)})
    print(json.dumps({"model": key, "world": args.world, "cells": counter["done"], "failures": counter["fail"],
                      "frontier_spent": None if spend is None else round(spend.spent, 6)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=sorted(ROSTER))
    parser.add_argument("--world", required=True, choices=("research_qa", "task_dag", "foraging"))
    parser.add_argument("--arms", nargs="*", default=None)
    parser.add_argument("--seeds", nargs="*", type=int, default=[0])
    parser.add_argument("--fixtures", nargs="*", type=int, default=None)
    parser.add_argument("--per-domain", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--cell-concurrency", type=int, default=3)
    parser.add_argument("--frontier-cap-usd", type=float, default=12.0)
    parser.add_argument("--max-tokens", type=int, default=QA_MAX_TOKENS,
                        help="research_qa completion cap (default: preregistered 512)")
    parser.add_argument("--out-dir", default=None,
                        help="output dir for cells/bundles/raw/run-log (default: preregistered OUT); ledger stays shared")
    parser.add_argument("--smoke", action="store_true", help="development split only")
    args = parser.parse_args()
    if args.world == "research_qa":
        args.arms = args.arms or list(QA_ARMS)
        unknown = [a for a in args.arms if a not in PROTOCOLS]
        if unknown:
            raise SystemExit(f"unknown research_qa arms: {unknown}")
    os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
