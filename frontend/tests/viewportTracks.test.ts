import assert from "node:assert/strict";
import test from "node:test";

import { lerpAngle, Tracks } from "../src/features/viewport/core/tracks.ts";
import type { AgentState } from "../src/features/viewport/core/model.ts";

const at = (id: string, x: number, z: number, attrs?: Record<string, unknown>): AgentState =>
  ({ id, kind: "ant", pos: [x, 0, z], attrs });

const close = (actual: number, expected: number, eps = 1e-6) =>
  assert.ok(Math.abs(actual - expected) < eps, `${actual} ≉ ${expected}`);

test("tracks pose exactly on integer steps", () => {
  const tracks = new Tracks([[at("a", 0, 0)], [at("a", 1, 0)]]);
  assert.deepEqual(tracks.poseAll(0)[0].pos, [0, 0, 0]);
  assert.deepEqual(tracks.poseAll(1)[0].pos, [1, 0, 0]);
});

test("tracks interpolate with easing: halfway is halfway, slower at the start", () => {
  const tracks = new Tracks([[at("a", 0, 0)], [at("a", 2, 0)]]);
  close(tracks.poseAll(0.5)[0].pos[0], 1);
  assert.ok(tracks.poseAll(0.25)[0].pos[0] < 0.5);
});

test("tracks face the direction of travel and keep it while standing still", () => {
  const tracks = new Tracks([[at("a", 0, 0)], [at("a", 1, 0)], [at("a", 1, 0)]]);
  close(tracks.poseAll(1)[0].heading, Math.PI / 2); // +x
  close(tracks.poseAll(2)[0].heading, Math.PI / 2);
});

test("tracks fade agents in and out when they appear or disappear", () => {
  const tracks = new Tracks([[at("gone", 0, 0)], [at("new", 3, 3)]]);
  const poses = tracks.poseAll(0.5);
  close(poses.find((p) => p.id === "gone")!.presence, 0.5);
  close(poses.find((p) => p.id === "new")!.presence, 0.5);
  assert.equal(tracks.poseAll(1).find((p) => p.id === "gone"), undefined);
});

test("tracks snap long jumps instead of sliding across the map", () => {
  const tracks = new Tracks([[at("a", 0, 0)], [at("a", 10, 0)]], 3);
  assert.equal(tracks.poseAll(0.4)[0].pos[0], 0);
  assert.equal(tracks.poseAll(0.6)[0].pos[0], 10);
});

test("tracks clamp positions outside the run", () => {
  const tracks = new Tracks([[at("a", 0, 0)], [at("a", 1, 0)]]);
  assert.deepEqual(tracks.poseAll(-5)[0].pos, [0, 0, 0]);
  assert.deepEqual(tracks.poseAll(99)[0].pos, [1, 0, 0]);
});

test("tracks switch attributes at the midpoint of a step", () => {
  const tracks = new Tracks([[at("a", 0, 0, { carrying: false })], [at("a", 1, 0, { carrying: true })]]);
  assert.equal(tracks.poseAll(0.4)[0].attrs?.carrying, false);
  assert.equal(tracks.poseAll(0.6)[0].attrs?.carrying, true);
});

test("lerpAngle turns the short way around", () => {
  const mid = lerpAngle(Math.PI * 0.9, -Math.PI * 0.9, 0.5);
  close(Math.cos(mid), -1, 1e-9);
});
