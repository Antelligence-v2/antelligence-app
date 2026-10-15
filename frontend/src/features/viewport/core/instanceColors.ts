import { useMemo } from "react";

/**
 * Args for an `instanceColor` attribute that exists from the first render.
 * three compiles the material on the first render even with zero instances, and a
 * mesh compiled without instance colors never picks them up later (white food,
 * invisible tails). Memoized: new args would recreate the buffer every render.
 */
export function useInstanceColors(capacity: number) {
  return useMemo(() => [new Float32Array(capacity * 3).fill(1), 3] as const, [capacity]);
}
