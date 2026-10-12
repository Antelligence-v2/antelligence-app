import assert from "node:assert/strict";
import test from "node:test";

import { frameAgentIds } from "../src/features/viewport/decode.ts";
import { LiveFramesSchema, RunJobSchema, WorldSchema } from "../src/api/engine.ts";
import type { Frames } from "../src/api/engine.ts";

const colony = (ants: number[][], predators: number[][]): Frames => ({
  run_id: "r",
  scene: { kind: "ant_colony", grid: [20, 20], nest: [10, 10], fields: ["trail"], queen: false },
  frames: [{ tick: 0, world: { ants, predators, foods: [], fields: {} }, signals: [] }],
});

test("ant colony agent ids come from the index column, so caught ants keep their ids", () => {
  const ids = frameAgentIds(colony([[1, 1, 0, 0, 0], [2, 2, 0, 1, 3]], [[5, 5, 100, 0, 0]]));
  assert.deepEqual(ids, ["ant-000", "ant-003", "predator-000"]);
});

test("world catalog accepts options and llm status", () => {
  const world = WorldSchema.parse({
    name: "ant_colony", arms: ["no_queen", "queen"], default_cases: [42], baseline: "no_queen",
    primary_metric: "food_collected", lower_is_better: false, success_metric: "all_food_collected",
    params: { n_ants: { default: 10, min: 1, max: 60 } }, description: "d",
    options: { agent_type: { default: "Rule-Based", allowed: ["Rule-Based", "LLM-Powered", "Hybrid"], label: "Ant brains" } },
    llm: { default_model: "meta-llama/Llama-3.3-70B-Instruct", available: false },
  });
  assert.equal(world.options?.agent_type.allowed.length, 3);
  assert.equal(world.llm?.available, false);
  // Older engines send neither field.
  assert.equal(WorldSchema.parse({ ...world, options: undefined, llm: undefined }).options, undefined);
});

test("run jobs and live frames parse", () => {
  const job = RunJobSchema.parse({ job_id: "j", status: "queued", run_id: "r", tick: 0, max_ticks: 200, llm: true, error: null });
  assert.equal(job.status, "queued");
  assert.throws(() => RunJobSchema.parse({ ...job, status: "lost" }));
  const live = LiveFramesSchema.parse({ scene: { kind: "ant_colony" }, frames: [], total: 0 });
  assert.equal(live.total, 0);
});
