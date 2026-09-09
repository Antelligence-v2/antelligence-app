import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_RESEARCH_FORM,
  buildResearchRequest,
  collectiveBehaviourLines,
  estimateResearchCalls,
  researchToCsv,
  researchToJson,
  validateResearchRequest,
} from "../src/lib/research.ts";
import type { ResearchCatalog, ResearchReport } from "../src/lib/researchTypes.ts";

const catalog: ResearchCatalog = {
  output_policies: [
    { id: "prompt_only", label: "Prompt-only baseline", description: "Original behavior" },
    { id: "constrained_short_v1", label: "Constrained short JSON", description: "Explicit repair" },
  ],
  models: [
    { key: "model-a", label: "Model A", model_id: "local/a", endpoint: "http://127.0.0.1:8090", availability: "ready", local: true },
    { key: "model-b", label: "Model B", model_id: "local/b", endpoint: "http://127.0.0.1:8092", availability: "ready", local: true },
  ],
  datasets: [
    { key: "pubmedqa", label: "PubMedQA", domain: "medical", source_url: "https://example.test/pubmedqa", license: "public", revision: "r1", source_sha256: "sha", development_count: 2, evaluation_count: 2, limitations: [] },
    { key: "finqa", label: "FinQA", domain: "finance", source_url: "https://example.test/finqa", license: "public", revision: "r1", source_sha256: "sha", development_count: 2, evaluation_count: 2, limitations: [] },
  ],
  protocols: [
    { id: "single", label: "Single", description: "", calls_per_model: 1 },
    { id: "independent_vote", label: "Independent vote", description: "", calls_per_model: 3 },
    { id: "peer_review", label: "Peer review", description: "", calls_per_model: 3 },
    { id: "signal_board", label: "Signal board", description: "", calls_per_model: 3 },
  ],
  limits: { max_calls: 600, max_wall_seconds: 3600, max_tasks_per_dataset: 50 },
  limitations: [],
};

const report = {
  run_id: "run-1",
  name: "=unsafe",
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:01Z",
  status: "completed",
  request: buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, model_keys: ["model-a", "model-b"], protocols: ["single"], datasets: ["finqa"] }),
  request_hash: "hash",
  dataset_manifest: [],
  models: [],
  selected_task_ids: [],
  total_cells: 1,
  completed_cells: 1,
  estimated_calls: 2,
  actual_calls: 2,
  cells: [{ cell_id: "cell-1", task_id: "task-1", dataset: "finqa", domain: "finance", variant: "single:model-a", protocol: "single", model_keys: ["model-a"], status: "completed", answer: "-2", correct: true, instruction_compliant: true, call_count: 1, prompt_tokens: 10, completion_tokens: 5, elapsed_s: 0.2, messages: [], usage_complete: true, error: null }],
  summary: [{ domain: "finance", variant: "single:model-a", protocol: "single", model_keys: ["model-a"], task_count: 1, completed_count: 1, correct_count: 1, error_count: 0, abstained_count: 0, invalid_count: 0, coverage: 1, task_success_rate: 1, answered_accuracy: 1, wilson_lower_95: 0.2, gate: "insufficient_evidence", target_accuracy: 0.8, min_cases: 30, call_count: 1, prompt_tokens: 10, completion_tokens: 5, elapsed_s: 0.2, usage_complete: true }],
  events: [],
  errors: [],
  limitations: ["Public benchmark may be model-seen."],
  metered_api_cost_usd: 0,
  proof_ok: false,
} as unknown as ResearchReport;

test("the default four-protocol two-domain budget is 80 calls", () => {
  assert.equal(estimateResearchCalls(2, 2, 2, catalog.protocols), 80);
});

test("new collective protocols and fallback use six calls per model", () => {
  assert.equal(estimateResearchCalls(1, 1, 1, ["evidence_exchange", "evidence_isolated", "solo_refine", "fallback"]), 24);
  const request = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, model_keys: ["model-a"], protocols: ["single", "independent_vote", "peer_review", "signal_board", "evidence_exchange", "evidence_isolated", "solo_refine"], datasets: ["finqa"] });
  const collectiveCatalog = { ...catalog, protocols: [...catalog.protocols, { id: "evidence_exchange", label: "Evidence exchange", description: "", calls_per_model: 6 }, { id: "evidence_isolated", label: "Evidence isolated", description: "", calls_per_model: 6 }, { id: "solo_refine", label: "Solo refine", description: "", calls_per_model: 6 }] };
  assert.deepEqual(validateResearchRequest(request, collectiveCatalog), []);
});
test("request builder preserves explicit bounded settings", () => {
  const request = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, name: "  check  ", model_keys: ["model-a"], protocols: ["single"], datasets: ["finqa"] });
  assert.equal(request.name, "check");
  assert.equal(request.output_policy, "constrained_short_v1");
  const baseline = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, output_policy: "prompt_only" });
  assert.equal(baseline.output_policy, "prompt_only");
  assert.equal(request.max_calls, 100);
  assert.equal(request.tasks_per_dataset, 2);
  assert.deepEqual(validateResearchRequest(request, catalog), []);
});

test("unknown model availability blocks a start instead of silently falling back", () => {
  const request = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, model_keys: ["model-a", "model-b"], protocols: ["single"], datasets: ["finqa"] });
  const unknownCatalog = { ...catalog, models: catalog.models.map((model) => model.key === "model-b" ? { ...model, availability: "unknown" as const, reason: "not probed" } : model) };
  assert.match(validateResearchRequest(request, unknownCatalog).join("\n"), /not ready/);
});

test("CSV formula safety does not turn numeric negatives into text", () => {
  const csv = researchToCsv({ ...report, cells: [{ ...report.cells[0], elapsed_s: -2 }] });
  assert.match(csv, /cell,run-1,'=unsafe/);
  assert.match(csv, /,10,5,-2,cell-1,task-1/);
  assert.match(csv, /,'-2,true,true,true/);
  assert.match(csv, /Public benchmark may be model-seen/);
});

test("CSV rows align with headers, including errors and limitations", () => {
  const csv = researchToCsv({ ...report, errors: ["transport failure"] });
  const lines = csv.trim().split("\n");
  const headers = lines[0].split(",");
  for (const line of lines.slice(1)) assert.equal(line.split(",").length, headers.length);
  const limitation = lines.find((line) => line.startsWith("limitation,"))!.split(",");
  assert.equal(limitation[headers.indexOf("limitations")], report.limitations[0]);
});

test("unsupported output policy is rejected rather than silently downgraded", () => {
  const request = report.request;
  assert.match(validateResearchRequest(request, { ...catalog, output_policies: undefined }).join("\n"), /Output policy.*not supported/);
  assert.deepEqual(validateResearchRequest({ ...request, output_policy: "prompt_only" }, { ...catalog, output_policies: undefined }), []);
});

test("CSV attributes the selected policy and preserves legacy reports", () => {
  const csv = researchToCsv(report).trim().split("\n");
  const headers = csv[0].split(",");
  assert.ok(headers.includes("output_policy"));
  assert.ok(headers.includes("response_format"));
  for (const line of csv.slice(1)) assert.equal(line.split(",")[headers.indexOf("output_policy")], "constrained_short_v1");
  const legacy = { ...report, request: { ...report.request } };
  delete legacy.request.output_policy;
  const legacyBefore = JSON.stringify(legacy);
  const oldCsv = researchToCsv(legacy).trim().split("\n");
  for (const line of oldCsv.slice(1)) assert.equal(line.split(",")[headers.indexOf("output_policy")], "prompt_only");
  assert.equal(JSON.stringify(legacy), legacyBefore);
});

test("source-backed arithmetic is opt-in and requires backend admission", () => {
  const request = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, output_policy: "source_calculation_v1", model_keys: ["model-a"], protocols: ["single"], datasets: ["finqa"] });
  const capableCatalog = { ...catalog, output_policies: [...catalog.output_policies!, { id: "source_calculation_v1" as const, label: "Source-backed arithmetic", description: "Experimental" }] };
  assert.equal(DEFAULT_RESEARCH_FORM.output_policy, "constrained_short_v1");
  assert.equal(request.output_policy, "source_calculation_v1");
  assert.deepEqual(validateResearchRequest(request, capableCatalog), []);
  assert.match(validateResearchRequest(request, catalog).join("\n"), /not supported/);
});

test("calculation exports retain the complete computed payload alongside the raw plan", () => {
  const payload = { answer: "-20.00", evidence_ids: ["table_1"], brief: "Change", calculation: { operation: "percent_change", operands: [{ evidence_id: "table_1", quote: "80", value: "80" }, { evidence_id: "table_1", quote: "100", value: "100" }], result: "-20.00", limitations: ["Source relevance is not verified."] } };
  const event = { message_id: "msg-1", task_id: "task-1", protocol: "single", model_key: "model-a", role: "solver", kind: "claim", round: 0, prompt_messages: [], content: '{"operation":"percent_change"}', payload, usage_complete: true };
  const measured = { ...report, events: [event] };
  const csv = researchToCsv(measured);
  assert.ok(csv.split("\n")[0].split(",").includes("payload"));
  assert.ok(csv.includes(JSON.stringify(payload).split('"').join('""')));
  assert.deepEqual(JSON.parse(researchToJson(measured)).events[0].payload, payload);
});

test("JSON export is the complete saved report", () => {
  assert.deepEqual(JSON.parse(researchToJson(report)), report);
});

test("collective behaviour lines explain sharing, provenance, and answer changes", () => {
  const lines = collectiveBehaviourLines([{
    cell_id: "cell-collective",
    task_id: "task-1",
    dataset: "finqa",
    domain: "finance",
    variant: "evidence_exchange:model-a",
    protocol: "evidence_exchange",
    model_keys: ["model-a"],
    status: "completed",
    answer: "final answer",
    correct: null,
    instruction_compliant: true,
    call_count: 6,
    prompt_tokens: 1,
    completion_tokens: 1,
    elapsed_s: 0.1,
    messages: [],
    usage_complete: true,
    cooperation: {
      mode: "evidence_exchange",
      agents: [{ agent_id: "agent-a", initial_evidence_ids: ["ev-1"], initial_answer: "initial answer", final_answer: "final answer", received: [{ sender: "agent-b", message_id: "msg-2", evidence_ids: ["ev-2"] }] }],
    },
  }]);
  assert.deepEqual(lines, [
    "Variant evidence_exchange:model-a",
    "Mode: Sharing on",
    "Agent agent-a knowledge IDs: ev-1",
    "Shared source IDs: ev-2 (from agent-b)",
    "Answer: initial answer → final answer",
    "Changed answer; this is not necessarily an improvement.",
  ]);
});

test("collective behaviour labels isolated and solo modes", () => {
  assert.deepEqual(collectiveBehaviourLines([
    { variant: "evidence_isolated:model-a", protocol: "evidence_isolated", cooperation: { mode: "evidence_isolated", agents: [] } },
    { variant: "solo_refine:model-a", protocol: "solo_refine", cooperation: { mode: "solo_refine", agents: [] } },
  ] as any), [
    "Variant evidence_isolated:model-a",
    "Mode: Sharing off",
    "Variant solo_refine:model-a",
    "Mode: Solo full evidence",
  ]);
});
