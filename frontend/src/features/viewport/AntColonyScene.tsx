import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Frame } from "@/api/engine";
import { decodeBase64, framePair, lerp } from "./decode";
import { themeColor, themeRgb, useSquareCanvas } from "./canvas";
import { FIELD_STYLE } from "./styles";

export type AntColonySceneData = {
  grid: [number, number];
  nest: [number, number];
  fields: string[];
  queen: boolean;
};

// Rows: ants [x, y, carrying, is_llm, index]; predators [x, y, energy, is_llm, index].
type Row = number[];
const TRAIL = 8;

const antId = (index: number) => `ant-${String(index).padStart(3, "0")}`;
const predatorId = (index: number) => `predator-${String(index).padStart(3, "0")}`;

/** Ants die mid-run, so rows are matched by their index column, not by position in the list. */
function byIndex(rows: Row[]): Map<number, Row> {
  return new Map(rows.map((row) => [row[4], row]));
}

function blend(from: Row[], to: Row[], t: number): Row[] {
  const next = byIndex(to);
  return from.map((row) => {
    const n = next.get(row[4]);
    if (!n) return row; // caught this tick: stays where it fell until the frame changes
    return [lerp(row[0], n[0], t), lerp(row[1], n[1], t), ...(t < 0.5 ? row.slice(2) : n.slice(2))];
  });
}

/** One pheromone frame as colored pixels, alpha scaled from zero to this frame's max. */
function fieldImage(b64: string, nx: number, ny: number, rgb: [number, number, number]): HTMLCanvasElement | null {
  const bytes = decodeBase64(b64);
  let hi = 0;
  for (const v of bytes) if (v > hi) hi = v;
  if (hi === 0) return null;
  const img = new ImageData(nx, ny);
  for (let x = 0; x < nx; x++) {
    for (let y = 0; y < ny; y++) {
      const v = bytes[x * ny + y] ?? 0; // engine layout: index = x * ny + y
      const p = (y * nx + x) * 4;
      img.data[p] = rgb[0];
      img.data[p + 1] = rgb[1];
      img.data[p + 2] = rgb[2];
      img.data[p + 3] = Math.round(Math.pow(v / 255, 0.6) * 190);
    }
  }
  const off = document.createElement("canvas");
  off.width = nx;
  off.height = ny;
  off.getContext("2d")?.putImageData(img, 0, 0);
  return off;
}

/** Ant colony: pheromone heatmap, food, nest (and Queen), ants with trails, predators. */
export function AntColonyScene({ scene, frames, position, layer, selected, onSelect }: {
  scene: AntColonySceneData;
  frames: Frame[];
  position: number;
  layer: string | null;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const { resolvedTheme } = useTheme();
  const { a, b, t } = framePair(frames, position);
  const index = frames.indexOf(a);
  const [W, H] = scene.grid;
  const ants = blend(a.world.ants as Row[], b.world.ants as Row[], t);
  const predators = blend(a.world.predators as Row[], b.world.predators as Row[], t);
  const foods = a.world.foods as number[][];

  const field = useMemo(() => {
    const encoded = layer ? (a.world.fields as Record<string, { b64: string }> | undefined)?.[layer] : undefined;
    if (!layer || !encoded) return null;
    return fieldImage(encoded.b64, W, H, themeRgb(FIELD_STYLE[layer]?.color ?? "--primary"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, layer, W, H, resolvedTheme]);

  const paths = useMemo(() => {
    const out = new Map<number, Array<[number, number]>>();
    for (let f = Math.max(0, index - TRAIL + 1); f <= index; f++) {
      for (const row of frames[f].world.ants as Row[]) {
        const path = out.get(row[4]) ?? [];
        path.push([row[0], row[1]]);
        out.set(row[4], path);
      }
    }
    return out;
  }, [frames, index]);

  const { wrap, canvas, size } = useSquareCanvas((ctx, s) => {
    const pad = 10;
    const cell = (s - pad * 2) / Math.max(W, H);
    const C = (v: number) => pad + (v + 0.5) * cell;

    ctx.fillStyle = themeColor("--surface-2");
    ctx.fillRect(pad, pad, cell * W, cell * H);
    if (field) {
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(field, pad, pad, cell * W, cell * H);
    }
    ctx.strokeStyle = themeColor("--border", 0.6);
    ctx.lineWidth = 1;
    for (let i = 0; i <= W; i++) {
      ctx.beginPath(); ctx.moveTo(pad + i * cell, pad); ctx.lineTo(pad + i * cell, pad + H * cell); ctx.stroke();
    }
    for (let j = 0; j <= H; j++) {
      ctx.beginPath(); ctx.moveTo(pad, pad + j * cell); ctx.lineTo(pad + W * cell, pad + j * cell); ctx.stroke();
    }

    // Nest: legacy drops food within 2 cells of the center, so show that zone.
    const [nx, ny] = scene.nest;
    ctx.fillStyle = themeColor("--primary", 0.08);
    ctx.fillRect(pad + (nx - 2) * cell, pad + (ny - 2) * cell, cell * 5, cell * 5);
    ctx.strokeStyle = themeColor("--primary", 0.75);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(pad + nx * cell + 2, pad + ny * cell + 2, cell - 4, cell - 4);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `600 ${Math.max(9, cell * 0.5)}px Inter Variable, sans-serif`;
    ctx.fillStyle = themeColor("--primary");
    ctx.fillText(scene.queen ? "♛" : "⌂", C(nx), C(ny) + 0.5);

    for (const [fx, fy] of foods) {
      ctx.fillStyle = themeColor("--warning", 0.9);
      ctx.beginPath();
      ctx.arc(C(fx), C(fy), Math.max(2, cell * 0.22), 0, Math.PI * 2);
      ctx.fill();
    }

    for (const [i, path] of paths) {
      const isSel = antId(i) === selected;
      for (let j = 1; j < path.length; j++) {
        ctx.strokeStyle = themeColor("--primary", (j / path.length) * (isSel ? 0.8 : 0.35));
        ctx.lineWidth = isSel ? 2.5 : 1.25;
        ctx.beginPath();
        ctx.moveTo(C(path[j - 1][0]), C(path[j - 1][1]));
        ctx.lineTo(C(path[j][0]), C(path[j][1]));
        ctx.stroke();
      }
    }

    for (const [x, y, energy, , i] of predators) {
      const isSel = predatorId(i) === selected;
      const r = cell * (isSel ? 0.42 : 0.36);
      ctx.shadowColor = themeColor("--danger", 0.8);
      ctx.shadowBlur = isSel ? 14 : 6;
      ctx.fillStyle = themeColor("--danger", 0.4 + (energy / 100) * 0.55);
      ctx.beginPath();
      ctx.moveTo(C(x), C(y) - r);
      ctx.lineTo(C(x) + r * 0.9, C(y) + r * 0.7);
      ctx.lineTo(C(x) - r * 0.9, C(y) + r * 0.7);
      ctx.closePath();
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    for (const [x, y, carrying, isLlm, i] of ants) {
      const isSel = antId(i) === selected;
      const r = cell * (isSel ? 0.3 : 0.24);
      ctx.shadowColor = themeColor("--primary", 0.8);
      ctx.shadowBlur = isSel ? 14 : 5;
      ctx.fillStyle = themeColor(isLlm ? "--info" : "--primary");
      ctx.beginPath();
      ctx.arc(C(x), C(y), r, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      if (carrying > 0) {
        ctx.fillStyle = themeColor("--warning");
        ctx.beginPath();
        ctx.arc(C(x) + r * 0.9, C(y) - r * 0.9, Math.max(2.5, cell * 0.1), 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }, [scene, ants.flat().join(","), predators.flat().join(","), a, field, paths, selected, resolvedTheme]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const cell = (size - 20) / Math.max(W, H);
    const gx = (e.clientX - rect.left - 10) / cell - 0.5;
    const gy = (e.clientY - rect.top - 10) / cell - 0.5;
    let best: string | null = null;
    let bestD = 0.7;
    for (const [x, y, , , i] of ants) {
      const d = Math.hypot(x - gx, y - gy);
      if (d < bestD) { bestD = d; best = antId(i); }
    }
    for (const [x, y, , , i] of predators) {
      const d = Math.hypot(x - gx, y - gy);
      if (d < bestD) { bestD = d; best = predatorId(i); }
    }
    if (best) onSelect(best);
  };

  return (
    <div ref={wrap} className="flex aspect-square w-full items-center justify-center">
      <canvas ref={canvas} style={{ width: size, height: size }} className="cursor-crosshair rounded-lg" onClick={pick} aria-label="Ant colony" role="img" />
    </div>
  );
}
