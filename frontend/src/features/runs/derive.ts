/** Pure derivations from a run's hash-chained event log. No React, no network. */
import type { EngineEvent } from "../../api/engine.ts";

export type TickPoint = { tick: number; metrics: Record<string, unknown> };

/** Per-tick world metrics, from `tick_ended` events, in tick order. */
export function tickSeries(events: readonly EngineEvent[]): TickPoint[] {
  return events
    .filter((e) => e.type === "tick_ended")
    .map((e) => ({ tick: e.tick, metrics: (e.data.metrics ?? {}) as Record<string, unknown> }))
    .sort((a, b) => a.tick - b.tick);
}

/** Metric keys that are numeric throughout the series (nulls allowed) and actually change. */
export function numericSeriesKeys(series: readonly TickPoint[]): string[] {
  if (series.length === 0) return [];
  const keys = Object.keys(series[series.length - 1].metrics);
  return keys.filter((key) => {
    let first: number | undefined;
    let varies = false;
    for (const point of series) {
      const v = point.metrics[key];
      if (v === null || v === undefined) continue;
      if (typeof v !== "number" || !Number.isFinite(v)) return false;
      if (first === undefined) first = v;
      else if (v !== first) varies = true;
    }
    return first !== undefined && varies;
  });
}

/** Values of one metric aligned to the series (null where missing). */
export function seriesValues(series: readonly TickPoint[], key: string): Array<number | null> {
  return series.map((p) => (typeof p.metrics[key] === "number" ? (p.metrics[key] as number) : null));
}

export function eventsByTick(events: readonly EngineEvent[]): Map<number, EngineEvent[]> {
  const map = new Map<number, EngineEvent[]>();
  for (const e of events) {
    const bucket = map.get(e.tick);
    if (bucket) bucket.push(e);
    else map.set(e.tick, [e]);
  }
  return map;
}

export function countByType(events: readonly EngineEvent[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const e of events) counts[e.type] = (counts[e.type] ?? 0) + 1;
  return counts;
}

/** Tick bounds of a run: ticks are 1-based in the engine; 0 holds run_started. */
export function tickRange(series: readonly TickPoint[]): { min: number; max: number } {
  if (series.length === 0) return { min: 0, max: 0 };
  return { min: series[0].tick, max: series[series.length - 1].tick };
}

/** The series point at or before `tick` (the state the world was in at that tick). */
export function pointAt(series: readonly TickPoint[], tick: number): TickPoint | undefined {
  let lo = 0;
  let hi = series.length - 1;
  let found: TickPoint | undefined;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (series[mid].tick <= tick) {
      found = series[mid];
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

const PERCENT_FRACTION = new Set(["kill_rate"]);

/** Human formatting for engine metrics: rates as %, floats trimmed, booleans as words. */
export function formatMetric(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "number") return typeof value === "string" ? value : JSON.stringify(value);
  if (PERCENT_FRACTION.has(key)) return `${(value * 100).toFixed(1)}%`;
  if (key.endsWith("_pct")) return `${value.toFixed(1)}%`;
  if (Number.isInteger(value)) return value.toLocaleString("en-US");
  const abs = Math.abs(value);
  return abs >= 1000 ? Math.round(value).toLocaleString("en-US") : value.toFixed(abs < 1 ? 3 : 1);
}

/**
 * Playback clock: advance `tick` by elapsed time at `ticksPerSecond`.
 * Returns the new (fractional) position and whether playback reached the end.
 */
export function advancePlayhead(position: number, elapsedMs: number, ticksPerSecond: number, max: number): { position: number; ended: boolean } {
  const next = position + (elapsedMs / 1000) * ticksPerSecond;
  return next >= max ? { position: max, ended: true } : { position: next, ended: false };
}
