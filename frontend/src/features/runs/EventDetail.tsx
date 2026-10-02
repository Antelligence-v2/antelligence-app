import type { ReactNode } from "react";
import { ArrowDown, Link2 } from "lucide-react";
import type { EngineEvent } from "@/api/engine";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Hash } from "@/design/Hash";
import { StatusDot } from "@/design/StatusDot";
import { describeEvent, findOrigin } from "./describe";

/** Minimal JSON rendering with muted keys and colored scalars. */
function JsonView({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (value === null || value === undefined) return <span className="text-muted-foreground">null</span>;
  if (typeof value === "string") return <span className="break-all text-success">"{value}"</span>;
  if (typeof value === "number") return <span className="text-info">{value}</span>;
  if (typeof value === "boolean") return <span className="text-warning">{String(value)}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">[]</span>;
    if (value.every((v) => typeof v !== "object" || v === null)) {
      return <span>[{value.map((v, i) => <span key={i}>{i > 0 && ", "}<JsonView value={v} /></span>)}]</span>;
    }
    return <div className="pl-3">{value.map((v, i) => <div key={i}><JsonView value={v} depth={depth + 1} /></div>)}</div>;
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length === 0) return <span className="text-muted-foreground">{"{}"}</span>;
  return (
    <div className={depth > 0 ? "pl-3" : undefined}>
      {entries.map(([k, v]) => (
        <div key={k} className="leading-relaxed">
          <span className="text-muted-foreground">{k}: </span>
          <JsonView value={v} depth={depth + 1} />
        </div>
      ))}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] items-baseline gap-3 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/** Ids an event relies on (cites) or refers to, resolved to the events that produced them. */
function references(event: EngineEvent): string[] {
  const d = event.data;
  const ids = new Set<string>();
  for (const key of ["cites", "signal_ids", "memory_ids", "parent_ids"]) {
    const v = d[key];
    if (Array.isArray(v)) for (const id of v) if (typeof id === "string") ids.add(id);
  }
  if (typeof d.signal_id === "string") ids.add(d.signal_id);
  return [...ids];
}

export function EventDetail({ event, events, onOpen, onClose }: {
  event: EngineEvent | null;
  events: readonly EngineEvent[];
  onOpen: (e: EngineEvent) => void;
  onClose: () => void;
}) {
  const view = event ? describeEvent(event) : null;
  const refs = event ? references(event) : [];
  return (
    <Sheet open={!!event} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 shadow-e3 sm:max-w-[460px]" onOpenAutoFocus={(e) => e.preventDefault()}>
        {event && view && (
          <>
            <div className="space-y-1.5 border-b p-5 pr-12">
              <SheetTitle className="flex items-center gap-2 text-[15px]">
                <StatusDot tone={view.tone} /> {view.title}
              </SheetTitle>
              <SheetDescription className="numeric font-mono text-2xs">
                #{event.seq} · tick {event.tick} · {event.agent_id ?? "world"} · {event.type}
              </SheetDescription>
              {view.detail && <p className="text-sm text-muted-foreground">{view.detail}</p>}
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto p-5">
              <section className="space-y-2">
                <h3 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Data</h3>
                <div className="rounded-lg border bg-surface-2 p-3 font-mono text-2xs"><JsonView value={event.data} /></div>
              </section>

              {refs.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">References</h3>
                  <div className="space-y-1">
                    {refs.map((id) => {
                      const origin = findOrigin(events, id);
                      return (
                        <div key={id} className="flex items-center justify-between gap-3 rounded-md border px-2.5 py-1.5">
                          <Hash value={id} />
                          {origin ? (
                            <button type="button" onClick={() => onOpen(origin)} className="inline-flex items-center gap-1 text-2xs text-primary hover:underline">
                              <Link2 className="size-3" /> {describeEvent(origin).title} · t{origin.tick}
                            </button>
                          ) : (
                            <span className="text-2xs text-muted-foreground">not in this log</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              <section className="space-y-2">
                <h3 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Hash chain</h3>
                <div className="space-y-1.5 rounded-lg border p-3">
                  <Row label="previous"><Hash value={event.prev_hash} head={10} tail={8} /></Row>
                  <div className="pl-[100px] text-muted-foreground"><ArrowDown className="size-3" /></div>
                  <Row label="this event"><Hash value={event.hash} head={10} tail={8} /></Row>
                </div>
                <p className="text-2xs leading-relaxed text-muted-foreground">
                  Each hash covers the previous hash plus this event's canonical body. The engine re-verifies the whole chain every time the log is read, so an edited, dropped or reordered event fails to load.
                </p>
              </section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
