import assert from "node:assert/strict";
import test from "node:test";

import type { Frames } from "../src/api/engine.ts";
import { cellId, tumorViewModel, umToScene } from "../src/features/viewport/worlds/tumor/adapter.ts";

// 2×2 field, bytes in engine layout (index = x * ny + y): only (x=1, y=0) is set.
const field = Buffer.from([0, 0, 255, 0]).toString("base64");

// Two ticks: bot-000 targets cell 7, which then turns apoptotic (a kill).
const run: Frames = {
  run_id: "t",
  scene: { kind: "tumor", domain: [0, 600], center: [300, 300], tumor_radius: 200, vessels: [[100, 100]], field_shape: [2, 2], field_spacing: 300, fields: ["drug"] },
  frames: [
    { tick: 3, world: { bots: [[100, 100, 1, 20, 7]], cells: [[300, 400, 0, 7]], fields: { drug: { b64: field } } }, signals: [[300, 400, "found", "bot-000", 10]] },
    { tick: 4, world: { bots: [[300, 380, 2, 15, 7]], cells: [[300, 400, 3, 7]], fields: { drug: { b64: field } } }, signals: [] },
  ],
};

test("umToScene centers on the tumor at 100 µm per unit", () => {
  assert.deepEqual(umToScene([300, 300], 300, 300), [0, 0, 0]);
  assert.deepEqual(umToScene([300, 300], 500, 100), [2, 0, -2]);
});

test("tumor adapter maps bots with run UI ids, cells by id, and signals", () => {
  const model = tumorViewModel(run);
  assert.equal(model.steps, 2);
  const kinds = model.frames[0].map((a) => `${a.kind}:${a.id}`).sort();
  assert.deepEqual(kinds, ["bot:bot-000", "cell:cell:7", "signal:signal:bot-000:found:300,400"]);
  const bot = model.frames[1].find((a) => a.kind === "bot")!;
  assert.deepEqual(bot.attrs, { state: "delivering", payload: 15, target: 7 });
  assert.equal(model.frames[1].find((a) => a.id === cellId(7))!.attrs!.phase, "apoptotic");
  assert.deepEqual(model.bounds, { min: [-3, 0, -3], max: [3, 1, 3] });
});

test("tumor adapter records kills and decodes fields to z-major order", () => {
  const model = tumorViewModel(run);
  assert.deepEqual(model.events, [{ step: 1, pos: umToScene([300, 300], 300, 400), kind: "kill", data: { cell: 7 } }]);
  const drug = model.fields.drug;
  assert.equal(drug.snapshots.length, 2);
  assert.deepEqual([...drug.snapshots[0].values], [0, 1, 0, 0]); // (x=1, z=0)
  assert.equal(drug.cellSize, 3);
});
