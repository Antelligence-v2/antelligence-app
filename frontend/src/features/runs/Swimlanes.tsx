import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import type { LaneState, Lanes } from "./describe";

const ROW = 14;
const GAP = 3;
const MAX_VISIBLE_ROWS = 14;

const STYLE: Record<LaneState, [cssVar: string, alpha: number]> = {
  observed: ["--foreground", 0.07],
  acted: ["--primary", 0.32],
  signaled: ["--primary", 0.95],
  rejected: ["--warning", 0.85],
  blocked: ["--danger", 0.95],
  failed: ["--danger", 1],
};

function cssColor(name: string, alpha: number): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return `hsl(${v} / ${alpha})`;
}

/**
 * One row per agent, one cell per tick, colored by what the agent did.
 * Canvas-rendered (tumor runs reach 40 agents × 400 ticks); click to select
 * an agent and seek to that tick.
 */
export function Swimlanes({ lanes, min, max, cursor, selected, onPick }: {
  lanes: Lanes;
  min: number;
  max: number;
  cursor: number;
  selected: string | null;
  onPick: (agent: string, tick: number) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<{ agent: string; tick: number; x: number; y: number } | null>(null);
  const { resolvedTheme } = useTheme();
  const span = Math.max(1, max - min + 1);
  const height = lanes.agents.length * (ROW + GAP);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    if (!c || width === 0) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(width * dpr);
    c.height = Math.round(height * dpr);
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const colors = Object.fromEntries(Object.entries(STYLE).map(([k, [v, a]]) => [k, cssColor(v, a)])) as Record<LaneState, string>;
    const cellW = width / span;
    const pad = cellW > 3 ? 0.5 : 0;
    lanes.agents.forEach((agent, row) => {
      const y = row * (ROW + GAP);
      if (agent === selected) {
        ctx.fillStyle = cssColor("--primary", 0.08);
        ctx.fillRect(0, y - 1, width, ROW + 2);
      }
      const cells = lanes.cells.get(agent);
      if (!cells) return;
      for (const [tick, state] of cells) {
        ctx.fillStyle = colors[state];
        ctx.fillRect((tick - min) * cellW + pad, y, Math.max(1, cellW - pad * 2), ROW);
      }
    });
    const x = ((cursor - min + 0.5) / span) * width;
    ctx.fillStyle = cssColor("--foreground", 0.7);
    ctx.fillRect(Math.round(x) - 0.5, 0, 1, height);
  }, [lanes, width, height, span, min, cursor, selected, resolvedTheme]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const row = Math.floor((e.clientY - rect.top) / (ROW + GAP));
    const tick = min + Math.floor(((e.clientX - rect.left) / rect.width) * span);
    const agent = lanes.agents[row];
    return agent === undefined ? null : { agent, tick: Math.min(max, Math.max(min, tick)), x: e.clientX - rect.left, y: row * (ROW + GAP) };
  };

  return (
    <div className="overflow-y-auto overscroll-contain pb-6" style={{ maxHeight: MAX_VISIBLE_ROWS * (ROW + GAP) + 24 }}>
    <div className="flex gap-3">
      <div className="shrink-0">
        {lanes.agents.map((agent) => (
          <button
            key={agent}
            type="button"
            onClick={() => onPick(agent, Math.round(cursor))}
            className={cn(
              "block w-20 truncate text-left font-mono text-2xs leading-[14px] transition-colors",
              agent === selected ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
            style={{ height: ROW, marginBottom: GAP }}
          >
            {agent}
          </button>
        ))}
      </div>
      <div ref={wrap} className="relative min-w-0 flex-1">
        <canvas
          ref={canvas}
          style={{ width: "100%", height }}
          className="block cursor-pointer"
          onMouseMove={(e) => setHover(pick(e))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => { const p = pick(e); if (p) onPick(p.agent, p.tick); }}
        />
        {hover && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 font-mono text-2xs shadow-e2"
            style={{ left: hover.x, top: hover.y + ROW + 4 }}
          >
            {hover.agent} · t{hover.tick} · {lanes.cells.get(hover.agent)?.get(hover.tick) ?? "idle"}
          </div>
        )}
      </div>
    </div>
    </div>
  );
}
