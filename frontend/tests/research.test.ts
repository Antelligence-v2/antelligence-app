import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_RESEARCH_FORM,
  buildResearchRequest,
  estimateResearchCalls,
  researchToCsv,
  researchToJson,
  validateResearchRequest,
} from "../src/lib/research.ts";
import type { ResearchCatalog, ResearchReport } from "../src/lib/researchTypes.ts";

const catalog: ResearchCatalog = {
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

test("request builder preserves explicit bounded settings", () => {
  const request = buildResearchRequest({ ...DEFAULT_RESEARCH_FORM, name: "  check  ", model_keys: ["model-a"], protocols: ["single"], datasets: ["finqa"] });
  assert.equal(request.name, "check");
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

test("JSON export is the complete saved report", () => {
  assert.deepEqual(JSON.parse(researchToJson(report)), report);
});
