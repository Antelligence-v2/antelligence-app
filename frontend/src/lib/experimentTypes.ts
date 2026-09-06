export type ExperimentArm = "no_bots" | "fixed" | "pheromone" | string;
export type ExperimentStatus = "queued" | "running" | "completed" | "partial" | "failed" | string;
export type ReplayStatus = "matched" | "mismatch" | "error" | string;

export interface TumorSimulationConfig {
  domain_size: number;
  voxel_size: number;
  n_nanobots: number;
  tumor_radius: number;
  agent_type: "LLM-Powered" | "Rule-Based" | "Hybrid" | string;
  selected_model: string;
  use_queen: boolean;
  use_llm_queen: boolean;
  max_steps: number;
  seed: number;
  offline: boolean;
  cell_density: number;
  vessel_density: number;
  /** Present on executed arm configs; intentionally omitted from POST request config. */
  pheromones_enabled?: boolean;
  [key: string]: unknown;
}

export interface ExperimentRequest {
  name: string;
  seeds: number[];
  config: TumorSimulationConfig;
}

export interface ExperimentCase {
  case_id: string;
  arm: ExperimentArm;
  seed: number;
  run_id: string;
  config_hash: string;
  initial_geometry_hash: string;
  trace_hash: string;
  config: TumorSimulationConfig;
  initial_living_cells: number | null;
  final_living_cells: number | null;
  net_cell_reduction_pct: number | null;
  deliveries: number | null;
  drug_delivered: number | null;
  simulation_minutes: number | null;
  runtime_seconds: number | null;
}

export interface ExperimentSummary {
  arm: ExperimentArm;
  seed_count: number;
  net_cell_reduction_pct_mean: number | null;
  net_cell_reduction_pct_std: number | null;
  deliveries_mean: number | null;
  drug_delivered_mean: number | null;
  vs_no_bots_pp: number | null;
  vs_fixed_pp: number | null;
}

export interface ReplayCheck {
  experiment_id: string;
  case_id: string;
  status: ReplayStatus;
  expected_trace_hash: string;
  actual_trace_hash: string;
  replay_run_id: string;
  checked_at: string;
  message: string;
}

export interface Experiment {
  experiment_id: string;
  name: string;
  created_at: string;
  status: ExperimentStatus;
  request: ExperimentRequest;
  case_count: number;
  seed_count: number;
  matched_initial_geometry: boolean;
  cases: ExperimentCase[];
  summary: ExperimentSummary[];
  replay_checks: ReplayCheck[];
  limitations: string[];
  error?: string | null;
}

export interface ExperimentLibraryEntry {
  experiment_id: string;
  name: string;
  created_at: string;
  status: ExperimentStatus;
  case_count: number;
  seed_count: number;
}
