import { useCallback, useEffect, useRef, useState } from "react";
import { isTypingTarget } from "@/shell/hotkeys";
import { advancePlayhead } from "./derive";

export const SPEEDS = [5, 10, 20, 40] as const;

export type Playback = {
  /** Integer tick shown in the UI. */
  tick: number;
  /** Fractional playhead, for smooth interpolation in viewports. */
  position: number;
  playing: boolean;
  speed: number;
  min: number;
  max: number;
  seek: (tick: number) => void;
  step: (delta: number) => void;
  toggle: () => void;
  setSpeed: (speed: number) => void;
};

/**
 * Tick playback driven by requestAnimationFrame. Keyboard: space play/pause,
 * ←/→ step (shift: 10), Home/End jump. Starts at `initial` (e.g. from the URL).
 */
export function usePlayback(min: number, max: number, initial?: number): Playback {
  const clamp = useCallback((t: number) => Math.min(max, Math.max(min, t)), [min, max]);
  const [position, setPosition] = useState(() => clamp(initial ?? max));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<number>(10);
  const raf = useRef<number>();
  const last = useRef<number>();

  useEffect(() => setPosition((p) => clamp(p)), [clamp]);

  useEffect(() => {
    if (!playing) return;
    last.current = undefined;
    const frame = (now: number) => {
      const elapsed = last.current === undefined ? 0 : now - last.current;
      last.current = now;
      let ended = false;
      setPosition((p) => {
        const next = advancePlayhead(p, elapsed, speed, max);
        ended = next.ended;
        return next.position;
      });
      if (ended) setPlaying(false);
      else raf.current = requestAnimationFrame(frame);
    };
    raf.current = requestAnimationFrame(frame);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [playing, speed, max]);

  const seek = useCallback((t: number) => setPosition(clamp(Math.round(t))), [clamp]);
  const step = useCallback((delta: number) => { setPlaying(false); setPosition((p) => clamp(Math.round(p) + delta)); }, [clamp]);
  const toggle = useCallback(() => {
    setPlaying((isPlaying) => {
      if (!isPlaying) setPosition((p) => (p >= max ? min : p)); // replay from the start when at the end
      return !isPlaying;
    });
  }, [min, max]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); step(e.shiftKey ? 10 : 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); step(e.shiftKey ? -10 : -1); }
      else if (e.key === "Home") { e.preventDefault(); setPlaying(false); setPosition(min); }
      else if (e.key === "End") { e.preventDefault(); setPlaying(false); setPosition(max); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, step, min, max]);

  return { tick: Math.floor(position), position, playing, speed, min, max, seek, step, toggle, setSpeed };
}
