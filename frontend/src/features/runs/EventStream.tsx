import { useEffect, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { X } from "lucide-react";
import type { EngineEvent } from "@/api/engine";
import { StatusDot } from "@/design/StatusDot";
import { cn } from "@/lib/utils";
import { countByType } from "./derive";
import { describeEvent, filterEvents } from "./describe";

export type StreamScope = "tick" | "all";

const TYPE_CHIPS: Array<[string, string]> = [
  ["decided", "decisions"], ["outcome", "outcomes"], ["signal_deposited", "signals"], ["memory_changed", "memory"],
  ["intent_blocked", "blocked"], ["signal_expired", "expired"], ["observed", "observations"], ["tick_ended", "ticks"],
];

const ROW_HEIGHT = 34;

/**
 * Virtualized, filterable view of the hash-chained event log. In "tick" scope
 * it follows the playhead; in "all" scope it scrolls to the playhead's tick.
 */
export function EventStream({ events, tick, scope, onScope, types, onTypes, agent, onClearAgent, onOpen, openSeq }: {
  events: EngineEvent[];
  tick: number;
  scope: StreamScope;
  onScope: (s: StreamScope) => void;
  types: Set<string>;
  onTypes: (t: Set<string>) => void;
  agent: string | null;
  onClearAgent: () => void;
  onOpen: (e: EngineEvent) => void;
  openSeq: number | null;
}) {
  const inScope = useMemo(
    () => filterEvents(events, { types: new Set(), agent, tick: scope === "tick" ? tick : null }),
    [events, agent, scope, tick],
  );
  const counts = useMemo(() => countByType(inScope), [inScope]);
  const rows = useMemo(() => filterEvents(inScope, { types, agent: null, tick: null }), [inScope, types]);
  const parent = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({ count: rows.length, getScrollElement: () => parent.current, estimateSize: () => ROW_HEIGHT, overscan: 12 });

  useEffect(() => {
    if (scope !== "all") return;
    const index = rows.findIndex((e) => e.tick >= tick);
    if (index >= 0) virtual.scrollToIndex(index, { align: "start" });
  }, [scope, tick, rows, virtual]);

  const toggleType = (type: string) => {
    const next = new Set(types);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onTypes(next);
  };

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-0.5 rounded-md border p-0.5">
          {(["tick", "all"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onScope(s)}
              className={cn("h-6 rounded px-2 text-2xs transition-colors", scope === s ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
            >
              {s === "tick" ? `Tick ${tick}` : "All ticks"}
            </button>
          ))}
        </div>
        {agent && (
          <button type="button" onClick={onClearAgent} className="inline-flex h-6 items-center gap-1 rounded-md bg-primary/12 px-2 font-mono text-2xs text-primary">
            {agent} <X className="size-3" />
          </button>
        )}
        <div className="flex flex-wrap gap-1">
          {TYPE_CHIPS.filter(([type]) => counts[type]).map(([type, label]) => (
            <button
              key={type}
              type="button"
              onClick={() => toggleType(type)}
              className={cn(
                "inline-flex h-6 items-center gap-1 rounded-md border px-1.5 text-2xs transition-colors",
                types.has(type) ? "border-primary/50 bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label} <span className="numeric font-mono opacity-70">{counts[type]}</span>
            </button>
          ))}
        </div>
      </div>

      <div ref={parent} className="h-[420px] overflow-y-auto overscroll-contain">
        {rows.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">No events match.</p>
        ) : (
          <div className="relative w-full" style={{ height: virtual.getTotalSize() }}>
            {virtual.getVirtualItems().map((item) => {
              const e = rows[item.index];
              const view = describeEvent(e);
              return (
                <button
                  key={e.seq}
                  type="button"
                  onClick={() => onOpen(e)}
                  className={cn(
                    "absolute left-0 top-0 flex w-full items-center gap-3 border-b border-border/50 px-4 text-left text-xs transition-colors hover:bg-accent/60",
                    openSeq === e.seq && "bg-accent",
                  )}
                  style={{ height: ROW_HEIGHT, transform: `translateY(${item.start}px)` }}
                >
                  <StatusDot tone={view.tone} />
                  <span className="w-36 shrink-0 truncate font-medium">{view.title}</span>
                  <span className="min-w-0 flex-1 truncate text-muted-foreground">{view.detail}</span>
                  <span className="w-16 shrink-0 truncate text-right font-mono text-2xs text-muted-foreground">{e.agent_id ?? "—"}</span>
                  <span className="numeric w-10 shrink-0 text-right font-mono text-2xs text-muted-foreground">t{e.tick}</span>
                  <span className="numeric w-12 shrink-0 text-right font-mono text-2xs text-muted-foreground/60">#{e.seq}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
