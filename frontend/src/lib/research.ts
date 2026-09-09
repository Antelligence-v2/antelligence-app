import type {
  ResearchCatalog,
  ResearchGate,
  ResearchReport,
  ResearchRunRequest,
  ResearchOutputPolicy,
  ResearchCell,
  ResearchEvidence,
  ResearchEvent,
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
  evidence_exchange: 6,
  evidence_isolated: 6,
  solo_refine: 6,
  evidence_sources: 6,
  fallback: 6,
};

export const DEFAULT_RESEARCH_PROTOCOLS = ["single", "independent_vote", "peer_review", "signal_board"] as const;

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
  if (request.protocols.length < 1 || request.protocols.length > 8) errors.push("Select 1–8 protocols.");
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

export function researchUsage(report: ResearchReport) {
  const accounting = report.call_accounting;
  if (accounting?.mode === "shared_initial_fork_v1") {
    const complete = accounting.usage_complete && accounting.fresh_calls === report.actual_calls && accounting.logical_steps === report.events.length && accounting.fresh_calls + accounting.reused_initial_steps === accounting.logical_steps;
    const measured = (value: number | null) => complete && value !== null && Number.isFinite(value) && value >= 0 ? value : null;
    return { prompt_tokens: measured(accounting.physical_prompt_tokens), completion_tokens: measured(accounting.physical_completion_tokens), elapsed_s: measured(accounting.physical_elapsed_s), complete,
      note: `${accounting.fresh_calls} fresh API calls; ${accounting.logical_steps} logical steps include ${accounting.reused_initial_steps} reused initial steps. Per-condition rows allocate the common starting findings to each condition; these totals count real requests once.` };
  }
  const complete = report.summary.length > 0 && report.summary.every((row) => row.usage_complete);
  return { prompt_tokens: complete ? report.summary.reduce((sum, row) => sum + row.prompt_tokens, 0) : null,
    completion_tokens: complete ? report.summary.reduce((sum, row) => sum + row.completion_tokens, 0) : null,
    elapsed_s: complete ? report.summary.reduce((sum, row) => sum + row.elapsed_s, 0) : null, complete,
    note: "Recorded physical usage. Missing usage stays unknown, not zero." };
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
    "parent_ids", "response_id", "request_hash", "finish_reason", "prompt_messages", "content", "error", "limitations", "output_policy", "response_format", "payload", "inference_provenance", "call_accounting",
  ];
  const rows: unknown[][] = [headers];
  const add = (row: Record<string, unknown>) => {
    const full = { run_id: report.run_id, name: report.name, status: report.status, output_policy: report.request.output_policy ?? "prompt_only", ...row };
    rows.push(headers.map((key) => (full as Record<string, unknown>)[key]));
  };
  if (report.call_accounting) add({ row_type: "accounting", call_accounting: JSON.stringify(report.call_accounting) });
  for (const row of report.summary || []) add({ ...row, row_type: "summary", model_keys: row.model_keys.join(" | ") });
  for (const cell of report.cells || []) add({ ...cell, row_type: "cell", status: report.status, model_keys: cell.model_keys.join(" | ") });
  for (const event of report.events || []) add({ ...event, row_type: "event", parent_ids: (event.parent_ids || []).join(" | "), prompt_messages: JSON.stringify(event.prompt_messages || []), response_format: JSON.stringify(event.response_format ?? null), payload: JSON.stringify(event.payload ?? null), inference_provenance: JSON.stringify(event.inference_provenance ?? null) });
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

export interface CollectiveBehaviourSource {
  id: string;
  text: string;
  sender?: string;
  message_id?: string;
}

export interface CollectiveBehaviourAgentView {
  label: string;
  agent_id: string;
  initial_evidence_ids: string[];
  starting_sources: CollectiveBehaviourSource[];
  shared_sources: CollectiveBehaviourSource[];
  received_findings: { sender: string; answer: string | null; brief: string }[];
  initial_answer: string | null;
  final_answer: string | null;
}

export interface CollectiveBehaviourView {
  cell_id: string;
  task_id: string;
  question: string;
  variant: string;
  protocol: string;
  mode_label: string;
  source_only: boolean;
  agents: CollectiveBehaviourAgentView[];
}

const COLLECTIVE_BEHAVIOUR_PROTOCOLS = new Set(["evidence_exchange", "evidence_isolated", "solo_refine", "evidence_sources"]);
const SOURCE_TEXT_UNAVAILABLE = "Source text unavailable";

function record(value: unknown): Record<string, any> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, any> : null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function promptRecord(event: ResearchEvent | null | undefined): Record<string, any> | null {
  const messages = Array.isArray(event?.prompt_messages) ? event.prompt_messages : [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const content = messages[index]?.content;
    if (typeof content === "string") {
      try {
        const parsed = JSON.parse(content);
        const parsedRecord = record(parsed);
        if (parsedRecord) return parsedRecord;
      } catch {
        // Legacy traces can contain non-JSON prompts; their IDs still remain useful.
      }
    } else {
      const parsedRecord = record(content);
      if (parsedRecord) return parsedRecord;
    }
  }
  return null;
}

function evidenceRecord(value: unknown, fallbackId?: string, metadata?: Pick<CollectiveBehaviourSource, "sender" | "message_id">): CollectiveBehaviourSource | null {
  const source = record(value);
  const id = typeof source?.id === "string" ? source.id : fallbackId;
  if (!id) return null;
  const text = typeof source?.text === "string" && source.text.length > 0 ? source.text : SOURCE_TEXT_UNAVAILABLE;
  return { id, text, ...metadata };
}

function sourcesForIds(evidence: unknown, ids: string[], metadata?: Pick<CollectiveBehaviourSource, "sender" | "message_id">): CollectiveBehaviourSource[] {
  const entries = Array.isArray(evidence) ? evidence : [];
  const byId = new Map<string, CollectiveBehaviourSource>();
  for (const entry of entries) {
    const source = evidenceRecord(entry, undefined, metadata);
    if (source) byId.set(source.id, source);
  }
  return ids.map((id) => byId.get(id) || evidenceRecord(undefined, id, metadata)!).filter(Boolean);
}

function dedupeSources(sources: CollectiveBehaviourSource[]): CollectiveBehaviourSource[] {
  const seen = new Set<string>();
  return sources.filter((source) => {
    const key = `${source.sender || ""}\u0000${source.message_id || ""}\u0000${source.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function answerFromEvent(event: ResearchEvent | null | undefined): string | null {
  if (event?.parse_error || event?.error) return null;
  const payload = record(event?.payload);
  return typeof payload?.answer === "string" ? payload.answer : null;
}

function agentLabel(protocol: string, index: number): string {
  if (protocol === "solo_refine") return "Solo researcher";
  return `Researcher ${String.fromCharCode(65 + index)}`;
}

function modeLabel(protocol: string): string {
  switch (protocol) {
    case "evidence_exchange": return "Sources and peer conclusions shared";
    case "evidence_sources": return "Sources shared; peer conclusions hidden";
    case "evidence_isolated": return "Sources kept separate";
    case "solo_refine": return "One researcher with all sources";
    default: return "Collective trace";
  }
}

function collectiveEvents(cell: ResearchCell): ResearchEvent[] {
  return Array.isArray(cell.messages) ? cell.messages : [];
}

function sourceOnlySharedSources(events: ResearchEvent[], agent: { received?: { sender: string; message_id: string; evidence_ids: string[]; evidence?: ResearchEvidence[] }[] }): CollectiveBehaviourSource[] {
  const sources: CollectiveBehaviourSource[] = [];
  for (const event of events) {
    if (event.kind !== "revision") continue;
    const prompt = promptRecord(event);
    const signals = Array.isArray(prompt?.signals) ? prompt.signals : [];
    for (const signalValue of signals) {
      const signal = record(signalValue);
      if (!signal) continue;
      const sender = typeof signal.sender === "string" ? signal.sender : undefined;
      const messageId = typeof signal.message_id === "string" ? signal.message_id : undefined;
      const payload = record(signal.payload);
      const ids = strings(payload?.evidence_ids);
      const evidence = Array.isArray(signal.evidence) ? signal.evidence : [];
      for (const source of sourcesForIds(evidence, ids, { sender, message_id: messageId })) sources.push(source);
    }
  }
  if (sources.length === 0) {
    for (const received of agent.received || []) {
      for (const source of sourcesForIds(received.evidence, strings(received.evidence_ids), { sender: received.sender, message_id: received.message_id })) sources.push(source);
    }
  }
  return dedupeSources(sources);
}

export function collectiveBehaviourViews(cells: ResearchCell[]): CollectiveBehaviourView[] {
  const views: CollectiveBehaviourView[] = [];
  for (const cell of cells || []) {
    const cooperation = cell.cooperation;
    const protocol = typeof cell.protocol === "string" ? cell.protocol : cooperation?.mode;
    if (!cooperation || !protocol || !COLLECTIVE_BEHAVIOUR_PROTOCOLS.has(protocol)) continue;
    const events = collectiveEvents(cell);
    const agents = Array.isArray(cooperation.agents) ? cooperation.agents : [];
    const task = record(promptRecord(events[0])?.task);
    views.push({
      cell_id: cell.cell_id,
      task_id: cell.task_id,
      question: typeof task?.question === "string" ? task.question : "Question text unavailable",
      variant: typeof cell.variant === "string" ? cell.variant : protocol,
      protocol,
      mode_label: modeLabel(protocol),
      source_only: protocol === "evidence_sources",
      agents: agents.map((agent, index) => {
        const agentEvents = events.filter((event) => event.role === agent.agent_id);
        const initialEvent = agentEvents.find((event) => event.round === 0 && event.kind === "claim") || agentEvents.find((event) => event.round === 0) || null;
        const revisionEvents = agentEvents.filter((event) => event.kind === "revision" || event.round > 0);
        const finalEvent = revisionEvents[revisionEvents.length - 1] || initialEvent;
        const initialPrompt = promptRecord(initialEvent);
        const startingEvidence = initialPrompt?.task && record(initialPrompt.task) ? (initialPrompt.task as Record<string, any>).evidence : undefined;
        const initialIds = strings(agent.initial_evidence_ids);
        const startingSources = sourcesForIds(startingEvidence, initialIds);
        const initialAnswer = agent.initial_answer === null || typeof agent.initial_answer === "string" ? agent.initial_answer : answerFromEvent(initialEvent);
        const finalAnswer = agent.final_answer === null || typeof agent.final_answer === "string" ? agent.final_answer : answerFromEvent(finalEvent);
        return {
          label: agentLabel(protocol, index),
          agent_id: agent.agent_id,
          initial_evidence_ids: initialIds,
          starting_sources: startingSources,
          shared_sources: protocol === "solo_refine" || protocol === "evidence_isolated" ? [] : sourceOnlySharedSources(agentEvents, agent),
          received_findings: protocol !== "evidence_exchange" ? [] : revisionEvents.flatMap((event) => {
            const signals = promptRecord(event)?.signals;
            return !Array.isArray(signals) ? [] : signals.flatMap((value) => {
              const signal = record(value);
              const finding = record(signal?.payload);
              if (!finding || typeof signal?.sender !== "string") return [];
              return [{ sender: signal.sender, answer: typeof finding.answer === "string" ? finding.answer : null, brief: typeof finding.brief === "string" ? finding.brief : "Finding text unavailable" }];
            });
          }),
          initial_answer: initialAnswer,
          final_answer: finalAnswer,
        };
      }),
    });
  }
  return views;
}

function hasReadablePromptTrace(cells: ResearchCell[]): boolean {
  return (cells || []).some((cell) => collectiveEvents(cell).some((event) => promptRecord(event) !== null));
}

export function collectiveBehaviourLines(cells: ResearchCell[]): string[] {
  // Preserve the compact projection used by old saved reports with no prompt trace.
  // Newer reports use the source-text projection below, while the structured view
  // remains the UI source of truth in both cases.
  if (!hasReadablePromptTrace(cells)) {
    const lines: string[] = [];
    for (const cell of cells) {
      const protocol = typeof cell.protocol === "string" ? cell.protocol : cell.cooperation?.mode;
      if (!cell.cooperation || !protocol || !COLLECTIVE_BEHAVIOUR_PROTOCOLS.has(protocol)) continue;
      const mode = cell.cooperation.mode === "evidence_exchange" ? "Sharing on" : cell.cooperation.mode === "solo_refine" ? "Solo full evidence" : cell.cooperation.mode === "evidence_isolated" ? "Sharing off" : cell.cooperation.mode === "evidence_sources" ? "Sources only" : "Unknown";
      lines.push(`Variant ${cell.variant}`, `Mode: ${mode}`);
      for (const agent of cell.cooperation.agents || []) {
        lines.push(`Agent ${agent.agent_id} knowledge IDs: ${agent.initial_evidence_ids.join(", ") || "none"}`);
        const received = (agent.received || []).flatMap((item) => item.evidence_ids.map((evidenceId) => `${evidenceId} (from ${item.sender})`));
        if (received.length > 0) lines.push(`Shared source IDs: ${received.join(", ")}`);
        const initial = agent.initial_answer ?? "—";
        const final = agent.final_answer ?? "—";
        lines.push(`Answer: ${initial} → ${final}`);
        if (agent.initial_answer !== agent.final_answer) lines.push("Changed answer; this is not necessarily an improvement.");
      }
    }
    return lines;
  }

  return collectiveBehaviourViews(cells).flatMap((view) => [
    `Variant ${view.variant}`,
    `Mode: ${view.mode_label}`,
    ...view.agents.flatMap((agent) => [
      agent.label,
      ...(agent.starting_sources.length > 0 ? agent.starting_sources.map((source) => `Starting source text: ${source.text}`) : ["Starting source text: Source text unavailable"]),
      ...(agent.shared_sources.length > 0 ? agent.shared_sources.map((source) => `Shared source text: ${source.text}`) : []),
      `Initial answer: ${agent.initial_answer ?? "Answer unavailable"}`,
      `Final answer: ${agent.final_answer ?? "Answer unavailable"}`,
    ]),
  ]);
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
