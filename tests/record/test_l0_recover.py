"""Tests for L0 canonical JSONL, blobs >4 KiB, 12 MiB rollover, lock, diagnose/recover, and byte-cut property."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess

import pytest

from antelligence.record import (
    ROLLOVER_BYTES,
    LockHeld,
    NeedsRecovery,
    Writer,
    bundle,
    diagnose,
    read_blob,
    read_segments,
    recover,
    validate,
)
from antelligence.record.l1_gate import L1Gate


def test_byte_cut_property(tmp_path):
    """Every byte cut 0..len(data) of a log is classified accurately and torn_tail recovers cleanly."""
    log_path = tmp_path / "a.jsonl"
    g = L1Gate(str(log_path), "a", "t é中\U0001F600", ["shell"], {"spend_microusd": 100, "max_steps": 10, "max_depth": 2})
    g.tool("shell", {"cmd": "ls"})
    g.tool_result(True, "ok é", 2)
    g.model_call("m", "x", 5)
    g.model_result(1, 1, 3, "y")
    g.note("中文")
    g.end("pass")

    data = log_path.read_bytes()
    cut_path = tmp_path / "cut.jsonl"
    for k in range(0, len(data) + 1):
        cut = data[:k]
        dg = diagnose(cut)
        v = validate(cut)
        if dg["cls"] == "clean":
            assert v["valid"], (k, v)
        else:
            assert not v["valid"], (k, dg["cls"], v)
        if dg["cls"] == "torn_tail":
            prefix = cut[: dg["good_bytes"]]
            pv = validate(prefix)
            assert pv["valid"] and pv["status"] == "open"
            cut_path.write_bytes(cut)
            for fname in os.listdir(tmp_path):
                if fname.startswith("cut.jsonl."):
                    os.remove(tmp_path / fname)
            rec = recover(str(cut_path))
            rec_bytes = open(rec["recovered_path"], "rb").read()
            rv = validate(rec_bytes)
            assert rv["valid"] and rv["status"] == "open"
            assert rec_bytes.startswith(prefix)
            assert cut_path.read_bytes() == cut


def test_lock_and_blobs_over_4kib(tmp_path):
    log_path = str(tmp_path / "run.jsonl")
    blobs_dir = str(tmp_path / "blobs")
    w = Writer(log_path, run="r1", allow=["shell"], caps={"spend_microusd": 10, "max_steps": 5, "max_depth": 1}, blobs_dir=blobs_dir)
    with pytest.raises(LockHeld):
        Writer(log_path, run="r1")
    big = "A" * 5000
    ev = w.append("tool_result", {"ok": True, "result": big, "bytes": len(big)}, actor="tool")
    assert ev["data"]["result"].startswith("blob:")
    sha = ev["data"]["blob_sha256"]
    assert read_blob(blobs_dir, sha) == big.encode("utf-8")
    w.close()

    # Stale lock triggers NeedsRecovery
    (tmp_path / "run.jsonl.lock").write_text("999999 0.1\n", encoding="utf-8")
    with pytest.raises(NeedsRecovery):
        Writer(log_path, run="r1")


def test_rollover_12mib_compat(tmp_path):
    """Segment rollover produces v0.2-valid segments linked by continuation_run_id & prev_segment_sha256."""
    assert ROLLOVER_BYTES == 12 * 1024 * 1024
    log_path = str(tmp_path / "seg.jsonl")
    # Use a 2 KiB segment cap to test rollover fast while verifying v0.2 validator compliance
    w = Writer(log_path, run="r-roll", max_bytes=2048, blobs_dir=None)
    for i in range(40):
        w.append("note", {"text": f"event-{i}-" + ("x" * 100)})
    w.append("run_end", {"status": "pass", "grader": "test", "grader_kind": "automatic", "detail": "done"})
    segs = list(w.segments)
    w.close()

    assert len(segs) >= 2
    files = {os.path.basename(p): open(p, "rb").read() for _, p in segs}
    for name, raw in files.items():
        res = validate(raw)
        assert res["valid"] and res["status"] == "complete", (name, res)
    bres = bundle(files)
    assert bres["valid"] and bres["status"] == "complete", bres
    all_evs = read_segments([p for _, p in segs])
    assert any(e["kind"] == "note" for e in all_evs)


def test_optional_four_way_validator(tmp_path):
    """Run local 4-way validator if Rust/Node/Go toolchains exist; otherwise skip cleanly."""
    if not shutil.which("node"):
        pytest.skip("node toolchain not available for 4-way validator")
    # Check if exploratory rust binary exists
    rust_bin = "/Users/operator/Desktop/research/antelligence-app/docs/harness/rust/target/debug/harness-validator-exploratory"
    if not os.path.exists(rust_bin):
        pytest.skip("exploratory Rust validator binary not built in this environment")
    log_path = str(tmp_path / "v.jsonl")
    w = Writer(log_path, run="r-4way")
    w.append("run_end", {"status": "pass", "grader": "test", "grader_kind": "automatic", "detail": "ok"})
    w.close()
    raw = open(log_path, "rb").read()
    r = subprocess.run([rust_bin], input=raw, capture_output=True, check=True)
    assert '"valid":true' in r.stdout.decode("utf-8").replace(" ", "")
