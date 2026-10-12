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
import { tumorViewModel, umToScene, UM, type TumorScene as TumorSceneData } from "./adapter";
import { MAX_JUMP, TumorScene3D } from "./TumorScene3D";
import { TUMOR_COLORS } from "./palette";

/** Everything inside the canvas (these hooks need the R3F context). */
function Scene({ model, tracks, scene, position, playing, layer, selected, onSelect, preset, follow, quality, autoRotate }: {
  model: ViewModel;
  tracks: Tracks;
  scene: TumorSceneData;
  position: number;
  playing: boolean;
  layer: string | null;
  selected: string | null;
  onSelect: (id: string) => void;
  preset: CameraPreset;
  follow: boolean;
  quality: Quality;
  autoRotate: boolean;
}) {
  const playhead = usePlayhead(position, playing);
  const poses = usePoses(tracks, playhead);
  const vessels = useMemo(() => scene.vessels.map(([x, y]) => umToScene(scene.center, x, y)), [scene]);
  return (
    <>
      <TumorScene3D model={model} poses={poses} playhead={playhead}
        span={(scene.domain[1] - scene.domain[0]) * UM} radius={scene.tumor_radius * UM} vessels={vessels}
        layer={layer} selected={selected} onSelect={onSelect} />
      <CameraRig bounds={model.bounds} preset={preset} follow={follow ? selected : null} poses={poses} autoRotate={autoRotate} />
      <Pipeline quality={quality} bloomStrength={1.1} />
    </>
  );
}

const pill = (active: boolean) => cn(
  "h-7 rounded-md border px-2 text-xs capitalize backdrop-blur transition-colors",
  active ? "border-primary/60 bg-primary/20 text-white" : "border-white/15 bg-black/35 text-white/70 hover:text-white",
);

const Swatch = ({ label, color }: { label: string; color: string }) => (
  <span className="inline-flex items-center gap-1.5">
    <span className="size-2 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />{label}
  </span>
);

/**
 * 3D replay of an engine tumor run, driven by the run page's playhead.
 * Selection is shared with the rest of the run UI (inspector, swimlanes).
 */
export default function TumorView({ data, position, playing, layer, selected, onSelect, fallback, className }: {
  data: Frames;
  /** The page's fractional playhead, in ticks. */
  position: number;
  playing: boolean;
  /** Field glowing through the tissue, or null. */
  layer: string | null;
  selected: string | null;
  onSelect: (agent: string) => void;
  /** Shown if the 3D renderer fails (the 2D scene). */
  fallback?: ReactNode;
  className?: string;
}) {
  const model = useMemo(() => tumorViewModel(data), [data]);
  const tracks = useMemo(() => new Tracks(model.frames, MAX_JUMP), [model]);
  const scene = data.scene as unknown as TumorSceneData;
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
  const span = (scene.domain[1] - scene.domain[0]) * UM;
  return (
    <div className={cn("relative aspect-square w-full overflow-hidden rounded-lg", className)}>
      <Stage
        camera={{ position: [span * 0.55, span * 0.85, span * 0.95], fov: 40 }}
        onBackend={setBackend}
        onError={setError}
        fallback={fallback}
      >
        <Scene
          model={model} tracks={tracks} scene={scene}
          position={position - data.frames[0].tick} playing={playing} layer={layer}
          selected={selected} onSelect={onSelect}
          preset={preset} follow={follow && !!selected} quality={quality} autoRotate={autoRotate}
        />
      </Stage>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-center gap-1 p-2">
        <div className="pointer-events-auto flex flex-wrap gap-1">
          {CAMERA_PRESETS.map((p) => (
            <button key={p} type="button" className={pill(preset === p && !follow)} onClick={() => { setFollow(false); setPreset(p); }}>{p}</button>
          ))}
          <button type="button" className={pill(autoRotate)} aria-pressed={autoRotate} onClick={() => setAutoRotate((v) => !v)}>orbit</button>
          {selected && (
            <button type="button" className={pill(follow)} aria-pressed={follow} onClick={() => setFollow((v) => !v)}>follow {selected}</button>
          )}
        </div>
        <div className="pointer-events-auto ml-auto flex items-center gap-1">
          <button type="button" className={pill(quality === "high")} title="Ambient occlusion on/off"
            onClick={() => setQuality((q) => (q === "high" ? "low" : "high"))}>
            {quality === "high" ? "fx high" : "fx low"}
          </button>
          <span className="rounded border border-white/15 bg-black/35 px-1.5 py-0.5 font-mono text-[10px] uppercase text-white/60 backdrop-blur"
            title="Rendering backend">{backend ?? "…"}</span>
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap gap-x-3 gap-y-1 bg-gradient-to-t from-black/60 to-transparent px-3 pb-2 pt-6 text-[10px] text-white/75">
        {Object.entries(TUMOR_COLORS.bot).map(([state, c]) => <Swatch key={state} label={state} color={c} />)}
        <span className="w-full" />
        {Object.entries(TUMOR_COLORS.cell).map(([phase, c]) => <Swatch key={phase} label={`${phase} cell`} color={c} />)}
        <Swatch label="vessel" color={TUMOR_COLORS.vessel} />
      </div>
    </div>
  );
}
