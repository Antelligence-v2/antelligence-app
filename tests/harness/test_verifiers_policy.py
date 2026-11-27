"""Tests for Verifier (deterministic checks, phantom spans, AST sandbox, cross-family Checker) and Policy."""

from __future__ import annotations

import asyncio
import json

import pytest

from antelligence.harness.core import Artifact, Task
from antelligence.harness.policy import (
    CalibrationGate,
    CDMGateError,
    CDMWrapper,
    Policy,
    UncalibratedGateError,
)
from antelligence.harness.verifiers import SelfCheckError, Verifier, check_code, run_sandbox


def test_calibration_gate_blocks_raw_logprobs_and_passes_calibrated(tmp_path):
    # Well-calibrated dev split: 9/10 correct at p=0.90, 6/10 correct at p=0.60 -> ECE = 0.0
    dev_probs = (
        [{"bug": 0.90, "other": 0.10}] * 10
        + [{"bug": 0.60, "other": 0.40}] * 10
    )
    dev_labels = (["bug"] * 9 + ["other"]) + (["bug"] * 6 + ["other"] * 4)

    # Raw SLM logprobs are explicitly banned
    with pytest.raises(UncalibratedGateError, match="raw SLM logprobs"):
        Policy.fit_conformal(dev_probs, dev_labels, is_raw_logprobs=True)

    with pytest.raises(UncalibratedGateError, match="raw SLM logprobs"):
        CalibrationGate().evaluate([0.99, 0.98], [True, False], source="raw_logprobs")

    # Overconfident uncalibrated predictions fail held-out ECE/Brier
    bad_report = CalibrationGate(max_ece=0.10).evaluate([0.99, 0.99, 0.99, 0.99], [True, False, False, False])
    assert not bad_report.passed
    with pytest.raises(UncalibratedGateError):
        Policy.fit_threshold([0.99, 0.99, 0.99, 0.99], [True, False, False, False], gate=CalibrationGate(max_ece=0.10))

    # Calibrated dev split passes CalibrationGate and serializes with sha256
    pol = Policy.fit_conformal(dev_probs, dev_labels, alpha=0.15, source="isotonic_dev")
    assert pol.calibration is not None and pol.calibration.passed

    path = tmp_path / "policy.json"
    sha = pol.save(path)
    loaded = Policy.load(path, expect_sha256=sha)
    assert loaded.sha256 == sha

    # Runtime raw logprob flag is still blocked
    with pytest.raises(UncalibratedGateError):
        loaded.decide({"bug": 0.9, "other": 0.1}, is_raw_logprobs=True)

    dec_keep = loaded.decide({"bug": 0.95, "other": 0.05})
    assert not dec_keep.escalate
    dec_esc = loaded.decide({"bug": 0.52, "other": 0.48})
    assert dec_esc.escalate


def test_verifier_catches_100_percent_synthetic_phantom_spans_and_sandbox():
    source = (
        "### Describe the bug\n"
        "App crashes with SegmentationFault when loading an empty config file.\n"
        "### To reproduce\n"
        "Run cli --config empty.yaml on macOS.\n"
    )
    verifier = Verifier(allowed_labels={"bug", "other"}, min_span_len=12)

    phantom_payloads = [
        {"label": "bug", "confidence": 0.9, "evidence_span": "This text does not exist anywhere", "rationale": "x"},
        {"label": "bug", "confidence": 0.9, "evidence_span": "### Describe the bug", "rationale": "boilerplate"},
        {"label": "bug", "confidence": 0.9, "evidence_span": "short", "rationale": "too short"},
        {"label": "bug", "confidence": 0.9, "evidence_span": "", "rationale": "empty"},
    ]
    caught = sum(1 for p in phantom_payloads if not verifier.verify_deterministic(p, source_text=source).strict_ok)
    assert caught == len(phantom_payloads)

    valid = {
        "label": "bug",
        "confidence": 0.92,
        "evidence_span": "App crashes with SegmentationFault when loading an empty config file.",
        "rationale": "crash report",
    }
    res = verifier.verify_deterministic(json.dumps(valid), source_text=source)
    assert res.ok and res.strict_ok and res.lenient_ok

    # AST sandbox: refuses dangerous code, executes safe math in python -I -S
    assert not run_sandbox("import os\nprint(os.getcwd())").ok
    assert not run_sandbox("print((1).__class__)").ok
    ok_sbx = run_sandbox("import math\nprint(math.factorial(5))")
    assert ok_sbx.ok and ok_sbx.stdout.strip() == "120"


def test_cross_family_checker_bans_self_check():
    verifier = Verifier(allowed_labels={"bug", "other"})
    task = Task(id="t1", payload={"title": "Crash", "body": "Null pointer dereference on startup."})
    maker_art = Artifact(
        task_id="t1",
        tool="maker",
        answer="bug",
        payload={
            "label": "bug",
            "confidence": 0.9,
            "evidence_span": "Null pointer dereference on startup.",
            "rationale": "npe",
        },
    )

    with pytest.raises(SelfCheckError):
        asyncio.run(
            verifier.verify_with_checker(
                task,
                maker_art,
                maker_model="qwen2.5-3b",
                checker_model="qwen2.5-72b",
                source_text="Null pointer dereference on startup.",
            )
        )


def test_cdm_wrapper_gated_to_20_labels_plus_other_and_seeded_shuffle():
    with pytest.raises(CDMGateError):
        CDMWrapper(["bug", "docs"])  # missing 'other'
    with pytest.raises(CDMGateError):
        CDMWrapper([f"l{i}" for i in range(20)] + ["other"])  # 21 > 20

    labels = ("bug", "documentation", "other")
    cdm = CDMWrapper(labels, seed=42)
    s1 = cdm.shuffled_options("task-1")
    s2 = cdm.shuffled_options("task-1")
    assert s1 == s2
    assert set(s1) == set(labels)
    unshuffled = cdm.unshuffle_probs({s1[0]: 0.7, s1[1]: 0.2, s1[2]: 0.1})
    assert abs(sum(unshuffled.values()) - 1.0) < 1e-9
