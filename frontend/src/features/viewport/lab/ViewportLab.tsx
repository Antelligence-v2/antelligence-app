import { useMemo, useState } from "react";
import { usePlayback, SPEEDS } from "@/features/runs/usePlayback";
import { Viewport } from "../Viewport";
import { demoForagingFrames } from "../worlds/foraging/demo";

/**
 * Dev-only sandbox (/viewport-lab): the real run viewport on a synthetic
 * foraging run, so the 3D view can be checked without the backend.
 * Space plays/pauses, arrows step. Append ?renderer=webgl to force the WebGL 2 fallback.
 */
export default function ViewportLab() {
  const data = useMemo(() => demoForagingFrames(), []);
  const playback = usePlayback(0, data.frames.length - 1, 0);
  const [agent, setAgent] = useState<string | null>(null);
  return (
    <div className="space-y-3 p-4">
      <header className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">Viewport lab · foraging demo</span>
        <button type="button" className="h-7 rounded-md border px-2 text-xs" onClick={playback.toggle}>{playback.playing ? "Pause" : "Play"}</button>
        {SPEEDS.map((s) => (
          <button key={s} type="button" className={`h-7 rounded-md border px-2 text-xs ${s === playback.speed ? "bg-accent" : ""}`} onClick={() => playback.setSpeed(s)}>{s} t/s</button>
        ))}
        <input type="range" min={playback.min} max={playback.max} value={playback.tick} onChange={(e) => playback.seek(Number(e.target.value))} className="w-56" aria-label="Seek" />
        <span className="font-mono text-xs text-muted-foreground">t{playback.tick} / {playback.max}</span>
      </header>
      <Viewport data={data} position={playback.position} tick={playback.tick} playing={playback.playing} selected={agent} onSelect={setAgent} />
    </div>
  );
}
