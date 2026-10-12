/** A synthetic foraging run in the engine's frame format, for the viewport lab. Pure. */
import type { Frame, Frames } from "../../../../api/engine.ts";

/** Small seeded PRNG (mulberry32) so the demo is identical every time. */
function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Pos = [number, number];
const DIRS: Pos[] = [[0, -1], [0, 1], [1, 0], [-1, 0]];

/**
 * Mirrors antelligence/worlds/foraging: a 10×10 grid, numbered foods that must
 * reach the nest in order, agents that move one cell N/S/E/W per tick and post
 * "found" signals (ttl 30) when food is in view. Agents sweep randomly until the
 * needed food is known, fetch it, and carry it home.
 */
export function demoForagingFrames({ size = 10, agents = 3, foods = 3, ticks = 120, viewK = 5, seed = 101 } = {}): Frames {
  const rand = rng(seed);
  const cell = (): Pos => [Math.floor(rand() * size), Math.floor(rand() * size)];
  const same = (a: Pos, b: Pos) => a[0] === b[0] && a[1] === b[1];
  const nest = cell();
  const food: Pos[] = [];
  while (food.length < foods) {
    const f = cell();
    if (!same(f, nest) && !food.some((g) => same(f, g)) && Math.max(Math.abs(f[0] - nest[0]), Math.abs(f[1] - nest[1])) > 2) food.push(f);
  }
  const pos: Pos[] = Array.from({ length: agents }, cell);
  const carrying: number[][] = Array.from({ length: agents }, () => []);
  const remaining = new Set(food.map((_, i) => i));
  const signals: Array<{ x: number; y: number; sender: string; food: number; expires: number }> = [];
  let delivered = 0;
  let known: Pos | null = null;

  const toward = (p: Pos, goal: Pos): Pos => {
    const dx = Math.sign(goal[0] - p[0]);
    const dy = Math.sign(goal[1] - p[1]);
    if (dx !== 0 && (dy === 0 || rand() < 0.5)) return [p[0] + dx, p[1]];
    return [p[0], p[1] + dy];
  };
  const clamp = ([x, y]: Pos): Pos => [Math.min(size - 1, Math.max(0, x)), Math.min(size - 1, Math.max(0, y))];

  const frames: Frame[] = [];
  for (let tick = 0; tick < ticks; tick++) {
    if (tick > 0) {
      for (let a = 0; a < agents; a++) {
        const next = delivered < foods ? delivered : null;
        let goal: Pos | null = null;
        if (carrying[a].length) goal = nest;
        else if (next !== null && known) goal = known;
        const step = goal ? toward(pos[a], goal) : (() => { const d = DIRS[Math.floor(rand() * 4)]; return [pos[a][0] + d[0], pos[a][1] + d[1]] as Pos; })();
        pos[a] = clamp(step);

        // Seeing food posts a signal; the needed one becomes known to everyone.
        const r = Math.floor(viewK / 2);
        for (const i of remaining) {
          const f = food[i];
          if (Math.abs(f[0] - pos[a][0]) <= r && Math.abs(f[1] - pos[a][1]) <= r) {
            if (!signals.some((s) => s.food === i && s.expires > tick)) signals.push({ x: f[0], y: f[1], sender: String(a), food: i, expires: tick + 30 });
            if (i === next) known = f;
          }
        }
        if (next !== null && !carrying[a].length && remaining.has(next) && same(pos[a], food[next])) {
          remaining.delete(next);
          carrying[a].push(next);
        } else if (carrying[a].length && same(pos[a], nest)) {
          delivered += carrying[a].length;
          carrying[a] = [];
          known = null;
        }
      }
    }
    const next = delivered < foods ? delivered : null;
    frames.push({
      tick,
      world: {
        agents: pos.map((p, a) => [p[0], p[1], carrying[a].length]),
        remaining: [...remaining].map((i) => [food[i][0], food[i][1], i]),
        delivered,
        next_needed: next,
      },
      signals: signals.filter((s) => s.expires > tick).map((s) => [s.x, s.y, "found", s.sender, s.expires - tick] as [number, number, string, string, number]),
    });
  }
  return {
    run_id: "demo-foraging",
    scene: { kind: "grid", grid: [size, size], nest, view_k: viewK, foods: food.map((f, i) => [f[0], f[1], i]) },
    frames,
  };
}
