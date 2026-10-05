/** Pure helpers for replaying frames. No DOM. */
import type { Frame, Frames } from "../../api/engine.ts";

/** base64 → bytes (works in browsers and Node 20). */
export function decodeBase64(b64: string): Uint8Array {
  if (typeof atob === "function") {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  return new Uint8Array(Buffer.from(b64, "base64"));
}

/** Frame at or before a (possibly fractional) tick, plus the next one and the blend factor. */
export function framePair(frames: readonly Frame[], position: number): { a: Frame; b: Frame; t: number } {
  const first = frames[0].tick;
  const i = Math.min(frames.length - 1, Math.max(0, Math.floor(position) - first));
  const a = frames[i];
  const b = frames[Math.min(frames.length - 1, i + 1)];
  const t = b === a ? 0 : Math.min(1, Math.max(0, position - a.tick));
  return { a, b, t };
}

export const lerp = (from: number, to: number, t: number) => from + (to - from) * t;

/**
 * Interpolate positions of rows shaped [x, y, ...rest] between two frames.
 * Rows are matched by index (the engine emits agents in stable sorted order);
 * jumps longer than `maxJump` (e.g. teleports to a vessel) are not smeared.
 */
export function interpolateRows(from: number[][], to: number[][], t: number, maxJump = Infinity): number[][] {
  return from.map((row, i) => {
    const next = to[i];
    if (!next) return row;
    const jump = Math.hypot(next[0] - row[0], next[1] - row[1]);
    if (jump > maxJump) return t < 0.5 ? row : next;
    return [lerp(row[0], next[0], t), lerp(row[1], next[1], t), ...(t < 0.5 ? row.slice(2) : next.slice(2))];
  });
}

/** Last `length` positions of each row index up to and including frame index `upto` (for trails). */
export function trails(frames: readonly Frame[], key: string, upto: number, length: number): Array<Array<[number, number]>> {
  const start = Math.max(0, upto - length + 1);
  const out: Array<Array<[number, number]>> = [];
  for (let f = start; f <= upto; f++) {
    const rows = (frames[f].world[key] ?? []) as number[][];
    rows.forEach((row, i) => (out[i] ??= []).push([row[0], row[1]]));
  }
  return out;
}

/** Agent ids in frame row order (the engine emits agents sorted by id). */
export function frameAgentIds(data: Frames): string[] {
  const kind = data.scene.kind as string;
  const first = data.frames[0].world;
  const count = ((kind === "tumor" ? first.bots : first.agents) as unknown[] | undefined)?.length ?? 0;
  return Array.from({ length: count }, (_, i) => (kind === "tumor" ? `bot-${String(i).padStart(3, "0")}` : String(i)));
}
