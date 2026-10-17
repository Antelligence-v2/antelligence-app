"""v4_replay_bundles: offline replay from the reply caches reproduces the recorded hashes and writes a bundle."""

import asyncio
import gzip
import json
from pathlib import Path

import pytest

from antelligence.experiments import v4_pilot as p
from antelligence.experiments import v4_wiring as w
from antelligence.kernel.canonical import content_hash
from antelligence.provenance.bundle import verify_bundle_integrity
from scripts import v4_replay_bundles as rb
from tests.engine.fake_pilot_world import FAKE_A

WORLDS = {"fake_a": FAKE_A}


def record(tmp_path, arm, seed=1, condition="v1"):
    """A 'live' dry run that fills the cache and the ledger, as the evaluation did."""
    hooks = w.make_dry_hooks(ledger=tmp_path / "ledger.jsonl", cache_dir=tmp_path / "cache")
    spec = p.CellSpec("fake_a", arm, seed, condition)
    cell = asyncio.run(p.arun_cell(spec, FAKE_A, hooks.build_policies, ledger_tags=hooks.ledger_tags,
                                   ledger_rows=hooks.ledger_rows, reconcile=hooks.reconcile))
    return cell


def fake_factory(url, suffix, recorded):
    leaves = w.fake_leaves()
    # the same fakes as the recording, but any call is a miss
    return rb.wiring.Leaves(
        nous=lambda: rb._NoCallProvider(leaves.nous(), recorded),
        pod=lambda m: (rb._NoCallProvider(leaves.pod(m)[0], recorded), m),
        jev=lambda: rb._NoCallBackend(leaves.jev(), recorded), laya=lambda: rb._NoCallBackend(leaves.laya(), recorded),
        slm=lambda: rb._NoCallBackend(leaves.slm(), recorded), deepseek=leaves.deepseek)


@pytest.fixture(autouse=True)
def fake_arms(monkeypatch):
    monkeypatch.setattr(rb, "pod_candidates", lambda arm: [("http://pod.invalid/v1", "")])


@pytest.mark.parametrize("arm", ["S", "DS-all", "F-Jev"])
def test_replay_reproduces_hashes_and_writes_bundle(tmp_path, arm):
    recorded = record(tmp_path, arm)
    out = tmp_path / "bundles"
    entry = rb.replay_one(recorded, WORLDS, tmp_path / "cache", out, leaves_factory=fake_factory)
    assert entry["match"] and entry["replayed_trace_hash"] == recorded["trace_hash"]
    assert entry["replayed_config_hash"] == recorded["config_hash"] and entry["cache_misses"] == 0
    folder = out / entry["bundle"]
    assert folder == out / "fake_a" / f"{arm}-s1-v1"
    bundle = json.loads((folder / f"fake_a-{arm}-s1-v1.bundle.json").read_text())
    assert verify_bundle_integrity(bundle) and bundle["trace_hash"] == recorded["trace_hash"]
    assert bundle["extra"]["cell"] == recorded["key"]
    assert list((folder / "events").glob("*.jsonl.gz")) and not list((folder / "events").glob("*.jsonl"))
    assert list(folder.glob("*.frames.json.gz"))
    frames = json.loads(gzip.open(next(folder.glob("*.frames.json.gz")), "rt").read())
    assert frames["frames"] and content_hash(bundle["spec"])


def test_cache_miss_is_a_failure_not_a_model_call(tmp_path):
    recorded = record(tmp_path, "DS-all")
    empty = tmp_path / "empty-cache"
    entry = rb.replay_one(recorded, WORLDS, empty, tmp_path / "bundles", leaves_factory=fake_factory)
    assert not entry["match"] and entry["cache_misses"] > 0 and entry["bundle"] is None
    assert not (tmp_path / "bundles").exists()


def test_recorded_failure_is_replayed_before_the_cache(tmp_path):
    recorded = record(tmp_path, "DS-all")
    first = next(iter(rb.recorded_errors(tmp_path / "ledger.jsonl", recorded["run_tag"])), None)
    assert first is None  # the dry run made no failing call
    rec = rb.Recorded({"abc": ["ProviderError: HTTP 429: slow down"]})
    assert isinstance(rec.failure("abc"), Exception) and rec.failure("abc") is None and rec.replayed_errors == 1


def test_no_key_is_read_or_held(tmp_path):
    leaves = rb.offline_leaves("https://pod.example/v1")
    assert leaves.jev().inner._api_key == rb.PLACEHOLDER
    with pytest.raises(rb.OfflineError):
        asyncio.run(leaves.jev().decide(type("R", (), {"request_hash": "h" * 64})()))


def test_default_selection_is_seed1_v1_plus_s_base():
    cells = [{"key": f"w|{a}|{s}|{c}", "world": "w", "arm": a} for a in ("S", "S-prime", "F-Jev")
             for s in (1, 2) for c in ("base", "v1")]
    keys = [c["key"] for c in rb.default_selection(cells)]
    assert keys == ["w|F-Jev|1|v1", "w|S|1|v1", "w|S|1|base", "w|S-prime|1|v1"]
    assert Path(rb.__file__).name == "v4_replay_bundles.py"
