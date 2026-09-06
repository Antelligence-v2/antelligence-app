import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_EXPERIMENT_CONFIG,
  buildExperimentRequest,
  experimentToCsv,
  experimentToJson,
  parseSeedInput,
  validateExperimentRequest,
} from "../src/lib/experiment.ts";
import type { Experiment } from "../src/lib/experimentTypes.ts";

test("the default experiment request is explicit and bounded", () => {
  const request = buildExperimentRequest("  Pheromone baseline  ", [17, 23, 42], DEFAULT_EXPERIMENT_CONFIG);

  assert.deepEqual(request, {
    name: "Pheromone baseline",
    seeds: [17, 23, 42],
    config: {
      ...DEFAULT_EXPERIMENT_CONFIG,
      agent_type: "Rule-Based",
      offline: true,
      use_queen: false,
      use_llm_queen: false,
      seed: 17,
    },
  });
  assert.deepEqual(validateExperimentRequest(request.name, request.seeds, request.config), []);
});

test("seed input accepts comma-separated integers and preserves order", () => {
  assert.deepEqual(parseSeedInput("17, 23\n42"), [17, 23, 42]);
  assert.deepEqual(parseSeedInput("  "), []);
});

test("validation reports contract violations without rewriting the request", () => {
  const errors = validateExperimentRequest(
    " ",
    [7, 7, -2, 4, 5, 6],
    {
      ...DEFAULT_EXPERIMENT_CONFIG,
      domain_size: 800,
      voxel_size: 10,
      tumor_radius: 500,
      n_nanobots: 26,
      max_steps: 201,
    },
  );

  assert.equal(errors.some((error) => error.includes("name")), true);
  assert.equal(errors.some((error) => error.includes("unique")), true);
  assert.equal(errors.some((error) => error.includes("1–5")), true);
  assert.equal(errors.some((error) => error.includes("25")), true);
  assert.equal(errors.some((error) => error.includes("200")), true);
  assert.equal(errors.some((error) => error.includes("grid")), true);
  assert.equal(errors.some((error) => error.includes("radius")), true);
});

test("CSV export contains actual case and summary values with safe quoting", () => {
  const experiment: Experiment = {
    experiment_id: "exp-1",
    name: "Seed, study",
    created_at: "2026-09-06T12:00:00Z",
    status: "completed",
    request: {
      name: "Seed, study",
      seeds: [17],
      config: { ...DEFAULT_EXPERIMENT_CONFIG, seed: 17 },
    },
    case_count: 3,
    seed_count: 1,
    matched_initial_geometry: true,
    cases: [
      {
        case_id: "fixed:17",
        arm: "fixed",
        seed: 17,
        run_id: "run-17",
        config_hash: "cfg",
        initial_geometry_hash: "geo",
        trace_hash: "trace",
        config: { ...DEFAULT_EXPERIMENT_CONFIG, seed: 17, n_nanobots: 10 },
        initial_living_cells: 10,
        final_living_cells: 8,
        net_cell_reduction_pct: 20,
        deliveries: 4,
        drug_delivered: 12.5,
        simulation_minutes: 20,
        runtime_seconds: 0.25,
      },
    ],
    summary: [
      {
        arm: "fixed",
        seed_count: 1,
        net_cell_reduction_pct_mean: 20,
        net_cell_reduction_pct_std: null,
        deliveries_mean: 4,
        drug_delivered_mean: 12.5,
        vs_no_bots_pp: null,
        vs_fixed_pp: null,
      },
    ],
    replay_checks: [],
    limitations: ["Synthetic 2D only"],
  };

  const csv = experimentToCsv(experiment);
  assert.match(csv, /row_type,experiment_id,name/);
  assert.match(csv, /case,exp-1,"Seed, study",completed,fixed:17,fixed,17,run-17/);
  assert.match(csv, /summary,exp-1,"Seed, study",completed,,,,,,,,,,,,,,,fixed,1,20,,4,12\.5/);
  assert.match(csv, /Synthetic 2D only/);
  for (const unsafeName of ["=1+1", "+1+1", "-cmd", "@SUM(A1:A2)"]) {
    const safeCsv = experimentToCsv({ ...experiment, name: unsafeName });
    assert.ok(safeCsv.includes(`case,exp-1,'${unsafeName},completed`), unsafeName);
    assert.equal(JSON.parse(experimentToJson({ ...experiment, name: unsafeName })).name, unsafeName);
  }
  const negative = experimentToCsv({
    ...experiment,
    cases: [{ ...experiment.cases[0], net_cell_reduction_pct: -2 }],
  });
  assert.ok(negative.includes(",10,8,-2,4,12.5,"), "numeric growth must stay numeric, not text");
});

test("JSON export is the saved report, not a reduced chart projection", () => {
  const report = { experiment_id: "exp-2", cases: [{ case_id: "no_bots:17", trace_hash: "abc" }] } as unknown as Experiment;
  const json = experimentToJson(report);

  assert.deepEqual(JSON.parse(json), report);
  assert.equal(json.endsWith("\n"), true);
});
