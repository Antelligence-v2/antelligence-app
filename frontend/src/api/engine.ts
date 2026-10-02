/**
 * Engine API contract (backend: antelligence/api/app.py, mounted at /engine).
 *
 * The engine returns plain dicts, so OpenAPI has no useful types for it. These
 * zod schemas are the contract instead: required fields are checked at the
 * boundary (drift fails loudly), unknown extra fields pass through untouched.
 * This module is pure (no network, no import.meta) so it is unit-testable.
 */
import { z } from "zod";

const hash = z.string().min(1);

export const HealthSchema = z.object({ ok: z.boolean(), worlds: z.array(z.string()) });

export const ParamBoundsSchema = z.object({ default: z.number(), min: z.number(), max: z.number() });
export type ParamBounds = z.infer<typeof ParamBoundsSchema>;

export const WorldSchema = z.object({
  name: z.string(),
  arms: z.array(z.string()).min(1),
  default_cases: z.array(z.number()),
  baseline: z.string(),
  primary_metric: z.string(),
  lower_is_better: z.boolean(),
  success_metric: z.string(),
  params: z.record(ParamBoundsSchema),
  description: z.string(),
  metric_label: z.string().optional(),
  arm_descriptions: z.record(z.string()).optional(),
}).passthrough();
export type World = z.infer<typeof WorldSchema>;

export const RunSpecSchema = z.object({
  world: z.string(),
  arm: z.string(),
  case: z.number(),
  params: z.record(z.unknown()),
});
export type RunSpec = z.infer<typeof RunSpecSchema>;

export const VerdictSchema = z.object({
  verdict: z.string(),
  goal_reached: z.boolean(),
  blocked_attempts: z.number(),
  concurrent_blocks: z.number(),
  rejected_actions: z.number(),
  unsafe_applied: z.number(),
  policy_failures: z.number(),
}).passthrough();
export type Verdict = z.infer<typeof VerdictSchema>;

export const TrustSchema = z.object({
  trust_tier: z.string(),
  proof_ok: z.boolean(),
  onchain_ok: z.boolean(),
  note: z.string().optional(),
}).passthrough();
export type Trust = z.infer<typeof TrustSchema>;

export const BundleSchema = z.object({
  schema: z.string(),
  run_id: z.string(),
  arm: z.string(),
  scope: z.string(),
  spec: RunSpecSchema,
  config_hash: hash,
  trace_hash: hash,
  bundle_hash: hash,
  event_count: z.number(),
  ticks: z.number(),
  stopped_reason: z.string().nullable(),
  metrics: z.record(z.unknown()),
  counters: z.record(z.number()),
  trust: TrustSchema,
}).passthrough();
export type Bundle = z.infer<typeof BundleSchema>;

export const OutboxSchema = z.object({
  status: z.string(),
  attempts: z.number(),
  publisher: z.string().nullable().optional(),
  receipt: z.unknown().optional(),
  last_error: z.string().nullable().optional(),
}).passthrough().nullable();
export type Outbox = z.infer<typeof OutboxSchema>;

export const RunSchema = z.object({
  run_id: z.string(),
  spec: RunSpecSchema,
  metrics: z.record(z.unknown()),
  ticks: z.number(),
  stopped_reason: z.string().nullable(),
  trace_hash: hash,
  config_hash: hash,
  event_count: z.number(),
  verdict: VerdictSchema,
  bundle_hash: hash,
  bundle: BundleSchema,
  outbox: OutboxSchema.optional(),
}).passthrough();
export type Run = z.infer<typeof RunSchema>;

export const EVENT_TYPES = [
  "run_started", "observed", "decided", "policy_failed", "outcome", "signal_deposited",
  "signal_rejected", "signal_expired", "intent_blocked", "memory_changed", "tick_ended", "run_finished",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export const EngineEventSchema = z.object({
  seq: z.number(),
  tick: z.number(),
  type: z.string(),
  agent_id: z.string().nullable(),
  data: z.record(z.unknown()),
  prev_hash: hash,
  hash,
});
export type EngineEvent = z.infer<typeof EngineEventSchema>;

export const EventPageSchema = z.object({
  run_id: z.string(),
  total: z.number(),
  offset: z.number(),
  trace_hash: hash,
  events: z.array(EngineEventSchema),
});
export type EventPage = z.infer<typeof EventPageSchema>;

/** Visualization frames (not evidence): static scene + one snapshot per tick, tick 0 = initial state. */
// [x, y, kind, sender, ticks_left] plus z for 3D runs.
export const SignalMarkSchema = z.tuple([z.number(), z.number(), z.string(), z.string(), z.number()]).rest(z.number());
export const FrameSchema = z.object({
  tick: z.number(),
  world: z.record(z.unknown()),
  signals: z.array(SignalMarkSchema),
});
export const FramesSchema = z.object({
  run_id: z.string(),
  scene: z.record(z.unknown()),
  frames: z.array(FrameSchema).min(1),
});
export type Frame = z.infer<typeof FrameSchema>;
export type Frames = z.infer<typeof FramesSchema>;

export const ReplaySchema = z.object({
  replay_ok: z.boolean(),
  reason: z.string().nullable(),
  replayed_trace_hash: z.string().nullable().optional(),
  expected_trace_hash: z.string().nullable().optional(),
  event_count: z.number().optional(),
}).passthrough();
export type Replay = z.infer<typeof ReplaySchema>;

export const ArmSummarySchema = z.object({
  cases: z.number(),
  successes: z.number(),
  success_wilson_95: z.object({ low: z.number(), high: z.number() }),
  verdicts: z.record(z.number()),
  unsafe_applied: z.number(),
  blocked_attempts: z.number(),
  concurrent_blocks: z.number(),
  policy_failures: z.number(),
}).passthrough();
export type ArmSummary = z.infer<typeof ArmSummarySchema>;

export const ComparisonSchema = z.object({
  pairs: z.number(),
  dropped_pairs: z.number(),
  wins: z.number(),
  losses: z.number(),
  ties: z.number(),
  baseline_total: z.number(),
  treatment_total: z.number(),
  mean_delta: z.number().nullable(),
  pct_change: z.number().nullable(),
  sign_test_p: z.number().nullable(),
  lower_is_better: z.boolean(),
}).passthrough();
export type Comparison = z.infer<typeof ComparisonSchema>;

export const ExperimentRequestSchema = z.object({
  world: z.string(),
  arms: z.array(z.string()),
  cases: z.array(z.number()),
  baseline: z.string(),
  params: z.record(z.unknown()),
});

export const ExperimentRunRowSchema = z.object({
  run_id: z.string(),
  spec: RunSpecSchema,
  trace_hash: hash,
  bundle_hash: hash,
  ticks: z.number(),
  verdict: z.string(),
}).passthrough();

/** Optional engine recommendation (newer engines): which arm, if any, beat the baseline. */
export const RecommendationSchema = z.object({
  best_arm: z.string().nullable(),
  baseline: z.string(),
  summary: z.string(),
  significance: z.number(),
  seeds: z.number(),
  underpowered: z.boolean(),
  verdicts: z.record(z.object({
    verdict: z.string(),
    reason: z.string(),
    pct_change: z.number().nullable(),
    mean_delta: z.number().nullable(),
    p: z.number().nullable(),
  }).passthrough()),
}).passthrough();
export type Recommendation = z.infer<typeof RecommendationSchema>;

export const ExperimentSchema = z.object({
  experiment_id: z.string(),
  request: ExperimentRequestSchema,
  primary_metric: z.string(),
  lower_is_better: z.boolean(),
  arms: z.record(ArmSummarySchema),
  comparisons_vs_baseline: z.record(ComparisonSchema),
  runs: z.record(z.array(ExperimentRunRowSchema)),
  caveats: z.array(z.string()),
  recommendation: RecommendationSchema.optional(),
}).passthrough();
export type Experiment = z.infer<typeof ExperimentSchema>;

export const ExperimentListItemSchema = z.object({
  experiment_id: z.string(),
  request: ExperimentRequestSchema,
  created_at: z.number(),
});
export type ExperimentListItem = z.infer<typeof ExperimentListItemSchema>;

export const ExperimentJobSchema = z.object({
  job_id: z.string(),
  status: z.enum(["running", "done", "failed"]),
  done: z.number(),
  total: z.number(),
  experiment_id: z.string().nullable(),
  error: z.string().nullable(),
});
export type ExperimentJob = z.infer<typeof ExperimentJobSchema>;

export type RunRequest = { world: string; arm: string; case: number; params?: Record<string, number> };
export type ExperimentBody = { world: string; arms: string[]; cases?: number[]; baseline?: string; params?: Record<string, number> };

/** A normalized API failure: what the user should read, plus the HTTP status if any. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number | null = null, readonly cause?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

type AxiosLike = { response?: { status?: number; data?: unknown }; message?: string; code?: string };

/** Turns axios / FastAPI / zod failures into one readable ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof z.ZodError) {
    const first = error.issues[0];
    return new ApiError(`Unexpected response from the engine (${first?.path.join(".") || "root"}: ${first?.message}).`, null, error);
  }
  const e = (error ?? {}) as AxiosLike;
  const status = e.response?.status ?? null;
  const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return new ApiError(detail, status, error);
  if (Array.isArray(detail)) {
    const msg = detail.map((d) => (d as { msg?: string }).msg).filter(Boolean).join("; ");
    if (msg) return new ApiError(msg, status, error);
  }
  if (status === 403) return new ApiError("The engine API only accepts local requests.", status, error);
  if (status === 404) return new ApiError("Not found.", status, error);
  if (!e.response) return new ApiError("Can't reach the engine. Is the backend running on this machine?", null, error);
  return new ApiError(e.message || `Request failed (${status}).`, status, error);
}

/**
 * Loads every event of a run by walking pages until `total` is reached.
 * `fetchPage` is injected so this stays testable without a network.
 */
export async function fetchAllEvents(
  fetchPage: (offset: number, limit: number) => Promise<EventPage>,
  pageSize = 1000,
): Promise<{ events: EngineEvent[]; total: number; trace_hash: string }> {
  const first = await fetchPage(0, pageSize);
  const events = [...first.events];
  while (events.length < first.total) {
    const page = await fetchPage(events.length, pageSize);
    if (page.events.length === 0) break; // log shrank or server capped: stop rather than loop forever
    events.push(...page.events);
  }
  return { events, total: first.total, trace_hash: first.trace_hash };
}
