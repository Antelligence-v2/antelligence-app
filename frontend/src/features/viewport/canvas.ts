import { useEffect, useLayoutEffect, useRef, useState } from "react";

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
