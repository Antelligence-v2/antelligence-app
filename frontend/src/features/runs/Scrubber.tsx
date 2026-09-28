import { useRef } from "react";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/design/Kbd";
import { cn } from "@/lib/utils";
import { SPEEDS, type Playback } from "./usePlayback";

/**
 * Transport + timeline. The track shows per-tick activity as a density strip
 * (and flags ticks with blocked intents), so interesting moments are findable.
 */
export function Scrubber({ playback, density, flagged }: {
  playback: Playback;
  density: Map<number, number>;
  flagged: Set<number>;
}) {
  const { min, max, position, tick, playing } = playback;
  const track = useRef<HTMLDivElement>(null);
  const span = Math.max(1, max - min);
  const pct = ((position - min) / span) * 100;
  const peak = Math.max(1, ...density.values());

  const seekFromPointer = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect) return;
    playback.seek(min + Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) * span);
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-0.5">
        <Button variant="ghost" size="icon-sm" aria-label="Previous tick" onClick={() => playback.step(-1)}><SkipBack /></Button>
        <Button variant="secondary" size="icon" aria-label={playing ? "Pause" : "Play"} onClick={playback.toggle} className="size-8 rounded-full">
          {playing ? <Pause className="fill-current" /> : <Play className="translate-x-px fill-current" />}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Next tick" onClick={() => playback.step(1)}><SkipForward /></Button>
      </div>

      <div
        ref={track}
        role="slider"
        tabIndex={0}
        aria-label="Tick"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={tick}
        className="group relative h-9 flex-1 cursor-pointer touch-none"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          seekFromPointer(e.clientX);
        }}
        onPointerMove={(e) => { if (e.buttons === 1) seekFromPointer(e.clientX); }}
      >
        <div className="absolute inset-x-0 top-1 flex h-4 items-end gap-px opacity-70">
          {Array.from({ length: span + 1 }, (_, i) => {
            const t = min + i;
            const d = density.get(t) ?? 0;
            return (
              <div
                key={t}
                className={cn("flex-1 rounded-[1px]", flagged.has(t) ? "bg-danger/80" : t <= tick ? "bg-primary/45" : "bg-foreground/15")}
                style={{ height: `${Math.max(8, (d / peak) * 100)}%` }}
              />
            );
          })}
        </div>
        <div className="absolute inset-x-0 bottom-2 h-1 rounded-full bg-surface-3">
          <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
        <div
          className="absolute bottom-[3px] size-3 -translate-x-1/2 rounded-full border border-primary/60 bg-foreground shadow-e2 transition-transform group-active:scale-110"
          style={{ left: `${pct}%` }}
        />
      </div>

      <div className="numeric w-24 text-right font-mono text-xs">
        <span className="text-foreground">t{tick}</span>
        <span className="text-muted-foreground"> / {max}</span>
      </div>

      <div className="hidden items-center gap-0.5 rounded-md border p-0.5 sm:flex">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => playback.setSpeed(s)}
            className={cn(
              "numeric h-6 rounded px-1.5 font-mono text-2xs transition-colors",
              playback.speed === s ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {s}/s
          </button>
        ))}
      </div>
    </div>
  );
}

export function PlaybackHints() {
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-muted-foreground">
      <span className="inline-flex items-center gap-1"><Kbd>space</Kbd> play</span>
      <span className="inline-flex items-center gap-1"><Kbd>←</Kbd><Kbd>→</Kbd> step</span>
      <span className="inline-flex items-center gap-1"><Kbd>⇧</Kbd>+<Kbd>←</Kbd> ×10</span>
      <span className="inline-flex items-center gap-1"><Kbd>home</Kbd><Kbd>end</Kbd> jump</span>
    </p>
  );
}
