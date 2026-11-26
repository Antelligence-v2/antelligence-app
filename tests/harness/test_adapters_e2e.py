"""Tests for curated_real, mcq_compat, Eval Hygiene Gate, S baseline, and Maker!=Checker cost accounting."""

from __future__ import annotations

import asyncio
import json

import pytest

from antelligence.harness.adapters import (
    CANONICAL_LABELS,
    CuratedRealTriageAdapter,
    EvalHygieneError,
    HoldoutGuard,
    MCQCompatAdapter,
    TFIDFBaseline,
    eval_hygiene_gate,
    load_gh_archive_jsonl,
)
from antelligence.harness.core import Artifact, Task, ToolRegistry, ToolSpec
from antelligence.harness.graph import ExecutionGraph
from antelligence.harness.replay import RecordingBox, ReplayBox
from antelligence.harness.scheduler import LiveBox, run_graph
from antelligence.harness.scorecard import bill, summary
from antelligence.harness.verifiers import Verifier
from antelligence.providers import ChatRequest, FakeProvider


def _synthetic_triage_tasks() -> list[Task]:
    samples = [
        ("t1", "bug", "Crash on startup", "Application throws NullPointerException when config is missing."),
        ("t2", "bug", "Segfault in parser", "Parser crashes with segmentation fault on malformed UTF-8 input."),
        ("t3", "feature_enhancement", "Add dark mode", "Please add dark mode theme support to the settings UI."),
        ("t4", "feature_enhancement", "Support YAML export", "Feature request to export reports in YAML format."),
        ("t5", "documentation", "Typo in README", "The installation section in README.md has a broken link."),
        ("t6", "documentation", "Update API docs", "Document the new authentication header in docs/api.md."),
        ("t7", "question_support", "How to configure proxy", "Question: how do I pass an HTTP proxy to the client?"),
        ("t8", "question_support", "Usage help needed", "How can I reset my local cache directory safely?"),
        ("t9", "build_ci_packaging", "Docker build fails", "GitHub Actions CI workflow fails during wheel packaging."),
        ("t10", "build_ci_packaging", "Pin setuptools in pyproject", "Build fails on Python 3.12 without setuptools pin."),
        ("t11", "performance", "Slow query latency", "Memory usage spikes and query takes 12 seconds on 10k rows."),
        ("t12", "performance", "Optimize loop allocation", "Profiling shows 80% CPU time spent in inner allocation."),
        ("t13", "security", "XSS vulnerability in render", "Unsanitized user input allows script injection in preview."),
        ("t14", "security", "Rotate leaked token", "CVE advisory: API token logged in plaintext debug output."),
        ("t15", "other", "Release schedule", "When is the next community sync meeting scheduled?"),
        ("t16", "other", "License question", "Checking CLA status for external contributors."),
    ]
    return [
        Task(id=tid, kind="gh_issue_triage", payload={"title": title, "body": body, "label": lbl})
        for tid, lbl, title, body in samples
    ]


def test_gh_archive_offline_loader_and_numpy_s_baseline(tmp_path):
    events = [
        {
            "id": "101",
            "type": "IssuesEvent",
            "created_at": "2026-11-01T10:00:00Z",
            "actor": {"login": "triager1"},
            "repo": {"name": "org/repo"},
            "payload": {
                "action": "labeled",
                "label": {"name": "bug"},
                "issue": {
                    "id": 1,
                    "comments": 0,
                    "user": {"login": "alice"},
                    "title": "Crash on empty input",
                    "body": "Contact alice@example.com; throws ValueError on empty payload.",
                },
            },
        },
        {  # bot actor filtered
            "id": "102",
            "type": "IssuesEvent",
            "actor": {"login": "dependabot[bot]"},
            "payload": {"action": "labeled", "label": {"name": "bug"}, "issue": {"comments": 0, "user": {"login": "a"}, "title": "x", "body": "y"}},
        },
        {  # self-label filtered
            "id": "103",
            "type": "IssuesEvent",
            "actor": {"login": "alice"},
            "payload": {"action": "labeled", "label": {"name": "bug"}, "issue": {"comments": 0, "user": {"login": "alice"}, "title": "x", "body": "y"}},
        },
    ]
    jsonl = tmp_path / "gh.jsonl"
    jsonl.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    loaded = load_gh_archive_jsonl(jsonl)
    assert len(loaded) == 1
    assert loaded[0].payload["label"] == "bug"
    assert "[EMAIL]" in loaded[0].payload["body"]
    assert "alice@example.com" not in loaded[0].payload["body"]

    # Pure-numpy S baseline fit + predict on synthetic issue triage fixture
    tasks = _synthetic_triage_tasks()
    baseline = TFIDFBaseline(CANONICAL_LABELS, epochs=150).fit(tasks)
    adapter = CuratedRealTriageAdapter()
    scores = [adapter.score(t, baseline.predict_artifact(t)) for t in tasks]
    assert sum(scores) / len(scores) >= 0.85


def test_eval_hygiene_gate_flags_60_8_shortcut_and_holdout_double_peek():
    # Construct 120 MCQ tasks where 73/120 (60.83%) are solved by a surface/syllogism cue
    tasks = []
    for i in range(120):
        is_shortcut = i < 73
        opts = {
            "A": "Short",
            "B": "All mammals are warm-blooded therefore this must be true" if is_shortcut else "Option B",
            "C": "Tiny",
            "D": "Brief",
        }
        gold = "B" if is_shortcut else "A"
        tasks.append(Task(id=f"mcq-{i}", kind="mcq", payload={"question": f"Q{i}", "options": opts, "answer": gold}))

    mcq = MCQCompatAdapter()
    audit = mcq.audit_shortcuts(tasks)
    assert abs(audit["shortcut_rate"] - 73 / 120) < 1e-3
    assert audit["shortcut_flagged"] is True

    arts = [mcq.parse_output(t, '{"answer":"A"}') for t in tasks]
    report = eval_hygiene_gate(mcq, tasks, arts, s_baseline_score=0.25, split="dev")
    assert not report.passed
    assert report.shortcut_flagged

    # Holdout double-peek check
    guard = HoldoutGuard()
    holdout_tasks = tasks[:10]
    eval_hygiene_gate(mcq, holdout_tasks, arts[:10], s_baseline_score=0.25, split="holdout", holdout_guard=guard, max_shortcut_rate=0.99)
    with pytest.raises(EvalHygieneError, match="double-peek"):
        eval_hygiene_gate(mcq, holdout_tasks, arts[:10], s_baseline_score=0.25, split="holdout", holdout_guard=guard, max_shortcut_rate=0.99)


def test_mcq_compat_parity_on_fixture_batch_with_replay_box(tmp_path):
    tasks = [
        Task(id="q1", kind="mcq", payload={"question": "2+2?", "options": ["3", "4", "5", "6"], "answer": "B"}),
        Task(id="q2", kind="mcq", payload={"question": "Capital of France?", "options": {"A": "Rome", "B": "Berlin", "C": "Paris", "D": "Madrid"}, "answer": "C"}),
    ]
    mcq = MCQCompatAdapter()

    async def run_mcq(task: Task, deps) -> Artifact:
        raw = '{"answer": "B"}' if task.id == "q1" else "The answer is C."
        art = mcq.parse_output(task, raw, tool="legacy_mcq")
        return Artifact(**{**art.to_dict(), "tokens_in": 10, "tokens_out": 4, "cost_usd": 0.001, "calls": 1})

    reg = ToolRegistry([ToolSpec(name="legacy_mcq", run=run_mcq)])
    graph = ExecutionGraph().add("legacy_mcq")

    rec = RecordingBox(LiveBox())
    res_live = asyncio.run(run_graph(tasks, graph, reg, box=rec))
    box_path = tmp_path / "mcq_replay.jsonl"
    rec.to_replay_box().to_jsonl(box_path)

    res_replay = asyncio.run(run_graph(tasks, graph, reg, box=ReplayBox.from_jsonl(box_path)))
    for tid in ("q1", "q2"):
        assert res_replay.artifacts[tid]["legacy_mcq"].answer == res_live.artifacts[tid]["legacy_mcq"].answer
        assert mcq.score(tasks[0 if tid == "q1" else 1], res_replay.artifacts[tid]["legacy_mcq"]) == 1.0


def test_end_to_end_maker_checker_escalation_cost_accounting():
    tasks = [
        Task(
            id="e1",
            kind="gh_issue_triage",
            payload={
                "title": "Crash on empty config",
                "body": "App throws NullPointerException when config.yaml is empty.",
                "label": "bug",
            },
        ),
        Task(
            id="e2",
            kind="gh_issue_triage",
            payload={
                "title": "Slow query on 10k rows",
                "body": "Database query takes 12 seconds when filtering 10k rows.",
                "label": "performance",
            },
        ),
    ]
    adapter = CuratedRealTriageAdapter()
    verifier = Verifier(allowed_labels=CANONICAL_LABELS)

    maker_provider = FakeProvider(
        lambda req: (
            '{"label":"bug","confidence":0.95,"evidence_span":"App throws NullPointerException when config.yaml is empty.","rationale":"crash"}'
            if "Crash" in req.messages[-1]["content"]
            else '{"label":"other","confidence":0.55,"evidence_span":"Database query takes 12 seconds when filtering 10k rows.","rationale":"uncertain"}'
        )
    )
    checker_provider = FakeProvider(
        lambda req: (
            '{"label":"bug"}' if "Crash" in req.messages[-1]["content"] else '{"label":"performance"}'
        )
    )
    frontier_provider = FakeProvider(
        lambda req: '{"label":"performance","confidence":0.98,"evidence_span":"Database query takes 12 seconds when filtering 10k rows.","rationale":"perf"}'
    )

    async def maker_step(task: Task, deps) -> Artifact:
        resp = await maker_provider.complete(
            ChatRequest(model="qwen2.5-3b", messages=[{"role": "user", "content": adapter.format_input(task)}])
        )
        art = adapter.parse_output(task, resp.content, tool="maker")
        return Artifact(
            **{**art.to_dict(), "tokens_in": resp.prompt_tokens, "tokens_out": resp.completion_tokens, "cost_usd": 0.0002, "calls": 1}
        )

    async def checker_step(task: Task, deps) -> Artifact:
        maker_art = deps["maker"]

        async def _check_fn(t: Task, m_art: Artifact) -> Artifact:
            resp = await checker_provider.complete(
                ChatRequest(model="gemini-2.5-flash", messages=[{"role": "user", "content": adapter.format_input(t)}])
            )
            lbl = json.loads(resp.content)["label"]
            return Artifact(
                task_id=t.id, tool="checker", answer=lbl, format_ok=True,
                tokens_in=resp.prompt_tokens, tokens_out=resp.completion_tokens, cost_usd=0.0005, calls=1,
            )

        vres = await verifier.verify_with_checker(
            task, maker_art, maker_model="qwen2.5-3b", checker_model="gemini-2.5-flash",
            checker_fn=_check_fn, source_text=f"{task.payload['title']}\n{task.payload['body']}",
        )
        c_art = vres.checker_artifact
        return Artifact(
            task_id=task.id,
            tool="checker",
            answer="escalate" if vres.escalate else "accept",
            format_ok=True,
            tokens_in=c_art.tokens_in if c_art else 0,
            tokens_out=c_art.tokens_out if c_art else 0,
            cost_usd=c_art.cost_usd if c_art else 0.0,
            calls=c_art.calls if c_art else 0,
        )

    async def frontier_step(task: Task, deps) -> Artifact:
        resp = await frontier_provider.complete(
            ChatRequest(model="claude-sonnet-4", messages=[{"role": "user", "content": adapter.format_input(task)}])
        )
        art = adapter.parse_output(task, resp.content, tool="frontier")
        return Artifact(
            **{**art.to_dict(), "tokens_in": resp.prompt_tokens, "tokens_out": resp.completion_tokens, "cost_usd": 0.005, "calls": 1}
        )

    reg = ToolRegistry([
        ToolSpec(name="maker", run=maker_step, model_key="qwen2.5-3b"),
        ToolSpec(name="checker", run=checker_step, model_key="gemini-2.5-flash"),
        ToolSpec(name="frontier", run=frontier_step, model_key="claude-sonnet-4"),
    ])
    graph = (
        ExecutionGraph()
        .add("maker")
        .add("checker", deps=("maker",))
        .add("frontier", deps=("checker",), when=lambda deps: deps["checker"].answer == "escalate")
    )

    rec = RecordingBox(LiveBox())
    res = asyncio.run(run_graph(tasks, graph, reg, box=rec))
    assert "frontier" in res.skipped["e1"]
    assert "frontier" in res.artifacts["e2"]

    outcomes = []
    for t in tasks:
        arts = list(res.artifacts[t.id].values())
        final_art = res.artifacts[t.id].get("frontier") or res.artifacts[t.id]["maker"]
        outcomes.append(bill(t, "maker_checker", final_art.answer, arts, score=adapter.score(t, final_art)))

    # e1: maker ($0.0002) + checker ($0.0005) = $0.0007, 2 calls
    # e2: maker ($0.0002) + checker ($0.0005) + frontier ($0.005) = $0.0057, 3 calls
    assert outcomes[0].calls == 2 and abs(outcomes[0].cost_usd - 0.0007) < 1e-6
    assert outcomes[1].calls == 3 and abs(outcomes[1].cost_usd - 0.0057) < 1e-6
    stats = summary(outcomes)["maker_checker"]
    assert stats["score"] == 1.0
    assert abs(stats["cost_usd"] - 0.0064) < 1e-6

    # ReplayBox $0 recomposition
    replay_res = asyncio.run(run_graph(tasks, graph, reg, box=rec.to_replay_box()))
    assert replay_res.artifacts["e2"]["frontier"].answer == "performance"
