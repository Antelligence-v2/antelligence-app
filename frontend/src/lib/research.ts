import type {
  ResearchCatalog,
  ResearchGate,
  ResearchReport,
  ResearchRunRequest,
  ResearchOutputPolicy,
} from "./researchTypes";

export const DEFAULT_RESEARCH_FORM = {
  name: "Local swarm research check",
  output_policy: "constrained_short_v1" as ResearchOutputPolicy,
  model_keys: [] as string[],
  protocols: [] as string[],
  datasets: [] as string[],
  split: "development" as const,
  tasks_per_dataset: 2,
  temperature: 0.2,
  seed: 17,
  max_tokens: 256,
  target_accuracy: 0.8,
  max_calls: 100,
  max_wall_seconds: 900,
};

export const FALLBACK_PROTOCOL_CALLS: Record<string, number> = {
  single: 1,
  independent_vote: 3,
  peer_review: 3,
  signal_board: 3,
};

export type ResearchForm = typeof DEFAULT_RESEARCH_FORM;

export function estimateResearchCalls(
  tasksPerDataset: number,
  datasetCount: number,
  modelCount: number,
  protocols: Array<{ id: string; calls_per_model?: number } | string>,
): number {
  const callsPerTaskPerModel = protocols.reduce((total, protocol) => {
    const id = typeof protocol === "string" ? protocol : protocol.id;
    return total + (typeof protocol === "string" ? FALLBACK_PROTOCOL_CALLS[id] ?? 0 : protocol.calls_per_model ?? FALLBACK_PROTOCOL_CALLS[id] ?? 0);
  }, 0);
  return tasksPerDataset * datasetCount * modelCount * callsPerTaskPerModel;
}

export function buildResearchRequest(form: ResearchForm): ResearchRunRequest {
  return {
    name: form.name.trim(),
    output_policy: form.output_policy,
    model_keys: [...form.model_keys],
    protocols: [...form.protocols],
    datasets: [...form.datasets],
    split: form.split,
    tasks_per_dataset: form.tasks_per_dataset,
    temperature: form.temperature,
    seed: form.seed,
    max_tokens: form.max_tokens,
    target_accuracy: form.target_accuracy,
    max_calls: form.max_calls,
    max_wall_seconds: form.max_wall_seconds,
  };
}

export function validateResearchRequest(request: ResearchRunRequest, catalog?: ResearchCatalog | null): string[] {
  const errors: string[] = [];
  const policy = request.output_policy ?? "prompt_only";
  if (!["prompt_only", "constrained_short_v1", "source_calculation_v1"].includes(policy)) errors.push(`Unknown output policy: ${policy}.`);
  else if (policy !== "prompt_only" && catalog && !catalog.output_policies?.some((entry) => entry.id === policy)) errors.push(`Output policy ${policy} is not supported by this backend.`);
  if (!request.name.trim()) errors.push("Name is required.");
  if (request.model_keys.length < 1 || request.model_keys.length > 2) errors.push("Select 1–2 models.");
  if (request.protocols.length < 1 || request.protocols.length > 4) errors.push("Select 1–4 protocols.");
  if (request.datasets.length < 1 || request.datasets.length > 2) errors.push("Select 1–2 datasets.");
  if (!Number.isInteger(request.tasks_per_dataset) || request.tasks_per_dataset < 1) errors.push("Tasks per dataset must be a positive integer.");
  if (catalog && request.tasks_per_dataset > catalog.limits.max_tasks_per_dataset) errors.push(`Tasks per dataset cannot exceed ${catalog.limits.max_tasks_per_dataset}.`);
  if (!Number.isFinite(request.temperature) || request.temperature < 0 || request.temperature > 1) errors.push("Temperature must be between 0 and 1.");
  if (!Number.isInteger(request.seed) || request.seed < 0 || request.seed > 2147483647) errors.push("Seed must be an integer from 0 to 2147483647.");
  if (!Number.isInteger(request.max_tokens) || request.max_tokens < 64 || request.max_tokens > 512) errors.push("Max tokens must be an integer from 64 to 512.");
  if (!Number.isFinite(request.target_accuracy) || request.target_accuracy < 0 || request.target_accuracy > 1) errors.push("Target accuracy must be between 0 and 1.");
  if (!Number.isInteger(request.max_calls) || request.max_calls < 1) errors.push("Max calls must be a positive integer.");
  if (catalog && request.max_calls > catalog.limits.max_calls) errors.push(`Max calls cannot exceed ${catalog.limits.max_calls}.`);
  if (!Number.isInteger(request.max_wall_seconds) || request.max_wall_seconds < 1) errors.push("Max wall seconds must be a positive integer.");
  if (catalog && request.max_wall_seconds > catalog.limits.max_wall_seconds) errors.push(`Max wall seconds cannot exceed ${catalog.limits.max_wall_seconds}.`);

  const requestedCalls = estimateResearchCalls(request.tasks_per_dataset, request.datasets.length, request.model_keys.length, request.protocols.map((id) => catalog?.protocols.find((protocol) => protocol.id === id) ?? id));
  if (requestedCalls > request.max_calls) errors.push(`Calculated budget is ${requestedCalls} calls, above the ${request.max_calls}-call cap.`);
  if (catalog) {
    const knownModels = new Map(catalog.models.map((model) => [model.key, model]));
    for (const key of request.model_keys) {
      const model = knownModels.get(key);
      if (!model) errors.push(`Unknown model: ${key}.`);
      else if (model.availability !== "ready") errors.push(`${model.label} is not ready: ${model.reason || "availability is unknown"}.`);
    }
    const knownProtocols = new Set(catalog.protocols.map((protocol) => protocol.id));
    for (const protocol of request.protocols) if (!knownProtocols.has(protocol)) errors.push(`Unknown protocol: ${protocol}.`);
    const knownDatasets = new Set(catalog.datasets.map((dataset) => dataset.key));
    for (const dataset of request.datasets) if (!knownDatasets.has(dataset)) errors.push(`Unknown dataset: ${dataset}.`);
  }
  return errors;
}

export function formatResearchPercent(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function formatResearchNumber(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

export function gateLabel(gate: string | undefined): string {
  return (gate || "unknown").split("_").join(" ");
}

export function gateClass(gate: string | undefined): string {
  switch (gate) {
    case "meets_sample_target": return "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200";
    case "below_target": return "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200";
    case "insufficient_evidence": return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200";
    default: return "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200";
  }
}

function formulaSafe(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  if (typeof value === "boolean") return value ? "true" : "false";
  let text = String(value);
  let index = 0;
  while (index < text.length && (text.charCodeAt(index) <= 32 || /\s/.test(text[index]))) index++;
  if (/^[=+\-@]/.test(text.slice(index))) text = `'${text}`;
  return text;
}

function csvCell(value: unknown): string {
  const text = formulaSafe(value);
  return /[",\n\r]/.test(text) ? `"${text.split('"').join('""')}"` : text;
}

export function researchToJson(report: ResearchReport): string {
  return `${JSON.stringify(report, null, 2)}\n`;
}

export function researchToCsv(report: ResearchReport): string {
  const headers = [
    "row_type", "run_id", "name", "status", "domain", "dataset", "variant", "protocol", "model_keys",
    "task_count", "completed_count", "correct_count", "error_count", "abstained_count", "invalid_count", "coverage",
    "task_success_rate", "answered_accuracy", "wilson_lower_95", "gate", "target_accuracy", "min_cases", "call_count",
    "prompt_tokens", "completion_tokens", "elapsed_s", "cell_id", "task_id", "answer", "correct", "instruction_compliant",
    "usage_complete", "message_id", "model_key", "requested_model", "served_model", "role", "kind", "round", "recipient",
    "parent_ids", "response_id", "request_hash", "finish_reason", "prompt_messages", "content", "error", "limitations", "output_policy", "response_format", "payload",
  ];
  const rows: unknown[][] = [headers];
  const add = (row: Record<string, unknown>) => {
    const full = { run_id: report.run_id, name: report.name, status: report.status, output_policy: report.request.output_policy ?? "prompt_only", ...row };
    rows.push(headers.map((key) => (full as Record<string, unknown>)[key]));
  };
  for (const row of report.summary || []) add({ ...row, row_type: "summary", model_keys: row.model_keys.join(" | ") });
  for (const cell of report.cells || []) add({ ...cell, row_type: "cell", status: report.status, model_keys: cell.model_keys.join(" | ") });
  for (const event of report.events || []) add({ ...event, row_type: "event", parent_ids: (event.parent_ids || []).join(" | "), prompt_messages: JSON.stringify(event.prompt_messages || []), response_format: JSON.stringify(event.response_format ?? null), payload: JSON.stringify(event.payload ?? null) });
  for (const error of report.errors || []) add({ row_type: "error", error });
  for (const limitation of report.limitations || []) add({ row_type: "limitation", limitations: limitation });
  return rows.map((row) => row.map(csvCell).join(",")).join("\n") + "\n";
}

export function sourceCalculationLines(payload: unknown): string[] {
  if (!payload || typeof payload !== "object" || !("calculation" in payload)) return [];
  const calculation = payload.calculation;
  if (!calculation || typeof calculation !== "object" || !("operation" in calculation) || !("operands" in calculation) || !("result" in calculation)) return [];
  if (typeof calculation.operation !== "string" || !Array.isArray(calculation.operands) || !(calculation.result === null || typeof calculation.result === "string")) return [];
  const operands: string[] = [];
  for (const [index, operand] of calculation.operands.entries()) {
    if (!operand || typeof operand !== "object" || typeof operand.evidence_id !== "string" || typeof operand.quote !== "string" || typeof operand.value !== "string") return [];
    operands.push(`Operand ${index + 1}: ${operand.evidence_id} · ${JSON.stringify(operand.quote)} → ${operand.value}`);
  }
  const limitations = "limitations" in calculation && Array.isArray(calculation.limitations) ? calculation.limitations.filter((value): value is string => typeof value === "string") : [];
  return [`Operation: ${calculation.operation}`, ...operands, `Stored result: ${calculation.result ?? "abstained"}`, ...limitations];
}

export function isTerminalResearchStatus(status: string): boolean {
  return ["completed", "partial", "failed", "interrupted"].includes(status);
}

export function isResearchReport(value: unknown): value is ResearchReport {
  const report = value as ResearchReport | null;
  return Boolean(report && typeof report.run_id === "string" && typeof report.status === "string" && Array.isArray(report.cells) && Array.isArray(report.summary) && Array.isArray(report.events));
}

export function isResearchCatalog(value: unknown): value is ResearchCatalog {
  const catalog = value as ResearchCatalog | null;
  return Boolean(catalog && Array.isArray(catalog.models) && Array.isArray(catalog.datasets) && Array.isArray(catalog.protocols) && catalog.limits);
}

export const RESEARCH_GATES: ResearchGate[] = ["unknown", "insufficient_evidence", "below_target", "meets_sample_target"];
