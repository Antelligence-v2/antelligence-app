import { useMemo, useState, type ReactNode } from "react";
import type { Frames } from "@/api/engine";
import { cn } from "@/lib/utils";
import { Stage } from "../../core/Stage";
import { Pipeline, type Quality } from "../../core/Pipeline";
import { CameraRig } from "../../core/CameraRig";
import { CAMERA_PRESETS, type CameraPreset } from "../../core/cameraPresets";
import { usePlayhead, usePoses } from "../../core/playhead";
import { Tracks } from "../../core/tracks";
import type { ViewModel } from "../../core/model";
import type { Backend } from "../../core/quality";
import { cellToScene, foragingViewModel, type ForagingScene as ForagingSceneData } from "./adapter";
import { ForagingScene } from "./ForagingScene";

/** Everything inside the canvas (these hooks need the R3F context). */
function Scene({ model, tracks, scene, position, playing, selected, onSelect, preset, follow, quality, autoRotate }: {
  model: ViewModel;
  tracks: Tracks;
  scene: ForagingSceneData;
  position: number;
  playing: boolean;
  selected: string | null;
  onSelect: (id: string) => void;
  preset: CameraPreset;
  follow: boolean;
  quality: Quality;
  autoRotate: boolean;
}) {
  const playhead = usePlayhead(position, playing);
  const poses = usePoses(tracks, playhead);
  const [width, height] = scene.grid;
  const nest = useMemo(() => cellToScene(width, height, scene.nest[0], scene.nest[1]), [width, height, scene.nest]);
  return (
    <>
      <ForagingScene model={model} poses={poses} width={width} height={height} nest={nest} viewK={scene.view_k}
        selected={selected} onSelect={onSelect} />
      <CameraRig bounds={model.bounds} preset={preset} follow={follow ? selected : null} poses={poses} autoRotate={autoRotate} />
      <Pipeline quality={quality} />
    </>
  );
}

const pill = (active: boolean) => cn(
  "h-7 rounded-md border px-2 text-xs capitalize backdrop-blur transition-colors",
  active ? "border-primary/60 bg-primary/20 text-white" : "border-white/15 bg-black/35 text-white/70 hover:text-white",
);

/**
 * 3D replay of an engine foraging run, driven by the run page's playhead.
 * Selection is shared with the rest of the run UI (inspector, swimlanes).
 */
export default function ForagingView({ data, position, playing, selected, onSelect, fallback, className, active = true }: {
  data: Frames;
  /** The page's fractional playhead, in ticks. */
  position: number;
  playing: boolean;
  selected: string | null;
  onSelect: (agent: string) => void;
  /** Shown if the 3D renderer fails (the 2D scene). */
  fallback?: ReactNode;
  className?: string;
  /** False pauses rendering while the view is hidden. */
  active?: boolean;
}) {
  const model = useMemo(() => foragingViewModel(data), [data]);
  const tracks = useMemo(() => new Tracks(model.frames), [model]);
  const scene = data.scene as unknown as ForagingSceneData;
  const [preset, setPreset] = useState<CameraPreset>("overview");
  const [follow, setFollow] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [quality, setQuality] = useState<Quality>("high");
  const [backend, setBackend] = useState<Backend | null>(null);
  const [error, setError] = useState<string | null>(null);

  // On failure show the 2D scene, but say why: a silent fallback hides the bug.
  if (error) {
    return (
      <div className="space-y-2">
        {fallback}
        <p className="rounded-md border border-warning/40 bg-warning/10 px-2 py-1.5 font-mono text-2xs text-warning" role="alert">
          3D failed, showing 2D: {error}
        </p>
      </div>
    );
  }
  const span = Math.max(scene.grid[0], scene.grid[1]);
  return (
    <div className={cn("relative aspect-square w-full overflow-hidden rounded-lg", className)}>
      <Stage
        camera={{ position: [span * 0.55, span * 0.85, span * 0.95], fov: 40 }}
        onBackend={setBackend}
        onError={setError}
        fallback={fallback}
        active={active}
      >
        <Scene
          model={model} tracks={tracks} scene={scene}
          position={position - data.frames[0].tick} playing={playing}
          selected={selected} onSelect={onSelect}
          preset={preset} follow={follow && !!selected} quality={quality} autoRotate={autoRotate}
        />
      </Stage>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-center gap-1 p-2">
        <div className="pointer-events-auto flex flex-wrap gap-1">
          {CAMERA_PRESETS.map((p) => (
            <button key={p} type="button" aria-pressed={preset === p && !follow} className={pill(preset === p && !follow)} onClick={() => { setFollow(false); setPreset(p); }}>{p}</button>
          ))}
          <button type="button" className={pill(autoRotate)} aria-pressed={autoRotate} onClick={() => setAutoRotate((v) => !v)}>orbit</button>
          {selected && (
            <button type="button" className={pill(follow)} aria-pressed={follow} onClick={() => setFollow((v) => !v)}>follow {selected}</button>
          )}
        </div>
        <div className="pointer-events-auto ml-auto flex items-center gap-1">
          <button type="button" aria-pressed={quality === "high"} className={pill(quality === "high")} title="Ambient occlusion on/off"
            onClick={() => setQuality((q) => (q === "high" ? "low" : "high"))}>
            {quality === "high" ? "fx high" : "fx low"}
          </button>
          <span className="rounded border border-white/15 bg-black/35 px-1.5 py-0.5 font-mono text-[10px] uppercase text-white/60 backdrop-blur"
            title="Rendering backend">{backend ?? "…"}</span>
        </div>
      </div>
    </div>
  );
}
