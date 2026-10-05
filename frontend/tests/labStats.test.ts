import assert from "node:assert/strict";
import test from "node:test";

import { cellIntensity, effectOf, forestBound, formatP, formatPct, minimumP } from "../src/features/lab/stats.ts";

test("effectOf respects the metric direction", () => {
  assert.equal(effectOf(-49, true), "better");
  assert.equal(effectOf(-49, false), "worse");
  assert.equal(effectOf(12, false), "better");
  assert.equal(effectOf(0, true), "neutral");
  assert.equal(effectOf(null, true), "neutral");
});

test("formatP and formatPct read like a paper", () => {
  assert.equal(formatP(0.0004), "p < 0.001");
  assert.equal(formatP(0.012), "p = 0.012");
  assert.equal(formatP(0.5), "p = 0.50");
  assert.equal(formatP(null), "—");
  assert.equal(formatPct(-49.2), "−49%");
  assert.equal(formatPct(3.14), "+3.1%");
  assert.equal(formatPct(0), "±0.0%");
});

test("forestBound is symmetric, clean and never tiny", () => {
  const c = (pct: number | null) => ({ pct_change: pct }) as never;
  assert.equal(forestBound({ a: c(-3) }), 5);
  assert.equal(forestBound({ a: c(-49), b: c(12) }), 50);
  assert.equal(forestBound({ a: c(130) }), 150);
});

test("cellIntensity maps best to 1 in either direction", () => {
  assert.equal(cellIntensity(10, 10, 20, true), 1);
  assert.equal(cellIntensity(20, 10, 20, false), 1);
  assert.equal(cellIntensity(5, 5, 5, true), 0.5);
});

test("minimumP shows when a design is underpowered", () => {
  assert.equal(minimumP(3), 0.25);
  assert.ok(minimumP(6) < 0.05);
});
