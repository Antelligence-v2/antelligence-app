#!/usr/bin/env python3
"""Replay recorded v4 pilot cells OFFLINE from the reply caches into run bundles (event log + replay frames).

No model call, no network, no key: every leaf (chat provider, decision backend) is a guard whose call can only
raise (a cache miss is counted and fails the cell; a call that failed live re-raises its recorded error). Real
HTTP classes are constructed with a placeholder secret only so that their ``describe()`` (and so the config
hash) equals the live run's; the placeholder is never sent anywhere. Each replay must reproduce the recorded
trace and config hashes.

    uv run python scripts/v4_replay_bundles.py [--cells KEY ...] [--out DIR]

Never touches cells.jsonl or any recorded result. Writes <out>/<world>/<arm>-s<seed>-<condition>/ and <out>/REPLAY.json.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import gzip
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.experiments import v4_pilot as pilot  # noqa: E402
from antelligence.kernel.decision import DecisionError  # noqa: E402
from antelligence.experiments import v4_wiring as wiring  # noqa: E402
from antelligence.providers.base import ProviderError  # noqa: E402
from antelligence.providers.decision_backends import JevBackend, LayaBackend, SLMBackend  # noqa: E402
from antelligence.providers.ledger import LedgerWriter  # noqa: E402
from antelligence.providers.openai_compat import OpenAICompatProvider  # noqa: E402

EXP_REL = "docs/research/v4-pilot-20261011"
DEFAULT_WORLDS = {"foraging_sb": "antelligence.worlds.foraging_sb:FORAGING_SB",
                  "graph_coloring": "antelligence.worlds.graph_coloring:GRAPH_COLORING"}
PLACEHOLDER = "offline-placeholder-never-sent"
# Pods that served the evaluation (ids from the local pod-cost ledger; the base URL is part of the config hash).
POD_IDS = ("2042id4xv8l9p5", "2u9o788caf9kuz", "uujxl4g9sofnqq", "4o8dp95zilkklm")
SERVED_SUFFIXES = ("", "-FP8")


class OfflineError(RuntimeError):
    """A leaf was called for a request that is neither cached nor a recorded failure: a cache miss."""


class Recorded:
    """What the replay re-creates besides cached replies. A live call that FAILED left no cache row (only a ledger
    error row), and its error text reached the trace (``provider:<Class>:<message>``); a request that failed and was
    later retried successfully is in the cache but must still fail first. So the failures recorded for this
    execution, in order, are raised ABOVE the cache; any request that then reaches a leaf is a true cache miss."""

    def __init__(self, errors: Optional[Mapping[str, Sequence[str]]] = None) -> None:
        self.errors = {h: list(v) for h, v in (errors or {}).items()}  # request_hash -> ["Class: message", ...]
        self.replayed_errors = 0
        self.misses: List[str] = []

    def failure(self, request_hash: str) -> Optional[Exception]:
        pending = self.errors.get(request_hash)
        if not pending:
            return None
        self.replayed_errors += 1
        name, _, message = pending.pop(0).partition(": ")
        return (DecisionError if name == "DecisionError" else ProviderError)(message)

    async def watch(self, request_hash: str, call: Any) -> Any:
        """Await a cached call; an offline cache miss (raised by the cache itself) is counted, then re-raised."""
        try:
            return await call
        except (ProviderError, DecisionError) as exc:
            if "cache miss in offline mode" in str(exc):
                self.misses.append(request_hash)
            raise

    def miss(self, request_hash: str, kind: str) -> Exception:
        self.misses.append(request_hash)
        return OfflineError(f"{kind} reply not in cache ({request_hash[:12]})")


class _NoCallProvider:
    def __init__(self, inner: Any, recorded: Recorded) -> None:
        self.inner, self.recorded = inner, recorded

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def complete(self, request: Any) -> Any:
        raise self.recorded.miss(request.request_hash, "chat")


class _NoCallBackend:
    def __init__(self, inner: Any, recorded: Recorded) -> None:
        self.inner, self.recorded = inner, recorded

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def decide(self, request: Any) -> Any:
        raise self.recorded.miss(request.request_hash, "decision")


class _FailFirstProvider:
    def __init__(self, inner: Any, recorded: Recorded) -> None:
        self.inner, self.recorded = inner, recorded

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def complete(self, request: Any) -> Any:
        failure = self.recorded.failure(request.request_hash)
        if failure:
            raise failure
        return await self.recorded.watch(request.request_hash, self.inner.complete(request))


class _FailFirstBackend:
    def __init__(self, inner: Any, recorded: Recorded) -> None:
        self.inner, self.recorded = inner, recorded

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def decide(self, request: Any) -> Any:
        failure = self.recorded.failure(request.request_hash)
        if failure:
            raise failure
        return await self.recorded.watch(request.request_hash, self.inner.decide(request))


class ReplayWiring(wiring.Wiring):
    """The real wiring, with recorded failures injected above each cache."""

    def __init__(self, *args: Any, recorded: Recorded, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.recorded = recorded

    def chat(self, spec: pilot.CellSpec, arm: pilot.ArmSpec, role: str) -> wiring.ChatLane:
        lane = super().chat(spec, arm, role)
        return wiring.ChatLane(_FailFirstProvider(lane.provider, self.recorded), lane.model)

    def decision(self, spec: pilot.CellSpec, leaf: Any, role: str) -> Any:
        return _FailFirstBackend(super().decision(spec, leaf, role), self.recorded)


def hooks_for(leaves: wiring.Leaves, ledger: Path, cache_dir: Path, recorded: Recorded) -> pilot.Hooks:
    """Same assembly as ``v4_wiring._hooks`` (live and dry runs), over replay wiring."""
    writer = LedgerWriter(ledger)
    wired = ReplayWiring(leaves, writer, cache_dir, offline=True, recorded=recorded)

    def rows_for(run: str) -> List[Dict[str, Any]]:
        return [r for r in writer.rows() if r.get("run") == run]

    return pilot.Hooks(build_policies=lambda spec, pw, world: wiring.build_policies(spec, pw, world, factories=wired),
                       ledger_tags=wiring.ledger_context, ledger_rows=rows_for, make_backend=lambda name: None,
                       reconcile=wired.reconcile)


def recorded_errors(ledger: Path, run_tag: str) -> Dict[str, List[str]]:
    """Failed calls of one recorded execution, in order, from the local usage ledger (error rows hold no secrets)."""
    out: Dict[str, List[str]] = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            row = json.loads(line) if line.strip() else {}
            if row.get("run") == run_tag and row.get("error") and row.get("request_hash"):
                out[row["request_hash"]] = [*out.get(row["request_hash"], []), row["error"]]
    return out


def offline_leaves(pod_base_url: str, served_suffix: str = "", recorded: Optional[Recorded] = None) -> wiring.Leaves:
    """Leaves that look like the live ones (same ``describe()``) but can never call out."""
    recorded = recorded or Recorded()
    def pod(model: str) -> Tuple[Any, str]:
        served = model + served_suffix
        provider = OpenAICompatProvider(pod_base_url, api_key=PLACEHOLDER, allowed_models=[served],
                                        extra_body=wiring.POD_EXTRA)
        return _NoCallProvider(provider, recorded), served

    def nous() -> Any:
        return _NoCallProvider(OpenAICompatProvider(wiring.NOUS_URL, api_key=PLACEHOLDER,
                                                    allowed_models=[wiring.NOUS_MODEL], extra_body=wiring.NOUS_EXTRA),
                               recorded)

    def slm() -> Any:
        provider, served = pod(wiring.SLM_MODEL)
        return _NoCallBackend(SLMBackend(provider, served), recorded)

    def refuse() -> Any:
        raise OfflineError("not available offline")

    return wiring.Leaves(nous=nous, pod=pod, slm=slm,
                         jev=lambda: _NoCallBackend(JevBackend(api_key=PLACEHOLDER), recorded),
                         laya=lambda: _NoCallBackend(LayaBackend(), recorded), deepseek=refuse)


LeavesFactory = Callable[[str, str, Recorded], wiring.Leaves]


def pod_candidates(arm: str) -> List[Tuple[str, str]]:
    """(pod base URL, served suffix) options to try. Arms with no pod need only one."""
    spec = pilot.ARMS[arm]
    if not (spec.backend == "vllm" or spec.escalation):
        return [("http://pod.invalid/v1", "")]
    return [(f"https://{pid}-8000.proxy.runpod.net/v1", sfx) for pid in POD_IDS for sfx in SERVED_SUFFIXES]


def compress_events(bundle_dir: Path) -> None:
    """Event logs dominate bundle size; keep them as .jsonl.gz (frames are already .json.gz)."""
    for log in (bundle_dir / "events").glob("*.jsonl"):
        with log.open("rb") as src, gzip.GzipFile(log.with_name(log.name + ".gz"), "wb", mtime=0) as dst:
            shutil.copyfileobj(src, dst)
        log.unlink()


def _bundle_path(out: Path, spec: pilot.CellSpec) -> Path:
    return out / spec.world / f"{spec.arm}-s{spec.seed}-{spec.condition}"


def replay_one(recorded: Mapping[str, Any], worlds: Mapping[str, Any], cache_dir: Path, out: Path, *,
               ledger: Optional[Path] = None, leaves_factory: LeavesFactory = offline_leaves) -> Dict[str, Any]:
    """Replay one recorded cell offline; the bundle is kept only if both hashes match."""
    spec = pilot.CellSpec(recorded["world"], recorded["arm"], recorded["seed"], recorded["condition"])
    # (plan.json carries no budget-cut queen_every overrides)
    entry: Dict[str, Any] = {"key": recorded["key"], "recorded_trace_hash": recorded["trace_hash"],
                             "recorded_config_hash": recorded["config_hash"], "match": False, "bundle": None}
    attempts: List[str] = []
    errors = recorded_errors(ledger, recorded["run_tag"]) if ledger else {}
    for url, suffix in pod_candidates(spec.arm):
        replay = Recorded(errors)
        with tempfile.TemporaryDirectory() as scratch:
            hooks = hooks_for(leaves_factory(url, suffix, replay), Path(scratch) / "ledger.jsonl", cache_dir, replay)
            bdir = Path(scratch) / "bundle"
            try:
                cell = asyncio.run(pilot.arun_cell(spec, worlds[spec.world], hooks.build_policies,
                                                   ledger_tags=hooks.ledger_tags, ledger_rows=hooks.ledger_rows,
                                                   reconcile=hooks.reconcile, bundle_dir=bdir))
            except Exception as exc:  # setup or run failure: try the next candidate, keep the reason
                attempts.append(f"{type(exc).__name__}: {exc}"[:160])
                continue
            entry.update(replayed_trace_hash=cell["trace_hash"], replayed_config_hash=cell["config_hash"],
                         cache_misses=len(replay.misses), recorded_errors_replayed=replay.replayed_errors,
                         cache_hits=cell["cache_hits"],
                         policy_failures=cell["policy_failures"], event_count=cell["event_count"])
            exact = (cell["trace_hash"] == recorded["trace_hash"] and cell["config_hash"] == recorded["config_hash"]
                     and not replay.misses and cell["policy_failures"] == recorded.get("policy_failures"))
            if exact:
                dest = _bundle_path(out, spec)
                compress_events(bdir)
                if dest.exists():
                    shutil.rmtree(dest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(bdir, dest)
                podded = "invalid" not in url
                entry.update(match=True, bundle=str(dest.relative_to(out)), pod_base_url=url if podded else None,
                             served_suffix=suffix if podded else None)
                return entry
            attempts.append(f"hash/calls mismatch (pod {url.split('//')[1].split('-')[0]}, suffix {suffix or 'none'}):"
                            f" trace {'=' if cell['trace_hash'] == recorded['trace_hash'] else '!='},"
                            f" config {'=' if cell['config_hash'] == recorded['config_hash'] else '!='},"
                            f" misses {len(replay.misses)}")
    entry["why_not"] = attempts[-1] if len(set(attempts)) == 1 else attempts[:3]
    return entry


def default_selection(cells: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Every (world, arm): seed 1 / v1, plus seed 1 / base for S (S' runs on variants only)."""
    by_key = {c["key"]: c for c in cells}
    pairs = sorted({(c["world"], c["arm"]) for c in cells})
    out = []
    for world, arm in pairs:
        keys = [f"{world}|{arm}|1|v1"] + ([f"{world}|{arm}|1|base"] if arm == "S" else [])
        out += [by_key[k] for k in keys if k in by_key]
    return out


def load_worlds() -> Dict[str, Any]:
    worlds = {}
    for name, ref in DEFAULT_WORLDS.items():
        module, attr = ref.split(":")
        worlds[name] = getattr(importlib.import_module(module), attr)
    return worlds


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--cells", nargs="*", help="cell keys (default: the seed-1 v1 selection + S base)")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    root = Path(args.root)
    exp = root / EXP_REL
    out = Path(args.out) if args.out else exp / "bundles"
    cells = pilot.load_cells(exp / "cells.jsonl")
    chosen = [c for c in cells if c["key"] in set(args.cells)] if args.cells else default_selection(cells)
    worlds = load_worlds()
    entries = []
    for cell in chosen:
        entry = replay_one(cell, worlds, root / "cache/v4-pilot", out, ledger=root / "ledger/v4-pilot-usage.jsonl")
        entries.append(entry)
        print(f"{'OK  ' if entry['match'] else 'FAIL'} {entry['key']}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    report = {"note": "offline replay from reply caches; no model call, no network, no key",
              "replayed": len(entries), "matched": sum(e["match"] for e in entries), "cells": entries}
    (out / "REPLAY.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"replayed": report["replayed"], "matched": report["matched"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
