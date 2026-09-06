import type {
  Experiment,
  ExperimentCase,
  ExperimentRequest,
  ExperimentSummary,
  TumorSimulationConfig,
} from "./experimentTypes";

export const DEFAULT_EXPERIMENT_CONFIG: TumorSimulationConfig = {
  domain_size: 400,
  voxel_size: 20,
  n_nanobots: 10,
  tumor_radius: 120,
  agent_type: "Rule-Based",
  selected_model: "mistralai/Mistral-Large-Instruct-2411",
  use_queen: false,
  use_llm_queen: false,
  max_steps: 200,
  seed: 17,
  offline: true,
  cell_density: 0.001,
  vessel_density: 0.01,
};

export function parseSeedInput(input: string): number[] {
  if (!input.trim()) return [];
  return input
    .split(/[\s,]+/)
    .filter((token) => token.length > 0)
    .map((token) => Number(token));
}

export function buildExperimentRequest(
  name: string,
  seeds: number[],
  config: TumorSimulationConfig,
): ExperimentRequest {
  return {
    name: name.trim(),
    seeds: [...seeds],
    config: {
      ...config,
      agent_type: "Rule-Based",
      offline: true,
      use_queen: false,
      use_llm_queen: false,
      seed: seeds[0] ?? config.seed,
    },
  };
}

export function validateExperimentRequest(
  name: string,
  seeds: number[],
  config: TumorSimulationConfig,
): string[] {
  const errors: string[] = [];
  if (typeof name !== "string" || name.trim().length === 0) {
    errors.push("Experiment name is required.");
  } else if (name.trim().length > 80) {
    errors.push("Experiment name must be 80 characters or fewer.");
  }

  if (!Array.isArray(seeds) || seeds.length < 1 || seeds.length > 5) {
    errors.push("Seeds must contain 1–5 values.");
  }
  const seen = new Set<number>();
  for (const seed of seeds ?? []) {
    if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) {
      errors.push("Every seed must be an integer from 0 to 4294967295.");
      break;
    }
    if (seen.has(seed)) {
      errors.push("Seeds must be unique.");
      break;
    }
    seen.add(seed);
  }

  if (!config || typeof config !== "object") {
    errors.push("A tumor simulation config is required.");
    return errors;
  }

  const finitePositive = (value: number | undefined, label: string) => {
    if (!Number.isFinite(value) || (value as number) <= 0) {
      errors.push(`${label} must be a finite positive number.`);
    }
  };
  finitePositive(config.domain_size, "Domain size");
  if (Number.isFinite(config.domain_size) && config.domain_size > 1000) {
    errors.push("Domain size must be 1000 or smaller for an experiment.");
  }
  finitePositive(config.voxel_size, "Voxel size");
  const gridIntervals = config.domain_size / config.voxel_size;
  if (!Number.isFinite(gridIntervals) || gridIntervals < 2 || gridIntervals > 30) {
    errors.push("The domain/voxel grid must contain between 2 and 30 intervals.");
  }
  finitePositive(config.tumor_radius, "Tumor radius");
  if (
    Number.isFinite(config.domain_size) &&
    Number.isFinite(config.tumor_radius) &&
    config.tumor_radius > config.domain_size / 2
  ) {
    errors.push("Tumor radius must fit inside the domain.");
  }
  if (!Number.isInteger(config.n_nanobots) || config.n_nanobots < 1 || config.n_nanobots > 25) {
    errors.push("Nanobots must be an integer from 1 to 25.");
  }
  if (!Number.isInteger(config.max_steps) || config.max_steps < 1 || config.max_steps > 200) {
    errors.push("Steps per run must be an integer from 1 to 200.");
  }
  finitePositive(config.cell_density, "Cell density");
  finitePositive(config.vessel_density, "Vessel density");

  const expectedCells = Math.PI * config.tumor_radius ** 2 * config.cell_density;
  if (Number.isFinite(expectedCells) && expectedCells > 100) {
    errors.push("Expected tumor cells must be 100 or fewer.");
  }
  const seedCount = Array.isArray(seeds) ? seeds.length : 0;
  if (Number.isFinite(expectedCells) && expectedCells * config.max_steps * seedCount * 3 > 100000) {
    errors.push("This experiment exceeds the bounded workload budget.");
  }

  if (config.agent_type !== "Rule-Based") {
    errors.push("Experiments require the Rule-Based agent type.");
  }
  if (config.offline !== true) errors.push("Experiments must run offline.");
  if (config.use_queen !== false || config.use_llm_queen !== false) {
    errors.push("Experiments do not support a Queen controller.");
  }
  return errors;
}

const CSV_COLUMNS = [
  "row_type",
  "experiment_id",
  "name",
  "status",
  "case_id",
  "arm",
  "seed",
  "run_id",
  "config_hash",
  "initial_geometry_hash",
  "trace_hash",
  "initial_living_cells",
  "final_living_cells",
  "net_cell_reduction_pct",
  "deliveries",
  "drug_delivered",
  "simulation_minutes",
  "runtime_seconds",
  "summary_arm",
  "seed_count",
  "net_cell_reduction_pct_mean",
  "net_cell_reduction_pct_std",
  "deliveries_mean",
  "drug_delivered_mean",
  "vs_no_bots_pp",
  "vs_fixed_pp",
  "limitations",
  "created_at",
  "matched_initial_geometry",
  "request_seeds",
  "request_config",
  "replay_status",
  "expected_trace_hash",
  "actual_trace_hash",
  "replay_run_id",
  "checked_at",
  "replay_message",
  "error",
] as const;

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function caseRow(experiment: Experiment, item: ExperimentCase): unknown[] {
  return [
    "case",
    experiment.experiment_id,
    experiment.name,
    experiment.status,
    item.case_id,
    item.arm,
    item.seed,
    item.run_id,
    item.config_hash,
    item.initial_geometry_hash,
    item.trace_hash,
    item.initial_living_cells,
    item.final_living_cells,
    item.net_cell_reduction_pct,
    item.deliveries,
    item.drug_delivered,
    item.simulation_minutes,
    item.runtime_seconds,
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    (experiment.limitations ?? []).join("; "),
    experiment.created_at,
    experiment.matched_initial_geometry,
    (experiment.request?.seeds ?? []).join(";"),
    experiment.request?.config,
    "",
    "",
    "",
    "",
    "",
    "",
    experiment.error ?? "",
  ];
}

function summaryRow(experiment: Experiment, item: ExperimentSummary): unknown[] {
  return [
    "summary",
    experiment.experiment_id,
    experiment.name,
    experiment.status,
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    item.arm,
    item.seed_count,
    item.net_cell_reduction_pct_mean,
    item.net_cell_reduction_pct_std,
    item.deliveries_mean,
    item.drug_delivered_mean,
    item.vs_no_bots_pp,
    item.vs_fixed_pp,
    (experiment.limitations ?? []).join("; "),
    experiment.created_at,
    experiment.matched_initial_geometry,
    (experiment.request?.seeds ?? []).join(";"),
    experiment.request?.config,
    "",
    "",
    "",
    "",
    "",
    "",
    experiment.error ?? "",
  ];
}

function replayRow(experiment: Experiment, item: Experiment["replay_checks"][number]): unknown[] {
  return [
    "replay",
    experiment.experiment_id,
    experiment.name,
    experiment.status,
    item.case_id,
    "",
    "",
    item.replay_run_id,
    "",
    "",
    item.expected_trace_hash,
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    (experiment.limitations ?? []).join("; "),
    experiment.created_at,
    experiment.matched_initial_geometry,
    (experiment.request?.seeds ?? []).join(";"),
    experiment.request?.config,
    item.status,
    item.expected_trace_hash,
    item.actual_trace_hash,
    item.replay_run_id,
    item.checked_at,
    item.message,
    experiment.error ?? "",
  ];
}

export function experimentToCsv(experiment: Experiment): string {
  const rows = [
    CSV_COLUMNS.map(csvCell),
    ...(experiment.cases ?? []).map((item) => caseRow(experiment, item).map(csvCell)),
    ...(experiment.summary ?? []).map((item) => summaryRow(experiment, item).map(csvCell)),
    ...(experiment.replay_checks ?? []).map((item) => replayRow(experiment, item).map(csvCell)),
  ];
  return `${rows.map((row) => row.join(",")).join("\n")}\n`;
}

export function experimentToJson(experiment: Experiment): string {
  return `${JSON.stringify(experiment, null, 2)}\n`;
}

export function formatExperimentNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  const formatted = formatExperimentNumber(value, digits);
  return formatted === "—" ? formatted : `${formatted}%`;
}

export function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function isFinishedExperiment(status: string): boolean {
  return status === "completed" || status === "partial" || status === "failed";
}

export function getCaseById(experiment: Experiment | null, caseId: string): ExperimentCase | undefined {
  return experiment?.cases?.find((item) => item.case_id === caseId);
}
