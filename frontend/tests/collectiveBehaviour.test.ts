import assert from "node:assert/strict";
import test from "node:test";

import { collectiveBehaviourLines, collectiveBehaviourViews } from "../src/lib/research.ts";
import type { ResearchCell } from "../src/lib/researchTypes.ts";

function promptView(view: Record<string, unknown>): { role: string; content: string }[] {
  return [
    { role: "system", content: "Answer from the visible evidence." },
    { role: "user", content: JSON.stringify(view) },
  ];
}

function sourceOnlyCell(): ResearchCell {
  const agents = [
    { agent_id: "qwen:worker-1", initial_evidence_ids: ["ev-a"], initial_answer: "maybe", final_answer: "yes", received: [{ sender: "qwen:worker-2", message_id: "msg-b", evidence_ids: ["ev-b"] }] },
    { agent_id: "qwen:worker-2", initial_evidence_ids: ["ev-b"], initial_answer: "no", final_answer: "no", received: [] },
    { agent_id: "qwen:worker-3", initial_evidence_ids: ["ev-c"], initial_answer: "yes", final_answer: "yes", received: [] },
  ];
  return {
    cell_id: "task-1:evidence_sources:qwen",
    task_id: "task-1",
    dataset: "pubmedqa",
    domain: "medical",
    variant: "evidence_sources:qwen",
    protocol: "evidence_sources",
    model_keys: ["qwen"],
    status: "completed",
    answer: "yes",
    correct: null,
    instruction_compliant: true,
    call_count: 6,
    prompt_tokens: 1,
    completion_tokens: 1,
    elapsed_s: 0.1,
    messages: [
      ...agents.map((agent, index) => ({
        message_id: `claim-${index + 1}`,
        task_id: "task-1",
        protocol: "evidence_sources",
        model_key: "qwen",
        role: agent.agent_id,
        kind: "claim" as const,
        round: 0,
        prompt_messages: promptView({
          task: { evidence: [{ id: `ev-${String.fromCharCode(97 + index)}`, text: `Starting passage ${index + 1}.` }] },
          agent_id: agent.agent_id,
          round: 0,
          own_previous: null,
          signals: [],
          instruction: "Share useful sources.",
        }),
        content: JSON.stringify({ answer: agent.initial_answer, evidence_ids: agent.initial_evidence_ids, brief: "Initial finding." }),
        payload: { answer: agent.initial_answer, evidence_ids: agent.initial_evidence_ids, brief: "Initial finding." },
        usage_complete: true,
      })),
      {
        message_id: "revision-1",
        task_id: "task-1",
        protocol: "evidence_sources",
        model_key: "qwen",
        role: "qwen:worker-1",
        kind: "revision",
        round: 1,
        prompt_messages: promptView({
          task: { evidence: [{ id: "ev-a", text: "Starting passage 1." }, { id: "ev-b", text: "Shared passage from worker 2." }] },
          agent_id: "qwen:worker-1",
          round: 1,
          own_previous: { message_id: "claim-1", payload: { answer: "maybe", evidence_ids: ["ev-a"], brief: "Initial finding." } },
          signals: [{
            sender: "qwen:worker-2",
            message_id: "msg-b",
            kind: "finding",
            round: 0,
            expires_round: 1,
            payload: { evidence_ids: ["ev-b"] },
            evidence: [{ id: "ev-b", text: "Shared passage from worker 2." }],
          }],
          instruction: "Reconsider using source passages.",
        }),
        content: JSON.stringify({ answer: "yes", evidence_ids: ["ev-b"], brief: "Revised finding." }),
        payload: { answer: "yes", evidence_ids: ["ev-b"], brief: "Revised finding." },
        parent_ids: ["claim-1", "msg-b"],
        usage_complete: true,
      },
    ],
    cooperation: { mode: "evidence_sources", agents },
    usage_complete: true,
  };
}

test("source-only collective view shows saved passages with human researcher labels", () => {
  const lines = collectiveBehaviourLines([sourceOnlyCell()]);

  assert.ok(lines.some((line) => line.includes("Researcher A")));
  assert.ok(lines.some((line) => line.includes("Starting passage 1.")));
  assert.ok(lines.some((line) => line.includes("Shared passage from worker 2.")));
  assert.ok(lines.some((line) => line.includes("Initial answer: maybe")));
  assert.ok(lines.some((line) => line.includes("Final answer: yes")));
  assert.equal(lines.some((line) => line.includes("Revised finding.")), false, "source-only mode must not display a peer conclusion");
});

test("collective view labels three workers and solo traces without relying on machine IDs", () => {
  const view = collectiveBehaviourViews([sourceOnlyCell()])[0];
  assert.deepEqual(view.agents.map((agent) => agent.label), ["Researcher A", "Researcher B", "Researcher C"]);
  assert.equal(view.agents[0].shared_sources[0].sender, "qwen:worker-2");
  assert.equal(view.agents[0].shared_sources[0].message_id, "msg-b");

  const solo = sourceOnlyCell();
  solo.protocol = "solo_refine";
  solo.variant = "solo_refine:qwen";
  solo.cooperation = { mode: "solo_refine", agents: [solo.cooperation!.agents[0]] };
  assert.equal(collectiveBehaviourViews([solo])[0].agents[0].label, "Solo researcher");
  assert.deepEqual(collectiveBehaviourViews([solo])[0].agents[0].shared_sources, []);
});

test("explicit absent answers cannot be resurrected from invalid raw model text", () => {
  const cell = sourceOnlyCell();
  cell.cooperation!.agents[0].initial_answer = null;
  cell.cooperation!.agents[0].final_answer = null;
  for (const event of cell.messages.filter((e) => e.role === "qwen:worker-1")) {
    event.payload = null;
    event.parse_error = "invalid citation";
    event.content = JSON.stringify({ answer: "yes", evidence_ids: ["foreign"], brief: "invalid" });
  }
  const view = collectiveBehaviourViews([cell])[0];
  assert.equal(view.agents[0].initial_answer, null);
  assert.equal(view.agents[0].final_answer, null);
});

test("collective views identify their question and distinguish findings from sources", () => {
  const cell = sourceOnlyCell();
  const question = "Does the reported intervention help?";
  const initial = JSON.parse(cell.messages[0].prompt_messages[1].content as string);
  initial.task.question = question;
  cell.messages[0].prompt_messages[1].content = JSON.stringify(initial);
  const full = structuredClone(cell);
  full.protocol = "evidence_exchange";
  full.variant = "evidence_exchange:qwen";
  full.cell_id = "task-1:evidence_exchange:qwen";
  full.cooperation!.mode = "evidence_exchange";
  const revision = JSON.parse(full.messages[3].prompt_messages[1].content as string);
  revision.signals[0].payload = { answer: "no", brief: "Only a subgroup benefits.", evidence_ids: ["ev-b"] };
  full.messages[3].prompt_messages[1].content = JSON.stringify(revision);
  const views = collectiveBehaviourViews([cell, full]);
  assert.equal(views[0].task_id, "task-1");
  assert.equal(views[0].question, question);
  assert.notEqual(views[0].cell_id, views[1].cell_id);
  assert.deepEqual(views[0].agents[0].received_findings, []);
  assert.equal(views[1].agents[0].received_findings[0].answer, "no");
  assert.equal(views[1].agents[0].received_findings[0].brief, "Only a subgroup benefits.");
});

test("missing prompt passages stay unavailable and unsafe text remains data", () => {
  const legacy = sourceOnlyCell();
  legacy.messages = [];
  legacy.cooperation!.agents[0].initial_evidence_ids = ["missing-source"];
  const legacyView = collectiveBehaviourViews([legacy])[0];
  assert.equal(legacyView.agents[0].starting_sources[0].text, "Source text unavailable");

  const escaped = sourceOnlyCell();
  escaped.messages[0].prompt_messages[1].content = JSON.stringify({ task: { evidence: [{ id: "ev-a", text: "<script>alert(1)</script>" }] } });
  const lines = collectiveBehaviourLines([escaped]);
  assert.ok(lines.some((line) => line.includes("<script>alert(1)</script>")));
  assert.equal(lines.some((line) => /success|correct|improved/i.test(line)), false);
});