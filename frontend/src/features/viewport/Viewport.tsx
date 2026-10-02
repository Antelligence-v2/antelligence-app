import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Playback } from "@/features/runs/usePlayback";
import { Skeleton } from "@/components/ui/skeleton";
import type { Frames } from "@/api/engine";
import { cn } from "@/lib/utils";
import { GridScene, type GridSceneData } from "./GridScene";
import { TumorScene, type TumorSceneData } from "./TumorScene";
import { FIELD_STYLE } from "./styles";
import { frameAgentIds } from "./decode";
import type { CameraPreset } from "./Scene3D";

// three.js + React Three Fiber load only when someone opens the 3D view.
const Scene3D = lazy(() => import("./Scene3D"));

/** Can this browser create a WebGL context at all? (Checked once.) */
let webglSupport: boolean | undefined;
function hasWebGL(): boolean {
  if (webglSupport === undefined) {
    try {
      const canvas = document.createElement("canvas");
      webglSupport = !!(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
    } catch {
      webglSupport = false;
    }
  }
  return webglSupport;
}

/** Keeps a 3D renderer failure inside the panel: report it and fall back to 2D. */
class RendererBoundary extends Component<{ onFail: (message: string) => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error) {
    this.props.onFail(error.message);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

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
export function Viewport({ data, playback, selected, onSelect }: {
  data: Frames;
  playback: Playback;
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const { position, tick } = playback;
  const kind = data.scene.kind as string;
  const fields = ((data.scene.fields as string[] | undefined) ?? []).filter((f) => FIELD_STYLE[f]);
  const [layer, setLayer] = useState<string | null>(fields.includes("drug") ? "drug" : fields[0] ?? null);
  const is3dRun = data.scene.dimensionality === 3;
  const webgl = hasWebGL();
  const [view, setView] = useState<"2d" | "3d">(is3dRun && webgl ? "3d" : "2d");
  const [renderError, setRenderError] = useState<string | null>(webgl ? null : "This browser can't create a WebGL context.");
  const [preset, setPreset] = useState<CameraPreset>("overview");
  const [autoRotate, setAutoRotate] = useState(false);
  useEffect(() => { if (layer && !fields.includes(layer)) setLayer(fields[0] ?? null); }, [fields, layer]);

  const frame = data.frames[Math.min(data.frames.length - 1, Math.max(0, tick - data.frames[0].tick))].world;

  return (
    <section className="surface-edge grid overflow-hidden rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="min-w-0 border-b p-3 lg:border-b-0 lg:border-r">
        <div className="mx-auto max-w-[560px]">
          {kind === "tumor" && view === "3d" ? (
            <RendererBoundary onFail={(message) => { setRenderError(message); setView("2d"); }}>
              <Suspense fallback={<Skeleton className="aspect-square w-full rounded-lg" />}>
                <Scene3D data={data} position={position} selected={selected} onSelect={onSelect} layer={layer} preset={preset} autoRotate={autoRotate} />
              </Suspense>
            </RendererBoundary>
          ) : (
            <SceneCanvas data={data} position={position} layer={layer} selected={selected} onSelect={onSelect} />
          )}
        </div>
      </div>
      <aside className="space-y-5 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Scene</h2>
          <span className="numeric font-mono text-2xs text-muted-foreground">t{tick} / {playback.max}</span>
        </div>
        {playback.max > playback.min && (
          <div className="flex gap-2">
            <Button size="sm" className="flex-1" onClick={playback.toggle}>
              {playback.playing ? <Pause className="fill-current" /> : <Play className="fill-current" />}
              {playback.playing ? "Pause" : playback.tick >= playback.max ? "Replay" : "Play"}
            </Button>
            <Button size="sm" variant="outline" aria-label="Restart from the first tick" onClick={() => { playback.seek(playback.min); if (!playback.playing) playback.toggle(); }}>
              <RotateCcw />
            </Button>
          </div>
        )}

        {kind === "tumor" && (
          <div className="space-y-2">
            <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">View</p>
            <div className="flex items-center gap-0.5 rounded-md border p-0.5">
              {(["2d", "3d"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  disabled={v === "3d" && !!renderError}
                  title={v === "3d" && renderError ? `3D unavailable: ${renderError}` : undefined}
                  onClick={() => setView(v)}
                  className={cn("h-7 flex-1 rounded px-2 text-xs font-medium uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-40", view === v ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {v}
                </button>
              ))}
            </div>
            {renderError && <p className="text-2xs text-warning">3D view unavailable ({renderError}). Showing 2D.</p>}
            <p className="text-2xs text-muted-foreground">
              {view === "3d"
                ? `Drag to orbit, scroll to zoom, click a bot.${is3dRun ? "" : " This run is 2D, so it lies flat; launch with dimensionality 3 for a volumetric tumor."}`
                : is3dRun ? "Top-down projection of a 3D run; fields show the slice through the tumor center." : "Top-down view."}
            </p>
          </div>
        )}

        {kind === "tumor" && view === "3d" && (
          <div className="space-y-2">
            <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Camera</p>
            <div className="flex flex-wrap gap-1">
              {(["overview", "top", "side"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPreset(p)}
                  className={cn("h-7 rounded-md border px-2 text-xs capitalize transition-colors", preset === p ? "border-primary/50 bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                aria-pressed={autoRotate}
                onClick={() => setAutoRotate((v) => !v)}
                className={cn("h-7 rounded-md border px-2 text-xs transition-colors", autoRotate ? "border-primary/50 bg-primary/10 text-foreground" : "text-muted-foreground hover:text-foreground")}
              >
                Rotate
              </button>
            </div>
          </div>
        )}

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
            {layer && (
              <p className="text-2xs text-muted-foreground">
                Brighter = higher concentration, scaled to this tick's range.{view === "3d" ? " Shown as a slice through the tumor center." : ""}
              </p>
            )}
          </div>
        )}

        <div className="space-y-2">
          <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Legend</p>
          {kind === "tumor" ? (
            <Legend items={[["nanobot", "bg-primary"], ["viable cell", "bg-foreground/50"], ["hypoxic", "bg-warning"], ["apoptotic", "bg-danger/75"], ["necrotic", "bg-muted-foreground/40"], ["vessel", "border border-danger bg-transparent"], ["signal", "bg-primary/60 rotate-45 rounded-none"]]} />
          ) : (
            <Legend items={[["agent", "bg-primary"], ["food (next = ring)", "bg-warning"], ["carrying", "bg-warning"], ["signal", "bg-info"], ["nest", "border border-primary bg-primary/15"]]} />
          )}
          <p className="text-2xs text-muted-foreground">
            {kind !== "tumor" ? "Dashed square = selected agent's field of view."
              : view === "3d" ? "Glass sphere = tumor boundary. Lines = recent paths. Dead cells shrink."
              : "Ring around a bot = drug payload left. Line = current target."}
          </p>
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
