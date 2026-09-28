import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Frame } from "@/api/engine";
import { framePair, interpolateRows, trails } from "./decode";
import { themeColor, useSquareCanvas } from "./canvas";

export type GridSceneData = {
  grid: [number, number];
  nest: [number, number];
  view_k: number;
  foods: Array<[number, number, number]>;
};

const TRAIL = 10;

/** Foraging world: grid, nest, ordered food, agents with trails, and sighting signals. */
export function GridScene({ scene, frames, position, agentIds, selected, onSelect }: {
  scene: GridSceneData;
  frames: Frame[];
  position: number;
  agentIds: string[];
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const { resolvedTheme } = useTheme();
  const { a, b, t } = framePair(frames, position);
  const index = frames.indexOf(a);
  const [W, H] = scene.grid;
  const agents = interpolateRows(a.world.agents as number[][], b.world.agents as number[][], t, 3);
  const remaining = a.world.remaining as number[][];
  const nextNeeded = a.world.next_needed as number | null;
  const paths = useMemo(() => trails(frames, "agents", index, TRAIL), [frames, index]);

  const { wrap, canvas, size } = useSquareCanvas((ctx, s) => {
    const pad = 10;
    const cell = (s - pad * 2) / Math.max(W, H);
    const C = (v: number) => pad + (v + 0.5) * cell; // cell center

    ctx.fillStyle = themeColor("--surface-2");
    ctx.fillRect(pad, pad, cell * W, cell * H);
    ctx.strokeStyle = themeColor("--border");
    ctx.lineWidth = 1;
    for (let i = 0; i <= W; i++) {
      ctx.beginPath(); ctx.moveTo(pad + i * cell, pad); ctx.lineTo(pad + i * cell, pad + H * cell); ctx.stroke();
    }
    for (let j = 0; j <= H; j++) {
      ctx.beginPath(); ctx.moveTo(pad, pad + j * cell); ctx.lineTo(pad + W * cell, pad + j * cell); ctx.stroke();
    }

    // Selected agent's field of view.
    const sel = agentIds.indexOf(selected ?? "");
    if (sel >= 0 && agents[sel]) {
      const r = Math.floor(scene.view_k / 2);
      ctx.fillStyle = themeColor("--primary", 0.07);
      ctx.strokeStyle = themeColor("--primary", 0.35);
      ctx.setLineDash([4, 4]);
      const [ax, ay] = [Math.round(agents[sel][0]), Math.round(agents[sel][1])];
      ctx.fillRect(pad + (ax - r) * cell, pad + (ay - r) * cell, scene.view_k * cell, scene.view_k * cell);
      ctx.strokeRect(pad + (ax - r) * cell, pad + (ay - r) * cell, scene.view_k * cell, scene.view_k * cell);
      ctx.setLineDash([]);
    }

    const [nx, ny] = scene.nest;
    ctx.fillStyle = themeColor("--primary", 0.14);
    ctx.strokeStyle = themeColor("--primary", 0.8);
    ctx.lineWidth = 1.5;
    ctx.fillRect(pad + nx * cell + 3, pad + ny * cell + 3, cell - 6, cell - 6);
    ctx.strokeRect(pad + nx * cell + 3, pad + ny * cell + 3, cell - 6, cell - 6);
    ctx.font = `500 ${Math.max(9, cell * 0.2)}px Inter Variable, sans-serif`;
    ctx.fillStyle = themeColor("--primary");
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("nest", C(nx), C(ny));

    const left = new Set(remaining.map(([x, y]) => `${x},${y}`));
    for (const [fx, fy, idx] of scene.foods) {
      const present = left.has(`${fx},${fy}`);
      const isNext = present && idx === nextNeeded;
      ctx.beginPath();
      ctx.arc(C(fx), C(fy), cell * 0.26, 0, Math.PI * 2);
      if (present) {
        ctx.fillStyle = themeColor("--warning", isNext ? 0.95 : 0.55);
        ctx.fill();
      } else {
        ctx.strokeStyle = themeColor("--muted-foreground", 0.4);
        ctx.setLineDash([2, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      if (isNext) {
        ctx.strokeStyle = themeColor("--warning", 0.9);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(C(fx), C(fy), cell * 0.36, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = present ? themeColor("--background") : themeColor("--muted-foreground", 0.6);
      ctx.font = `600 ${Math.max(9, cell * 0.22)}px Inter Variable, sans-serif`;
      ctx.fillText(String(idx), C(fx), C(fy) + 0.5);
    }

    for (const [x, y, , , ttl] of a.signals) {
      ctx.fillStyle = themeColor("--info", Math.min(0.85, 0.2 + ttl / 30));
      ctx.beginPath();
      ctx.arc(pad + x * cell + cell * 0.18, pad + y * cell + cell * 0.18, Math.max(2, cell * 0.06), 0, Math.PI * 2);
      ctx.fill();
    }

    paths.forEach((path, i) => {
      for (let j = 1; j < path.length; j++) {
        ctx.strokeStyle = themeColor("--primary", (j / path.length) * (agentIds[i] === selected ? 0.8 : 0.4));
        ctx.lineWidth = agentIds[i] === selected ? 2.5 : 1.5;
        ctx.beginPath();
        ctx.moveTo(C(path[j - 1][0]), C(path[j - 1][1]));
        ctx.lineTo(C(path[j][0]), C(path[j][1]));
        ctx.stroke();
      }
    });

    agents.forEach(([x, y, carrying], i) => {
      const isSel = agentIds[i] === selected;
      ctx.shadowColor = themeColor("--primary", 0.8);
      ctx.shadowBlur = isSel ? 14 : 6;
      ctx.fillStyle = themeColor("--primary");
      ctx.beginPath();
      ctx.arc(C(x), C(y), cell * (isSel ? 0.3 : 0.24), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = themeColor("--primary-foreground");
      ctx.font = `600 ${Math.max(9, cell * 0.22)}px Inter Variable, sans-serif`;
      ctx.fillText(agentIds[i], C(x), C(y) + 0.5);
      if (carrying > 0) {
        ctx.fillStyle = themeColor("--warning");
        ctx.beginPath();
        ctx.arc(C(x) + cell * 0.24, C(y) - cell * 0.24, Math.max(3, cell * 0.09), 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }, [scene, agents.flat().join(","), a, paths, selected, resolvedTheme]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const cell = (size - 20) / Math.max(W, H);
    const gx = (e.clientX - rect.left - 10) / cell - 0.5;
    const gy = (e.clientY - rect.top - 10) / cell - 0.5;
    let best = -1;
    let bestD = 0.6;
    agents.forEach(([x, y], i) => {
      const d = Math.hypot(x - gx, y - gy);
      if (d < bestD) { bestD = d; best = i; }
    });
    if (best >= 0) onSelect(agentIds[best]);
  };

  return (
    <div ref={wrap} className="flex aspect-square w-full items-center justify-center">
      <canvas ref={canvas} style={{ width: size, height: size }} className="cursor-crosshair rounded-lg" onClick={pick} aria-label="Foraging grid" role="img" />
    </div>
  );
}
