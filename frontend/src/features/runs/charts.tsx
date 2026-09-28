import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Pt = { x: number; y: number | null };

function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** Index of the last tick <= t (ticks ascending), or -1. */
function indexAtOrBefore(ticks: number[], t: number): number {
  let i = -1;
  for (let k = 0; k < ticks.length && ticks[k] <= t; k++) i = k;
  return i;
}

function extent(values: Array<number | null>): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) if (v !== null) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  if (!Number.isFinite(lo)) return [0, 1];
  if (lo === hi) return [lo - 1, hi + 1];
  return [lo, hi];
}

/** Line + soft area path through non-null points; gaps break the line. */
function paths(points: Pt[], sx: (x: number) => number, sy: (y: number) => number, baseline: number) {
  let line = "";
  let area = "";
  let run: Pt[] = [];
  const flush = () => {
    if (run.length === 0) return;
    const seg = run.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(2)},${sy(p.y!).toFixed(2)}`).join("");
    line += seg;
    area += `${seg}L${sx(run[run.length - 1].x).toFixed(2)},${baseline}L${sx(run[0].x).toFixed(2)},${baseline}Z`;
    run = [];
  };
  for (const p of points) {
    if (p.y === null) flush();
    else run.push(p);
  }
  flush();
  return { line, area };
}

/** Tiny inline trend line for KPI tiles, with a dot at the current tick. */
export function Sparkline({ ticks, values, cursor, className }: { ticks: number[]; values: Array<number | null>; cursor?: number; className?: string }) {
  const gradient = useId();
  const w = 120;
  const h = 32;
  const [lo, hi] = extent(values);
  const x0 = ticks[0] ?? 0;
  const x1 = ticks[ticks.length - 1] ?? 1;
  const sx = (x: number) => (x1 === x0 ? w / 2 : ((x - x0) / (x1 - x0)) * w);
  const sy = (y: number) => h - 2 - ((y - lo) / (hi - lo)) * (h - 4);
  const { line, area } = paths(ticks.map((x, i) => ({ x, y: values[i] })), sx, sy, h);
  const ci = cursor === undefined ? -1 : indexAtOrBefore(ticks, cursor);
  const cy = ci >= 0 ? values[ci] : null;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={cn("h-8 w-full overflow-visible", className)} aria-hidden>
      <defs>
        <linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.22" />
          <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradient})`} />
      <path d={line} fill="none" stroke="hsl(var(--primary))" strokeWidth="1.25" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      {ci >= 0 && cy !== null && <circle cx={sx(ticks[ci])} cy={sy(cy)} r="2.2" fill="hsl(var(--primary))" vectorEffect="non-scaling-stroke" />}
    </svg>
  );
}

/**
 * Metric-over-ticks chart: area + line, 3 y gridlines, playhead cursor, hover
 * readout. Click to seek. Pure SVG so the cursor tracks playback at 60 fps.
 */
export function TimeSeriesChart({ ticks, values, cursor, onSeek, format, height = 220 }: {
  ticks: number[];
  values: Array<number | null>;
  cursor: number;
  onSeek: (tick: number) => void;
  format: (v: number) => string;
  height?: number;
}) {
  const gradient = useId();
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 44, r: 12, t: 12, b: 24 };
  const w = Math.max(0, width - pad.l - pad.r);
  const h = height - pad.t - pad.b;
  const [lo, hi] = useMemo(() => extent(values), [values]);
  const x0 = ticks[0] ?? 0;
  const x1 = ticks[ticks.length - 1] ?? 1;
  const sx = (x: number) => pad.l + (x1 === x0 ? w / 2 : ((x - x0) / (x1 - x0)) * w);
  const sy = (y: number) => pad.t + h - ((y - lo) / (hi - lo)) * h;
  const { line, area } = useMemo(
    () => paths(ticks.map((x, i) => ({ x, y: values[i] })), sx, sy, pad.t + h),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ticks, values, width, lo, hi],
  );
  const tickAtX = (clientX: number, rect: DOMRect) => {
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left - pad.l) / Math.max(1, w)));
    return Math.round(x0 + ratio * (x1 - x0));
  };
  const shown = hover ?? cursor;
  const idx = indexAtOrBefore(ticks, shown);
  const shownValue = idx >= 0 ? values[idx] : null;
  const gridYs = [lo, (lo + hi) / 2, hi];
  const xTicks = Array.from(new Set([x0, Math.round(x0 + (x1 - x0) / 2), x1]));

  return (
    <div ref={ref} className="relative select-none" style={{ height }}>
      {width > 0 && (
        <svg
          width={width}
          height={height}
          className="cursor-crosshair"
          onMouseMove={(e) => setHover(tickAtX(e.clientX, e.currentTarget.getBoundingClientRect()))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => onSeek(tickAtX(e.clientX, e.currentTarget.getBoundingClientRect()))}
        >
          <defs>
            <linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.18" />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
            </linearGradient>
          </defs>
          {gridYs.map((y, i) => (
            <g key={i}>
              <line x1={pad.l} x2={pad.l + w} y1={sy(y)} y2={sy(y)} stroke="hsl(var(--border))" strokeDasharray={i === 0 ? undefined : "2 4"} />
              <text x={pad.l - 8} y={sy(y)} dy="0.32em" textAnchor="end" className="fill-muted-foreground font-mono text-[10px]">{format(y)}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} x={sx(t)} y={height - 6} textAnchor="middle" className="fill-muted-foreground font-mono text-[10px]">{t}</text>
          ))}
          <path d={area} fill={`url(#${gradient})`} />
          <path d={line} fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
          <line x1={sx(cursor)} x2={sx(cursor)} y1={pad.t} y2={pad.t + h} stroke="hsl(var(--foreground))" strokeOpacity="0.5" />
          {hover !== null && hover !== cursor && (
            <line x1={sx(hover)} x2={sx(hover)} y1={pad.t} y2={pad.t + h} stroke="hsl(var(--foreground))" strokeOpacity="0.18" strokeDasharray="3 3" />
          )}
          {idx >= 0 && shownValue !== null && (
            <circle cx={sx(ticks[idx])} cy={sy(shownValue)} r="3.5" fill="hsl(var(--background))" stroke="hsl(var(--primary))" strokeWidth="1.75" />
          )}
        </svg>
      )}
      {width > 0 && idx >= 0 && shownValue !== null && (
        <div
          className="pointer-events-none absolute top-1 rounded-md border bg-popover/95 px-2 py-1 font-mono text-2xs shadow-e2 backdrop-blur"
          style={{ left: Math.min(width - 120, Math.max(pad.l, sx(ticks[idx]) + 8)) }}
        >
          <span className="text-muted-foreground">t{ticks[idx]} </span>
          <span className="numeric font-medium text-foreground">{format(shownValue)}</span>
        </div>
      )}
    </div>
  );
}
