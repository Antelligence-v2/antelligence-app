/** Pure helpers for experiment reports. */
import type { Comparison } from "../../api/engine.ts";

export type Effect = "better" | "worse" | "neutral";

/** Whether a change vs baseline is an improvement, given the metric's direction. */
export function effectOf(pctChange: number | null, lowerIsBetter: boolean): Effect {
  if (pctChange === null || pctChange === 0) return "neutral";
  return (pctChange < 0) === lowerIsBetter ? "better" : "worse";
}

/** p-values as reviewers read them: "p < 0.001", "p = 0.012", or "—". */
export function formatP(p: number | null | undefined): string {
  if (p === null || p === undefined) return "—";
  if (p < 0.001) return "p < 0.001";
  return `p = ${p < 0.1 ? p.toPrecision(2) : p.toFixed(2)}`;
}

export function formatPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "±";
  return `${sign}${Math.abs(pct).toFixed(Math.abs(pct) < 10 ? 1 : 0)}%`;
}

/** Symmetric axis bound for a forest plot of % changes, rounded up to a clean step. */
export function forestBound(comparisons: Record<string, Comparison>): number {
  const max = Math.max(5, ...Object.values(comparisons).map((c) => Math.abs(c.pct_change ?? 0)));
  const step = max <= 20 ? 5 : max <= 50 ? 10 : 25;
  return Math.ceil(max / step) * step;
}

/** 0..1 intensity for a run-matrix cell; 1 = best value in the experiment for this metric. */
export function cellIntensity(value: number | null, lo: number, hi: number, lowerIsBetter: boolean): number {
  if (value === null || hi === lo) return 0.5;
  const t = (value - lo) / (hi - lo);
  return lowerIsBetter ? 1 - t : t;
}

/** The smallest two-sided sign-test p achievable with n pairs (all wins). */
export function minimumP(pairs: number): number {
  return pairs > 0 ? Math.min(1, 2 * 0.5 ** pairs) : 1;
}
