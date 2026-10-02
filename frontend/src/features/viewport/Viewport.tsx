import { useEffect, useState } from "react";
import type { Frames } from "@/api/engine";
import { cn } from "@/lib/utils";
import { GridScene, type GridSceneData } from "./GridScene";
import { TumorScene, type TumorSceneData } from "./TumorScene";
import { FIELD_STYLE } from "./styles";
import { frameAgentIds } from "./decode";

const Legend = ({ items }: { items: Array<[string, string]> }) => (
  <div className="flex flex-wrap gap-x-3 gap-y-1.5 text-2xs text-muted-foreground">
    {items.map(([label, cls]) => (
      <span key={label} className="inline-flex items-center gap-1.5"><span className={cn("size-2 rounded-full", cls)} />{label}</span>
    ))}
  </div>
);

/** Just the scene canvas for a run's frames (tumor or grid), no chrome. */
export function SceneCanvas({ data, position, layer, selected, onSelect }: {
  data: Frames;
  position: number;
  layer: string | null;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const agentIds = frameAgentIds(data);
  return (data.scene.kind as string) === "tumor" ? (
    <TumorScene scene={data.scene as unknown as TumorSceneData} frames={data.frames} position={position} layer={layer} agentIds={agentIds} selected={selected} onSelect={onSelect} />
  ) : (
    <GridScene scene={data.scene as unknown as GridSceneData} frames={data.frames} position={position} agentIds={agentIds} selected={selected} onSelect={onSelect} />
  );
}

/**
 * Spatial replay of a run from its recorded frames, driven by the playhead.
 * Click an agent to select it (shared with the inspector).
 */
export function Viewport({ data, position, tick, selected, onSelect }: {
  data: Frames;
  position: number;
  tick: number;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const kind = data.scene.kind as string;
  const fields = ((data.scene.fields as string[] | undefined) ?? []).filter((f) => FIELD_STYLE[f]);
  const [layer, setLayer] = useState<string | null>(fields.includes("drug") ? "drug" : fields[0] ?? null);
  useEffect(() => { if (layer && !fields.includes(layer)) setLayer(fields[0] ?? null); }, [fields, layer]);

  const frame = data.frames[Math.min(data.frames.length - 1, Math.max(0, tick - data.frames[0].tick))].world;

  return (
    <section className="surface-edge grid overflow-hidden rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="min-w-0 border-b p-3 lg:border-b-0 lg:border-r">
        <div className="mx-auto max-w-[560px]">
          <SceneCanvas data={data} position={position} layer={layer} selected={selected} onSelect={onSelect} />
        </div>
      </div>
      <aside className="space-y-5 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium">Scene</h2>
          <span className="numeric font-mono text-2xs text-muted-foreground">t{tick}</span>
        </div>

        {kind === "tumor" && fields.length > 0 && (
          <div className="space-y-2">
            <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Field</p>
            <div className="flex flex-wrap gap-1">
              {[null, ...fields].map((f) => (
                <button
                  key={f ?? "none"}
                  type="button"
                  onClick={() => setLayer(f)}
                  className={cn("h-7 rounded-md border px-2 text-xs transition-colors", layer === f ? "border-primary/50 bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {f ? FIELD_STYLE[f].label : "None"}
                </button>
              ))}
            </div>
            {layer && <p className="text-2xs text-muted-foreground">Brighter = higher concentration, scaled to this tick's range.</p>}
          </div>
        )}

        <div className="space-y-2">
          <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Legend</p>
          {kind === "tumor" ? (
            <Legend items={[["nanobot", "bg-primary"], ["viable cell", "bg-foreground/50"], ["hypoxic", "bg-warning"], ["apoptotic", "bg-danger/75"], ["necrotic", "bg-muted-foreground/40"], ["vessel", "border border-danger bg-transparent"], ["signal", "bg-primary/60 rotate-45 rounded-none"]]} />
          ) : (
            <Legend items={[["agent", "bg-primary"], ["food (next = ring)", "bg-warning"], ["carrying", "bg-warning"], ["signal", "bg-info"], ["nest", "border border-primary bg-primary/15"]]} />
          )}
          <p className="text-2xs text-muted-foreground">{kind === "tumor" ? "Ring around a bot = drug payload left. Line = current target." : "Dashed square = selected agent's field of view."}</p>
        </div>

        <div className="space-y-1.5 border-t pt-4 text-xs">
          {kind === "tumor" ? (
            <>
              <Row label="Living cells" value={String((frame.cells as number[][]).filter((c) => c[2] < 2).length)} />
              <Row label="Signals live" value={String(data.frames[Math.max(0, tick - data.frames[0].tick)]?.signals.length ?? 0)} />
            </>
          ) : (
            <>
              <Row label="Delivered" value={`${frame.delivered as number} / ${(data.scene.foods as unknown[]).length}`} />
              <Row label="Next needed" value={frame.next_needed === null || frame.next_needed === undefined ? "—" : `food ${frame.next_needed as number}`} />
            </>
          )}
          <Row label="Selected" value={selected ?? "click an agent"} mono />
        </div>
      </aside>
    </section>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("numeric", mono && "font-mono text-2xs")}>{value}</span>
    </div>
  );
}
