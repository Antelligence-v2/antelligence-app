import assert from "node:assert/strict";
import test from "node:test";

import {
  advancePlayhead, countByType, eventsByTick, formatMetric, numericSeriesKeys, pointAt, seriesValues, tickRange, tickSeries,
} from "../src/features/runs/derive.ts";
import type { EngineEvent } from "../src/api/engine.ts";

const ev = (seq: number, tick: number, type: string, data: Record<string, unknown> = {}): EngineEvent =>
  ({ seq, tick, type, agent_id: null, data, prev_hash: "p", hash: "h" });

const log: EngineEvent[] = [
  ev(0, 0, "run_started"),
  ev(1, 1, "decided"), ev(2, 1, "outcome"), ev(3, 1, "intent_blocked"),
  ev(4, 1, "tick_ended", { metrics: { living: 10, cleared: false, rate: 0, steps_to_success: null, label: "x", flat: 3 } }),
  ev(5, 2, "decided"),
  ev(6, 2, "tick_ended", { metrics: { living: 7, cleared: false, rate: 0.3, steps_to_success: null, label: "x", flat: 3 } }),
  ev(7, 3, "tick_ended", { metrics: { living: 4, cleared: true, rate: 0.6, steps_to_success: 3, label: "y", flat: 3 } }),
];

test("tickSeries reads tick_ended in tick order", () => {
  const series = tickSeries([...log].reverse());
  assert.deepEqual(series.map((p) => p.tick), [1, 2, 3]);
  assert.deepEqual(tickRange(series), { min: 1, max: 3 });
  assert.deepEqual(tickRange([]), { min: 0, max: 0 });
});

test("numericSeriesKeys keeps numeric metrics that change; drops flat, boolean and text", () => {
  const keys = numericSeriesKeys(tickSeries(log));
  assert.deepEqual(keys.sort(), ["living", "rate"]);
});

test("numericSeriesKeys ignores nulls but a single non-null value is not a trend", () => {
  assert.ok(!numericSeriesKeys(tickSeries(log)).includes("steps_to_success"));
});

test("seriesValues aligns values to ticks with nulls for gaps", () => {
  assert.deepEqual(seriesValues(tickSeries(log), "steps_to_success"), [null, null, 3]);
});

test("pointAt returns the state at or before a tick", () => {
  const series = tickSeries(log);
  assert.equal(pointAt(series, 0), undefined);
  assert.equal(pointAt(series, 2)?.metrics.living, 7);
  assert.equal(pointAt(series, 99)?.metrics.living, 4);
});

test("eventsByTick and countByType group activity", () => {
  const tick1 = eventsByTick(log).get(1) ?? [];
  assert.deepEqual(countByType(tick1), { decided: 1, outcome: 1, intent_blocked: 1, tick_ended: 1 });
});

test("formatMetric renders rates, integers, floats, booleans and missing values", () => {
  assert.equal(formatMetric("kill_rate", 0.17094), "17.1%");
  assert.equal(formatMetric("net_reduction_pct", 17.094), "17.1%");
  assert.equal(formatMetric("drug_delivered", 60), "60");
  assert.equal(formatMetric("deliveries", 1234), "1,234");
  assert.equal(formatMetric("mean_living_cells", 106.9), "106.9");
  assert.equal(formatMetric("x", 0.12345), "0.123");
  assert.equal(formatMetric("cleared", true), "Yes");
  assert.equal(formatMetric("cleared_at", null), "—");
});

test("advancePlayhead moves by elapsed time and clamps at the end", () => {
  assert.deepEqual(advancePlayhead(1, 500, 10, 100), { position: 6, ended: false });
  assert.deepEqual(advancePlayhead(98, 1000, 10, 100), { position: 100, ended: true });
});
