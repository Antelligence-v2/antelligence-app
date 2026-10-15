/** Engine foraging frames → the shared viewport model. Pure: no React, no three. */
import type { Frames } from "../../../../api/engine.ts";
import type { AgentState, Vec3, ViewModel, WorldEvent } from "../../core/model.ts";
import { frameAgentIds } from "../../decode.ts";

/** What the foraging world's scene() records (antelligence/worlds/foraging/world.py). */
export interface ForagingScene {
  kind: "grid";
  grid: [number, number];
  nest: [number, number];
  view_k: number;
  /** [x, y, order]: foods must reach the nest in this order. */
  foods: Array<[number, number, number]>;
}

/** Grid cell (x = column, y = row) → scene position; the grid is centered on the origin. */
export function cellToScene(width: number, height: number, x: number, y: number): Vec3 {
  return [x - width / 2 + 0.5, 0, y - height / 2 + 0.5];
}

export const foodId = (order: number) => `food:${order}`;

/** Signals are keyed by sender, kind and cell, so a re-posted mark keeps its identity. */
const signalId = (sender: string, kind: string, x: number, y: number) => `signal:${sender}:${kind}:${x},${y}`;

/**
 * Converts a foraging run's frames into the viewport model. Agent ids match the
 * rest of the run UI (frameAgentIds), so selection is shared with the inspector.
 */
export function foragingViewModel(data: Frames): ViewModel {
  const scene = data.scene as unknown as ForagingScene;
  const [width, height] = scene.grid;
  const at = (x: number, y: number) => cellToScene(width, height, x, y);
  const ids = frameAgentIds(data);
  const events: WorldEvent[] = [];

  const frames: AgentState[][] = data.frames.map((frame) => {
    const world = frame.world;
    const next = (world.next_needed as number | null | undefined) ?? null;
    const out: AgentState[] = [];
    ((world.agents ?? []) as number[][]).forEach(([x, y, carry], i) => {
      out.push({ id: ids[i] ?? String(i), kind: "ant", pos: at(x, y), attrs: { carry, carrying: carry > 0 } });
    });
    for (const [x, y, order] of (world.remaining ?? []) as number[][]) {
      out.push({ id: foodId(order), kind: "food", pos: at(x, y), attrs: { order, next: order === next } });
    }
    for (const [x, y, kind, sender, ttl] of frame.signals) {
      out.push({ id: signalId(sender, kind, x, y), kind: "signal", pos: at(x, y), attrs: { signal: kind, sender, ttl } });
    }
    return out;
  });

  // Food that leaves `remaining` was picked up there; a rising `delivered` count is a delivery at the nest.
  for (let i = 1; i < data.frames.length; i++) {
    const prev = data.frames[i - 1].world;
    const cur = data.frames[i].world;
    const still = new Set(((cur.remaining ?? []) as number[][]).map((f) => f[2]));
    for (const [x, y, order] of (prev.remaining ?? []) as number[][]) {
      if (!still.has(order)) events.push({ step: i, pos: at(x, y), kind: "pickup", data: { order } });
    }
    const delivered = (cur.delivered as number) - (prev.delivered as number);
    for (let d = 0; d < delivered; d++) events.push({ step: i, pos: at(scene.nest[0], scene.nest[1]), kind: "delivery" });
  }

  return {
    bounds: { min: [-width / 2, 0, -height / 2], max: [width / 2, 1, height / 2] },
    steps: data.frames.length,
    frames,
    fields: {},
    events,
  };
}
