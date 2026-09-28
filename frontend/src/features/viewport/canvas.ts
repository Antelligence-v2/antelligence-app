import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { decodeBase64 } from "./decode";

/** Theme color from a CSS variable ("--primary") as an hsl() string. */
export function themeColor(name: string, alpha = 1): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return `hsl(${v} / ${alpha})`;
}

/** Theme color as [r, g, b] (0-255), for writing pixels into ImageData. */
export function themeRgb(name: string): [number, number, number] {
  const el = document.createElement("span");
  el.style.color = themeColor(name);
  document.body.appendChild(el);
  const match = getComputedStyle(el).color.match(/\d+(\.\d+)?/g) ?? ["0", "0", "0"];
  el.remove();
  return [Number(match[0]), Number(match[1]), Number(match[2])];
}

/**
 * A square, DPR-aware canvas that redraws whenever `draw`'s inputs change.
 * Returns the ref and current CSS size so callers can hit-test clicks.
 */
export function useSquareCanvas(draw: (ctx: CanvasRenderingContext2D, size: number) => void, deps: unknown[]) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState(0);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setSize(Math.floor(Math.min(entry.contentRect.width, entry.contentRect.height))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    if (!c || size === 0) return;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(size * dpr)) {
      c.width = Math.round(size * dpr);
      c.height = Math.round(size * dpr);
    }
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);
    draw(ctx, size);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size, ...deps]);

  return { wrap, canvas, size };
}

/** Offscreen canvas holding one field frame as colored, alpha-scaled pixels. */
export function fieldImage(b64: string, nx: number, ny: number, rgb: [number, number, number]): HTMLCanvasElement | null {
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

