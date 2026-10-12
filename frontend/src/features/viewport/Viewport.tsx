import { lazy, Suspense, useEffect, useState } from "react";
import type { Frames } from "@/api/engine";
import { cn } from "@/lib/utils";
import { AntColonyScene, type AntColonySceneData } from "./AntColonyScene";
import { GridScene, type GridSceneData } from "./GridScene";
import { TumorScene, type TumorSceneData } from "./TumorScene";
import { FIELD_STYLE } from "./styles";
import { frameAgentIds } from "./decode";
import { canRender3D } from "./core/quality";

// three.js loads only when someone opens the 3D view.
const ForagingView = lazy(() => import("./worlds/foraging/ForagingView"));
const TumorView = lazy(() => import("./worlds/tumor/TumorView"));

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
  if ((data.scene.kind as string) === "ant_colony") {
    return <AntColonyScene scene={data.scene as unknown as AntColonySceneData} frames={data.frames} position={position} layer={layer} selected={selected} onSelect={onSelect} />;
  }
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
export function Viewport({ data, position, tick, playing = false, selected, onSelect }: {
  data: Frames;
  position: number;
  tick: number;
  playing?: boolean;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const kind = data.scene.kind as string;
  const fields = ((data.scene.fields as string[] | undefined) ?? []).filter((f) => FIELD_STYLE[f]);
  const [layer, setLayer] = useState<string | null>(fields.includes("drug") ? "drug" : fields.includes("trail") ? "trail" : fields[0] ?? null);
  useEffect(() => { if (layer && !fields.includes(layer)) setLayer(fields[0] ?? null); }, [fields, layer]);
  const has3D = (kind === "grid" || kind === "tumor") && canRender3D();
  // Tumor runs open in 3D; the 2D view stays one click away (and is the fallback without WebGL 2).
  const [view, setView] = useState<"2d" | "3d">(kind === "tumor" ? "3d" : "2d");

  const frame = data.frames[Math.min(data.frames.length - 1, Math.max(0, tick - data.frames[0].tick))].world;

  return (
    <section className="surface-edge grid overflow-hidden rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="min-w-0 border-b p-3 lg:border-b-0 lg:border-r">
        <div className="mx-auto max-w-[560px]">
          {has3D && view === "3d" ? (
            <Suspense fallback={<div className="aspect-square w-full animate-pulse rounded-lg bg-surface-2" />}>
              {kind === "tumor" ? (
                <TumorView
                  data={data} position={position} playing={playing} layer={layer} selected={selected} onSelect={onSelect}
                  fallback={<SceneCanvas data={data} position={position} layer={layer} selected={selected} onSelect={onSelect} />}
                />
              ) : (
                <ForagingView
                  data={data} position={position} playing={playing} selected={selected} onSelect={onSelect}
                  fallback={<SceneCanvas data={data} position={position} layer={layer} selected={selected} onSelect={onSelect} />}
                />
              )}
            </Suspense>
          ) : (
            <SceneCanvas data={data} position={position} layer={layer} selected={selected} onSelect={onSelect} />
          )}
        </div>
      </div>
      <aside className="space-y-5 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium">Scene</h2>
          <span className="numeric font-mono text-2xs text-muted-foreground">t{tick}</span>
        </div>

        {has3D && (
          <div className="space-y-2">
            <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">View</p>
            <div className="flex items-center gap-0.5 rounded-md border p-0.5">
              {(["2d", "3d"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={view === v}
                  onClick={() => setView(v)}
                  className={cn("h-7 flex-1 rounded px-2 text-xs font-medium uppercase transition-colors", view === v ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {v}
                </button>
              ))}
            </div>
            {view === "3d" && <p className="text-2xs text-muted-foreground">Drag to orbit, scroll to zoom, click {kind === "tumor" ? "a nanobot" : "an ant"} to select it.</p>}
          </div>
        )}

        {(kind === "tumor" || kind === "ant_colony") && fields.length > 0 && (
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
          {kind === "ant_colony" ? (
            <Legend items={[["rule ant", "bg-primary"], ["LLM ant", "bg-info"], ["food / carrying", "bg-warning"], ["predator", "bg-danger rotate-45 rounded-none"], ["nest zone", "border border-primary bg-primary/15"]]} />
          ) : kind === "tumor" ? (
            <Legend items={[["nanobot", "bg-primary"], ["viable cell", "bg-foreground/50"], ["hypoxic", "bg-warning"], ["apoptotic", "bg-danger/75"], ["necrotic", "bg-muted-foreground/40"], ["vessel", "border border-danger bg-transparent"], ["signal", "bg-primary/60 rotate-45 rounded-none"]]} />
          ) : (
            <Legend items={[["agent", "bg-primary"], ["food (next = ring)", "bg-warning"], ["carrying", "bg-warning"], ["signal", "bg-info"], ["nest", "border border-primary bg-primary/15"]]} />
          )}
          <p className="text-2xs text-muted-foreground">{kind === "ant_colony" ? "Food dropped inside the nest zone counts as delivered. ♛ = Queen at the nest." : kind === "tumor" ? "Ring around a bot = drug payload left. Line = current target." : "Dashed square = selected agent's field of view."}</p>
        </div>

        <div className="space-y-1.5 border-t pt-4 text-xs">
          {kind === "ant_colony" ? (
            <>
              <Row label="Food left" value={String((frame.foods as unknown[]).length)} />
              <Row label="Ants alive" value={String((frame.ants as unknown[]).length)} />
              <Row label="Carrying" value={String((frame.ants as number[][]).filter((r) => r[2] > 0).length)} />
              {data.scene.queen === true && <p className="pt-1 text-2xs leading-relaxed text-muted-foreground">{String(frame.queen_report ?? "")}</p>}
            </>
          ) : kind === "tumor" ? (
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
