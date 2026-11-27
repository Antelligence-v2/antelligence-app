"""Tests for L1Gate, grandchild repro, 20k depth-4 fuzz, escrow forfeit, kill, SIGTERM, usability, sandbox."""
from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
import time

import pytest

from antelligence.record import (
    InvalidRunError,
    L1Gate,
    SandboxViolation,
    audit_tree,
    check_bundle,
    export_bundle,
    load_live_state,
    verify_worker_sandbox,
)


def test_grandchild_repro_caught(tmp_path):
    """v4.8 grandchild repro: 20 vs 10 micro-USD leak must be blocked."""
    root = L1Gate(str(tmp_path / "root.jsonl"), "root", "t", ["shell"], {"spend_microusd": 10, "max_steps": 10, "max_depth": 3})
    c1 = root.spawn_child("c1", "t", ["shell"], {"spend_microusd": 10, "max_steps": 10, "max_depth": 3})
    g1 = c1.spawn_child("g1", "t", ["shell"], {"spend_microusd": 10, "max_steps": 10, "max_depth": 3})
    for _ in range(2):
        assert g1.model_call("m", "x", 5)
        assert g1.model_result(1, 1, 5, "y")
    c1.finish_child("g1")
    root.finish_child("c1")

    assert root.remaining() == (0, 8)
    assert root.model_call("m", "x", 10) is False
    root.end("pass")

    total_spent = root.spent + c1.spent + g1.spent
    assert total_spent == 10
    res = audit_tree(str(tmp_path))
    assert res["valid"] and res["violations"] == []


def test_depth4_budget_fuzz_20k(tmp_path):
    """20,000 random trees up to depth 4: zero spend/step cap violations."""
    violations = 0
    base = str(tmp_path)
    for seed in range(20_000):
        rng = random.Random(seed)
        B = rng.randint(0, 12)
        K = rng.randint(0, 6)
        D = rng.randint(1, 4)
        rdir = os.path.join(base, f"r{seed % 32}")
        os.makedirs(rdir, exist_ok=True)
        root = L1Gate(os.path.join(rdir, "root.jsonl"), "root", "t", ["shell"], {"spend_microusd": B, "max_steps": K, "max_depth": D})
        gates = [root]
        names = 0
        total_cost = 0
        reserves: dict[int, list[int]] = {}
        for _ in range(rng.randint(5, 30)):
            live = [g for g in gates if not g.ended]
            if not live:
                break
            g = rng.choice(live)
            op = rng.choice(["call", "result", "result", "spawn", "finish", "call"])
            if op == "call":
                W = rng.randint(0, 5)
                if g.model_call("m", "x", W):
                    reserves.setdefault(id(g), []).append(W)
            elif op == "result":
                r = reserves.get(id(g), [])
                if r:
                    W = r.pop(0)
                    c = rng.randint(0, W)
                    g.model_result(1, 1, c, "y")
                    total_cost += c
            elif op == "spawn":
                names += 1
                c = g.spawn_child(f"c{names}", "t", ["shell"], {"spend_microusd": rng.randint(0, 5), "max_steps": rng.randint(0, 4), "max_depth": rng.randint(g.depth + 1, D + 1)})
                if c is not None:
                    gates.append(c)
            elif op == "finish" and g.parent is not None:
                for p in gates:
                    if g.run in p.children and p.children[g.run]["state"] == "live" and not p.ended:
                        p.finish_child(g.run)
                        break
        for g in gates:
            if not g.ended:
                g.close_file()
        spent = sum(x.spent for x in gates)
        calls = sum(x.calls for x in gates)
        if spent > B or calls > K or total_cost > B:
            violations += 1
    assert violations == 0


def test_crashed_child_forfeits_escrow(tmp_path):
    """A crashed/external child that never writes run_end forfeits its full escrowed slice."""
    root = L1Gate(str(tmp_path / "root.jsonl"), "root", "t", ["shell"], {"spend_microusd": 100, "max_steps": 10, "max_depth": 2})
    assert root.spawn_child("c_crash", "t", ["shell"], {"spend_microusd": 40, "max_steps": 4, "max_depth": 2}, external=True) is None
    # Simulate crashed child: partial log with no run_end
    with open(tmp_path / "c_crash.jsonl", "w", encoding="utf-8") as f:
        f.write('{"partial":true}\n')
    root.finish_child("c_crash")
    assert root.children["c_crash"]["state"] == "forfeited"
    assert root.remaining() == (60, 6)
    root.end("pass")


def test_max_concurrent_workers_and_kill_file(tmp_path):
    root = L1Gate(str(tmp_path / "root.jsonl"), "root", "t", ["shell"], {"spend_microusd": 100, "max_steps": 10, "max_depth": 2}, max_concurrent_workers=1)
    c1 = root.spawn_child("c1", "t", ["shell"], {"spend_microusd": 20, "max_steps": 2, "max_depth": 1})
    assert c1 is not None
    assert root.spawn_child("c2", "t", ["shell"], {"spend_microusd": 20, "max_steps": 2, "max_depth": 1}) is None
    assert "child_max_concurrent_workers" in root.refusals
    root.finish_child("c1")
    # Kill file aborts subsequent operations
    (tmp_path / "root.jsonl.kill").write_text("stop", encoding="utf-8")
    assert root.note("after kill") is False
    assert root.ended and root.end_status == "aborted"


def test_usability_gate_blocks_export(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    g = L1Gate(str(run_dir / "root.jsonl"), "root", "t", ["shell"], {"spend_microusd": 100, "max_steps": 20, "max_depth": 1})
    for i in range(10):
        assert g.model_call("m", f"in{i}", 1)
        assert g.model_result(1, 1, 1, f"out{i}", format_ok=(i < 8))  # 8/10 = 80% < 85%
    g.end("pass")

    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "INVALID_RUN"
    assert status["usable_rate"] == 0.8

    with pytest.raises(InvalidRunError, match="STATUS=INVALID_RUN"):
        export_bundle(str(run_dir), str(tmp_path / "exported"))


def test_sigterm_writes_atomic_run_status(tmp_path):
    run_dir = tmp_path / "sig"
    run_dir.mkdir()
    script = (
        "import time; from antelligence.record import L1Gate; "
        f"g = L1Gate({str(run_dir / 'root.jsonl')!r}, 'r-sig', 't', ['shell'], "
        "{'spend_microusd': 10, 'max_steps': 5, 'max_depth': 1}, install_sigterm=True); "
        "time.sleep(10)"
    )
    proc = subprocess.Popen([sys.executable, "-c", script])
    status_file = run_dir / "run_status.json"
    for _ in range(50):
        if status_file.exists():
            break
        time.sleep(0.05)
    assert status_file.exists()
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)
    st = json.loads(status_file.read_text(encoding="utf-8"))
    assert st["status"] == "aborted"


def test_live_state_loader_ignores_prose_and_sandbox_check(tmp_path):
    run_dir = tmp_path / "live"
    run_dir.mkdir()
    (run_dir / "README.md").write_text("# Ignore me\n", encoding="utf-8")
    (run_dir / "run_status.json").write_text('{"status":"running"}', encoding="utf-8")
    (run_dir / "env_state.json").write_text('{"step":3}', encoding="utf-8")
    state = load_live_state(str(run_dir))
    assert set(state.keys()) == {"run_status.json", "env_state.json"}

    cfg = tmp_path / "worker_cfg"
    cfg.mkdir()
    assert verify_worker_sandbox(str(cfg), ["read_file", "grep"])["ok"] is True

    with pytest.raises(SandboxViolation):
        verify_worker_sandbox(str(cfg), ["*"])

    (cfg / "AGENTS.md").write_text("leaked", encoding="utf-8")
    with pytest.raises(SandboxViolation, match="AGENTS.md"):
        verify_worker_sandbox(str(cfg), ["read_file"])
