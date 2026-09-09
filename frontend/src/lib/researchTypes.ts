export type ResearchAvailability = "ready" | "unknown";
export type ResearchStatus = "running" | "completed" | "partial" | "failed" | "interrupted";
export type ResearchGate = "unknown" | "insufficient_evidence" | "below_target" | "meets_sample_target";

export interface ResearchModel {
  key: string;
  label: string;
  model_id: string;
  endpoint: string;
  availability: ResearchAvailability;
  reason?: string | null;
  provenance?: string | null;
  local: boolean;
}

export interface ResearchDataset {
  key: string;
  label: string;
  domain: "medical" | "finance" | string;
  source_url: string;
  license: string;
  revision: string;
  source_sha256: string;
  development_count: number;
  evaluation_count: number;
  limitations: string[];
}

export interface ResearchProtocol {
  id: string;
  label: string;
  description: string;
  calls_per_model: number;
}

export interface ResearchCatalog {
  output_policies?: { id: ResearchOutputPolicy; label: string; description: string }[];
  models: ResearchModel[];
  datasets: ResearchDataset[];
  protocols: ResearchProtocol[];
  limits: {
    max_calls: number;
    max_wall_seconds: number;
    max_tasks_per_dataset: number;
  };
  limitations: string[];
}

export type ResearchOutputPolicy = "prompt_only" | "constrained_short_v1" | "source_calculation_v1";

export interface ResearchRunRequest {
  output_policy?: ResearchOutputPolicy;
  name: string;
  model_keys: string[];
  protocols: string[];
  datasets: string[];
  split: "development" | "evaluation";
  tasks_per_dataset: number;
  temperature: number;
  seed: number;
  max_tokens: number;
  target_accuracy: number;
  max_calls: number;
  max_wall_seconds: number;
}

export interface ResearchLibraryEntry {
  run_id: string;
  name: string;
  created_at: string;
  status: ResearchStatus;
  completed_cells: number;
  total_cells: number;
}

export interface ResearchMessage {
  role?: string;
  content?: string;
  [key: string]: unknown;
}

export interface ResearchEvent {
  message_id: string;
  task_id: string;
  protocol: string;
  model_key: string;
  requested_model?: string;
  served_model?: string;
  role: string;
  kind: "claim" | "critique" | "revision" | string;
  round: number;
  recipient?: string | null;
  parent_ids?: string[];
  expires_round?: number | null;
  prompt_messages: ResearchMessage[];
  content: string;
  payload?: unknown;
  parse_error?: string | null;
  response_id?: string | null;
  request_hash?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  usage_complete: boolean;
  elapsed_s?: number | null;
  finish_reason?: string | null;
  error?: string | null;
  [key: string]: unknown;
}

export interface ResearchReceivedEvidence {
  sender: string;
  message_id: string;
  evidence_ids: string[];
}

export interface ResearchCooperationAgent {
  agent_id: string;
  initial_evidence_ids: string[];
  initial_answer: string | null;
  final_answer: string | null;
  received: ResearchReceivedEvidence[];
}

export interface ResearchCooperation {
  mode: string;
  agents: ResearchCooperationAgent[];
}

export interface ResearchCell {
  cell_id: string;
  task_id: string;
  dataset: string;
  domain: string;
  variant: string;
  protocol: string;
  model_keys: string[];
  status: "completed" | "error" | "abstained" | "invalid" | string;
  answer: string | null;
  expected_answer?: string | null;
  correct: boolean | null;
  instruction_compliant: boolean;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  elapsed_s: number;
  messages: ResearchEvent[];
  cooperation?: ResearchCooperation;
  error?: string | null;
  usage_complete: boolean;
  [key: string]: unknown;
}

export interface ResearchSummaryRow {
  domain: string;
  variant: string;
  protocol: string;
  model_keys: string[];
  task_count: number;
  completed_count: number;
  correct_count: number;
  error_count: number;
  abstained_count: number;
  invalid_count: number;
  coverage: number;
  task_success_rate: number;
  answered_accuracy: number | null;
  wilson_lower_95: number | null;
  gate: ResearchGate | string;
  target_accuracy: number;
  min_cases: number;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  elapsed_s: number;
  usage_complete: boolean;
  [key: string]: unknown;
}

export interface ResearchReport {
  run_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  status: ResearchStatus;
  request: ResearchRunRequest;
  request_hash: string;
  dataset_manifest: ResearchDataset[] | Record<string, unknown>;
  models: ResearchModel[] | Record<string, unknown>[];
  selected_task_ids: string[];
  total_cells: number;
  completed_cells: number;
  estimated_calls: number;
  actual_calls: number;
  cells: ResearchCell[];
  summary: ResearchSummaryRow[];
  events: ResearchEvent[];
  errors: string[];
  limitations: string[];
  metered_api_cost_usd: number;
  proof_ok: boolean;
}

export interface ResearchRunsResponse {
  items: ResearchLibraryEntry[];
  has_more: boolean;
}
