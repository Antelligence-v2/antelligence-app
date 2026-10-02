import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Frame } from "@/api/engine";
import { decodeBase64, framePair, interpolateRows, trails } from "./decode";
import { themeColor, themeRgb, useSquareCanvas } from "./canvas";
import { FIELD_STYLE } from "./styles";

export type TumorSceneData = {
  domain: [number, number];
  center: [number, number];
  tumor_radius: number;
  vessels: Array<[number, number]>;
  field_shape: [number, number];
  fields: string[];
};


// Cell rows: [x, y, phase, id]; phases: viable, hypoxic, necrotic, apoptotic.
const CELL_STYLE: Array<[string, number, number]> = [
  ["--foreground", 0.5, 1], ["--warning", 0.85, 1], ["--muted-foreground", 0.3, 0.7], ["--danger", 0.75, 0.8],
];
const TRAIL = 14;

/** Offscreen canvas holding one field frame as colored, alpha-scaled pixels. */
function fieldImage(b64: string, nx: number, ny: number, rgb: [number, number, number]): HTMLCanvasElement | null {
  const bytes = decodeBase64(b64);
  // Stretch between this frame's own min and max so near-uniform fields (oxygen)
  // still show their structure instead of a flat slab.
  let lo = 255;
  let hi = 0;
  for (const v of bytes) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const range = hi - lo;
  if (range === 0) return null; // uniform: nothing to show
  const img = new ImageData(nx, ny);
  for (let x = 0; x < nx; x++) {
    for (let y = 0; y < ny; y++) {
      const v = bytes[x * ny + y] ?? 0; // engine layout: index = x * ny + y
      const p = (y * nx + x) * 4;
      img.data[p] = rgb[0];
      img.data[p + 1] = rgb[1];
      img.data[p + 2] = rgb[2];
      img.data[p + 3] = range > 0 ? Math.round(Math.pow((v - lo) / range, 0.8) * 150) : 0;
    }
  }
  const off = document.createElement("canvas");
  off.width = nx;
  off.height = ny;
  off.getContext("2d")?.putImageData(img, 0, 0);
  return off;
}

export function TumorScene({ scene, frames, position, layer, agentIds, selected, onSelect }: {
  scene: TumorSceneData;
  frames: Frame[];
  position: number;
  layer: string | null;
  agentIds: string[];
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const { resolvedTheme } = useTheme();
  const { a, b, t } = framePair(frames, position);
  const index = frames.indexOf(a);
  const [nx, ny] = scene.field_shape;
  const span = scene.domain[1] - scene.domain[0];

  const field = useMemo(() => {
    const encoded = layer ? (a.world.fields as Record<string, { b64: string }> | undefined)?.[layer] : undefined;
    if (!layer || !encoded) return null;
    return fieldImage(encoded.b64, nx, ny, themeRgb(FIELD_STYLE[layer]?.color ?? "--primary"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, layer, nx, ny, resolvedTheme]);

  const bots = interpolateRows(a.world.bots as number[][], b.world.bots as number[][], t, span / 6);
  const cells = a.world.cells as number[][];
  const paths = useMemo(() => trails(frames, "bots", index, TRAIL), [frames, index]);

  const { wrap, canvas, size } = useSquareCanvas((ctx, s) => {
    const pad = 10;
    const k = (s - pad * 2) / span;
    const X = (x: number) => pad + (x - scene.domain[0]) * k;
    const Y = (y: number) => pad + (y - scene.domain[0]) * k;

    ctx.fillStyle = themeColor("--surface-2");
    ctx.fillRect(pad, pad, s - pad * 2, s - pad * 2);
    if (layer && !field) {
      ctx.font = "500 11px Inter Variable, sans-serif";
      ctx.fillStyle = themeColor("--muted-foreground");
      ctx.textAlign = "center";
      ctx.fillText(`${FIELD_STYLE[layer]?.label ?? layer} is uniform at this tick`, s / 2, s - pad - 10);
      ctx.textAlign = "start";
    }
    if (field) {
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(field, pad, pad, s - pad * 2, s - pad * 2);
    }

    ctx.setLineDash([4, 5]);
    ctx.strokeStyle = themeColor("--foreground", 0.22);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(X(scene.center[0]), Y(scene.center[1]), scene.tumor_radius * k, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = themeColor("--danger", 0.8);
    ctx.lineWidth = 1.5;
    for (const [vx, vy] of scene.vessels) {
      ctx.beginPath();
      ctx.arc(X(vx), Y(vy), 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    const cellR = Math.max(2, 9 * k);
    for (const [x, y, phase] of cells) {
      const [color, alpha, scale] = CELL_STYLE[phase] ?? CELL_STYLE[0];
      ctx.fillStyle = themeColor(color, alpha);
      ctx.beginPath();
      ctx.arc(X(x), Y(y), cellR * scale, 0, Math.PI * 2);
      ctx.fill();
    }

    for (const [x, y, kind, , left] of a.signals) {
      const r = 3.5;
      ctx.fillStyle = themeColor(kind === "claimed" ? "--warning" : "--primary", Math.min(0.9, 0.25 + left / 20));
      ctx.beginPath();
      ctx.moveTo(X(x), Y(y) - r);
      ctx.lineTo(X(x) + r, Y(y));
      ctx.lineTo(X(x), Y(y) + r);
      ctx.lineTo(X(x) - r, Y(y));
      ctx.closePath();
      ctx.fill();
    }

    paths.forEach((path, i) => {
      if (path.length < 2) return;
      for (let j = 1; j < path.length; j++) {
        ctx.strokeStyle = themeColor("--primary", (j / path.length) * (agentIds[i] === selected ? 0.9 : 0.45));
        ctx.lineWidth = agentIds[i] === selected ? 2 : 1.25;
        ctx.beginPath();
        ctx.moveTo(X(path[j - 1][0]), Y(path[j - 1][1]));
        ctx.lineTo(X(path[j][0]), Y(path[j][1]));
        ctx.stroke();
      }
    });

    const cellById = new Map(cells.map((c) => [c[3], c]));
    bots.forEach(([x, y, , payload, target], i) => {
      const isSel = agentIds[i] === selected;
      const cell = target !== null && target !== undefined ? cellById.get(target) : undefined;
      if (cell) {
        ctx.strokeStyle = themeColor("--primary", isSel ? 0.7 : 0.25);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(X(x), Y(y));
        ctx.lineTo(X(cell[0]), Y(cell[1]));
        ctx.stroke();
      }
      ctx.shadowColor = themeColor("--primary", 0.9);
      ctx.shadowBlur = isSel ? 14 : 8;
      ctx.fillStyle = themeColor("--primary");
      ctx.beginPath();
      ctx.arc(X(x), Y(y), isSel ? 5.5 : 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      // Payload ring: how much drug the bot still carries (of 20).
      ctx.strokeStyle = themeColor("--foreground", 0.8);
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      ctx.arc(X(x), Y(y), isSel ? 8 : 6.5, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * Math.max(0, Math.min(1, payload / 20))));
      ctx.stroke();
      if (isSel) {
        ctx.font = "500 10px 'JetBrains Mono', monospace";
        ctx.fillStyle = themeColor("--foreground");
        ctx.fillText(agentIds[i], X(x) + 10, Y(y) - 8);
      }
    });
  }, [scene, field, layer, bots.flat().join(","), a, paths, selected, resolvedTheme]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const k = (size - 20) / span;
    let best = -1;
    let bestD = 14;
    bots.forEach(([x, y], i) => {
      const d = Math.hypot(10 + (x - scene.domain[0]) * k - (e.clientX - rect.left), 10 + (y - scene.domain[0]) * k - (e.clientY - rect.top));
      if (d < bestD) { bestD = d; best = i; }
    });
    if (best >= 0) onSelect(agentIds[best]);
  };

  return (
    <div ref={wrap} className="flex aspect-square w-full items-center justify-center">
      <canvas ref={canvas} style={{ width: size, height: size }} className="cursor-crosshair rounded-lg" onClick={pick} aria-label="Tumor scene" role="img" />
    </div>
  );
}
