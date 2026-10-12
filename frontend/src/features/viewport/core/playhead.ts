import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Tracks, type Pose } from "./tracks";

/**
 * The scene's playhead as a ref read every frame (no React renders needed).
 *
 * `position` is the page's fractional playhead in frame-index units. While
 * playing it is already smooth, so the scene follows it exactly; a discrete
 * jump while paused (arrow-key step) glides over a few frames instead of
 * snapping, and long jumps (scrubbing, Home/End) cut straight there.
 */
export function usePlayhead(position: number, playing: boolean) {
  const target = useRef(position);
  const current = useRef(position);
  target.current = position;

  useFrame((_, dt) => {
    const gap = target.current - current.current;
    if (playing || Math.abs(gap) > 2 || Math.abs(gap) < 1e-3) current.current = target.current;
    else current.current += gap * Math.min(1, dt * 12);
  }, -2);

  return current;
}

/**
 * Poses for every tracked thing at the playhead, computed once per frame before
 * any consumer (swarms, camera, overlays) reads them.
 */
export function usePoses(tracks: Tracks, position: React.MutableRefObject<number>) {
  const state = useRef({ list: [] as Pose[], byId: new Map<string, Pose>() });
  useFrame(() => {
    const s = state.current;
    tracks.poseAll(position.current, s.list);
    s.byId.clear();
    for (const p of s.list) s.byId.set(p.id, p);
  }, -1);
  return state;
}

export type PoseRef = ReturnType<typeof usePoses>;
