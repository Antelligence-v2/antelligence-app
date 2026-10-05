import assert from "node:assert/strict";
import test from "node:test";

import { decodeBase64, framePair, interpolateRows, trails } from "../src/features/viewport/decode.ts";
import type { Frame } from "../src/api/engine.ts";

const frame = (tick: number, agents: number[][]): Frame => ({ tick, world: { agents }, signals: [] });
const frames = [frame(0, [[0, 0, 0], [5, 5, 0]]), frame(1, [[1, 0, 0], [5, 6, 1]]), frame(2, [[2, 0, 1], [9, 9, 1]])];

test("framePair picks the frame at or before the playhead and the blend toward the next", () => {
  const { a, b, t } = framePair(frames, 1.25);
  assert.equal(a.tick, 1);
  assert.equal(b.tick, 2);
  assert.equal(t, 0.25);
  assert.equal(framePair(frames, 2).t, 0);
  assert.equal(framePair(frames, 99).a.tick, 2);
  assert.equal(framePair(frames, -3).a.tick, 0);
});

test("interpolateRows blends positions and switches discrete fields at the midpoint", () => {
  const out = interpolateRows(frames[1].world.agents as number[][], frames[2].world.agents as number[][], 0.25, 3);
  assert.deepEqual(out[0], [1.25, 0, 0]);
  // Agent 1 jumps (5,6)->(9,9): longer than maxJump, so it snaps instead of smearing.
  assert.deepEqual(out[1], [5, 6, 1]);
  assert.deepEqual(interpolateRows(frames[1].world.agents as number[][], frames[2].world.agents as number[][], 0.75, 3)[1], [9, 9, 1]);
});

test("trails collect the last N positions per agent", () => {
  const paths = trails(frames, "agents", 2, 2);
  assert.deepEqual(paths[0], [[1, 0], [2, 0]]);
  assert.deepEqual(paths[1], [[5, 6], [9, 9]]);
});

test("decodeBase64 round-trips bytes", () => {
  assert.deepEqual([...decodeBase64("AAH/")], [0, 1, 255]);
});
