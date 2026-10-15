import assert from "node:assert/strict";
import test from "node:test";

import type { Frames } from "../src/api/engine.ts";
import { cellToScene, foodId, foragingViewModel } from "../src/features/viewport/worlds/foraging/adapter.ts";
import { demoForagingFrames } from "../src/features/viewport/worlds/foraging/demo.ts";

// Two ticks of a 4×2 foraging run: agent 0 picks up food 0, agent 1 delivers food 1.
const run: Frames = {
  run_id: "t",
  scene: { kind: "grid", grid: [4, 2], nest: [3, 1], view_k: 3, foods: [[1, 0, 0], [3, 0, 1]] },
  frames: [
    { tick: 5, world: { agents: [[0, 0, 0], [3, 0, 1]], remaining: [[1, 0, 0]], delivered: 0, next_needed: 0 }, signals: [[1, 0, "found", "0", 30]] },
    { tick: 6, world: { agents: [[1, 0, 1], [3, 1, 0]], remaining: [], delivered: 1, next_needed: 1 }, signals: [] },
  ],
};

test("cellToScene centers the grid on the origin, one unit per cell", () => {
  assert.deepEqual(cellToScene(4, 2, 0, 0), [-1.5, 0, -0.5]);
  assert.deepEqual(cellToScene(4, 2, 3, 1), [1.5, 0, 0.5]);
});

test("foraging adapter maps agents with the run UI's ids, food with its order, and signals", () => {
  const model = foragingViewModel(run);
  const kinds = model.frames[0].map((a) => `${a.kind}:${a.id}`).sort();
  assert.deepEqual(kinds, ["ant:0", "ant:1", "food:food:0", "signal:signal:0:found:1,0"]);
  const ant = model.frames[1].find((a) => a.id === "0")!;
  assert.deepEqual(ant.pos, cellToScene(4, 2, 1, 0));
  assert.deepEqual(ant.attrs, { carry: 1, carrying: true });
  const food = model.frames[0].find((a) => a.id === foodId(0))!;
  assert.equal(food.attrs?.next, true);
  assert.equal(model.frames[0].find((a) => a.kind === "signal")!.attrs?.ttl, 30);
});

test("foraging adapter records pickups and deliveries by frame index", () => {
  const { events } = foragingViewModel(run);
  assert.deepEqual(events.map((e) => [e.kind, e.step]).sort(), [["delivery", 1], ["pickup", 1]]);
  assert.deepEqual(events.find((e) => e.kind === "delivery")!.pos, cellToScene(4, 2, 3, 1));
});

test("foraging adapter frames the grid in its bounds", () => {
  const model = foragingViewModel(run);
  assert.deepEqual(model.bounds, { min: [-2, 0, -1], max: [2, 1, 1] });
  assert.equal(model.steps, 2);
});

test("demo foraging run is deterministic, engine-shaped, and delivers food in order", () => {
  const a = demoForagingFrames();
  assert.equal(JSON.stringify(a), JSON.stringify(demoForagingFrames()));
  assert.equal(a.scene.kind, "grid");
  const last = a.frames.at(-1)!.world;
  assert.ok((last.delivered as number) > 0, "some food is delivered");
  const delivered = a.frames.map((f) => f.world.delivered as number);
  assert.ok(delivered.every((d, i) => i === 0 || d >= delivered[i - 1]), "delivered never decreases");
  assert.ok(foragingViewModel(a).events.some((e) => e.kind === "delivery"));
});
