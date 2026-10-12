/** Engine tumor frames → the shared viewport model. Pure: no React, no three. */
import type { Frames } from "../../../../api/engine.ts";
import type { AgentState, FieldSeries, Vec3, ViewModel, WorldEvent } from "../../core/model.ts";
import { decodeBase64, frameAgentIds } from "../../decode.ts";

/** What the tumor world's scene() records (antelligence/worlds/tumor/world.py). Units: µm. */
export interface TumorScene {
  kind: "tumor";
  domain: [number, number];
  center: [number, number];
  tumor_radius: number;
  vessels: Array<[number, number]>;
  field_shape: [number, number];
  field_spacing?: number;
  fields: string[];
}

/** 100 µm per scene unit. */
export const UM = 1 / 100;

export const BOT_STATES = ["searching", "targeting", "delivering", "returning", "reloading"] as const;
export const CELL_PHASES = ["viable", "hypoxic", "necrotic", "apoptotic"] as const;

/** Engine (x, y) in µm → scene (x, 0, z), centered on the tumor. */
export function umToScene(center: [number, number], x: number, y: number): Vec3 {
  return [(x - center[0]) * UM, 0, (y - center[1]) * UM];
}

export const cellId = (id: number) => `cell:${id}`;
const signalId = (sender: string, kind: string, x: number, y: number) => `signal:${sender}:${kind}:${x},${y}`;

/** One encoded field frame (bytes, index = x * ny + y) → values in 0..1 with index = z * width + x. */
function decodeField(b64: string, nx: number, ny: number): { values: Float32Array; max: number } {
  const bytes = decodeBase64(b64);
  const values = new Float32Array(nx * ny);
  let max = 0;
  for (let x = 0; x < nx; x++) {
    for (let y = 0; y < ny; y++) {
      const v = (bytes[x * ny + y] ?? 0) / 255;
      values[y * nx + x] = v;
      if (v > max) max = v;
    }
  }
  return { values, max };
}

/**
 * Converts a tumor run's frames into the viewport model: nanobots (ids match the
 * run UI's, so selection is shared with the inspector), cells by id, live signals,
 * every recorded field, and kill events when a cell turns apoptotic.
 */
export function tumorViewModel(data: Frames): ViewModel {
  const scene = data.scene as unknown as TumorScene;
  const at = (x: number, y: number) => umToScene(scene.center, x, y);
  const ids = frameAgentIds(data);
  const events: WorldEvent[] = [];

  const frames: AgentState[][] = data.frames.map((frame) => {
    const world = frame.world;
    const out: AgentState[] = [];
    ((world.bots ?? []) as Array<[number, number, number, number, number | null]>).forEach(([x, y, state, payload, target], i) => {
      out.push({ id: ids[i] ?? `bot-${i}`, kind: "bot", pos: at(x, y), attrs: { state: BOT_STATES[state] ?? "searching", payload, target: target ?? null } });
    });
    for (const [x, y, phase, id] of (world.cells ?? []) as number[][]) {
      out.push({ id: cellId(id), kind: "cell", pos: at(x, y), attrs: { phase: CELL_PHASES[phase] ?? "viable" } });
    }
    for (const [x, y, kind, sender, ttl] of frame.signals) {
      out.push({ id: signalId(sender, kind, x, y), kind: "signal", pos: at(x, y), attrs: { signal: kind, sender, ttl } });
    }
    return out;
  });

  // A living cell that turns apoptotic was killed by a delivery there.
  for (let i = 1; i < data.frames.length; i++) {
    const before = new Map(((data.frames[i - 1].world.cells ?? []) as number[][]).map((c) => [c[3], c[2]]));
    for (const [x, y, phase, id] of (data.frames[i].world.cells ?? []) as number[][]) {
      const was = before.get(id);
      if (phase === 3 && was !== undefined && was < 2) events.push({ step: i, pos: at(x, y), kind: "kill", data: { cell: id } });
    }
  }

  const [nx, ny] = scene.field_shape ?? [0, 0];
  const span = scene.domain[1] - scene.domain[0];
  const spacing = scene.field_spacing ?? span / Math.max(1, nx - 1);
  const fields: Record<string, FieldSeries> = {};
  for (const name of scene.fields ?? []) {
    const snapshots: FieldSeries["snapshots"] = [];
    data.frames.forEach((frame, step) => {
      const encoded = (frame.world.fields as Record<string, { b64: string }> | undefined)?.[name];
      if (encoded) snapshots.push({ step, ...decodeField(encoded.b64, nx, ny) });
    });
    if (snapshots.length) {
      fields[name] = { width: nx, height: ny, origin: at(scene.domain[0], scene.domain[0]), cellSize: spacing * UM, snapshots };
    }
  }

  const half = (span / 2) * UM;
  const mid = at((scene.domain[0] + scene.domain[1]) / 2, (scene.domain[0] + scene.domain[1]) / 2);
  return {
    bounds: { min: [mid[0] - half, 0, mid[2] - half], max: [mid[0] + half, 1, mid[2] + half] },
    steps: data.frames.length,
    frames,
    fields,
    events,
  };
}
