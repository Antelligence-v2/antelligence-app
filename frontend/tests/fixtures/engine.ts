// Trimmed copies of real /engine responses (captured 2026-09-27 from antelligence/api/app.py).
const H = (c: string) => c.repeat(64);

export const world = {
  name: "foraging", arms: ["baseline", "hive_memory", "signals", "hive_memory_signals"],
  default_cases: [101, 102, 103], baseline: "baseline", primary_metric: "sweep_moves",
  lower_is_better: true, success_metric: "success", params: { max_steps: { default: 120, min: 10, max: 400 } },
  description: "E13 chain-prioritized foraging (10x10, 3 agents, 3 foods in order).",
};

export const run = {
  run_id: "foraging-hive_memory-101-8873656b40",
  spec: { world: "foraging", arm: "hive_memory", case: 101, params: { max_steps: 60 } },
  metrics: { sweep_moves: 41, success: true }, ticks: 31, stopped_reason: "world_done",
  trace_hash: H("a"), config_hash: H("b"), event_count: 369, bundle_hash: H("c"),
  verdict: { verdict: "success", goal_reached: true, blocked_attempts: 0, concurrent_blocks: 2, rejected_actions: 0, unsafe_applied: 0, policy_failures: 0 },
  bundle: {
    schema: "antelligence.run-bundle/v1", run_id: "foraging-hive_memory-101-8873656b40", arm: "hive_memory",
    scope: "foraging-hive_memory-101-8873656b40:hive_memory",
    spec: { world: "foraging", arm: "hive_memory", case: 101, params: { max_steps: 60 } },
    config_hash: H("b"), trace_hash: H("a"), bundle_hash: H("c"), event_count: 369, ticks: 31, stopped_reason: "world_done",
    metrics: { sweep_moves: 41 }, counters: { policy_failures: 0, signals_deposited: 28, signals_rejected: 0, intents_blocked: 2 },
    trust: { note: "Hash-chained event log + deterministic replay. Not a cryptographic proof.", onchain_ok: false, proof_ok: false, trust_tier: "local_replay" },
    extra: { verdict: { verdict: "success" } },
  },
  outbox: { bundle_hash: H("c"), run_id: "foraging-hive_memory-101-8873656b40", status: "pending", attempts: 0, publisher: null, receipt: null, last_error: null },
};

export const event = (seq: number, type = "observed", tick = 0) => ({
  seq, tick, type, agent_id: "0", data: { signal_ids: [] }, prev_hash: H("0"), hash: H("1"),
});
