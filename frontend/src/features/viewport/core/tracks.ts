import type { AgentState, Vec3, ViewModel } from "./model";

/** An agent's interpolated state at a fractional playhead position. */
export interface Pose {
  id: string;
  kind: string;
  pos: Vec3;
  /** Facing angle about +y; 0 faces +z. Carried over while the agent stands still. */
  heading: number;
  /** 0..1: fades in when the agent appears, out when it disappears. */
  presence: number;
  /** 0..1 progress through a move this step (0 when standing still). For gait/bob. */
  stride: number;
  attrs?: Record<string, unknown>;
}

interface Track {
  kind: string;
  /** Per step: state or undefined when absent. */
  states: Array<AgentState | undefined>;
  /** Per step: heading after that step's move (carried forward). */
  headings: Float32Array;
}

const headingOf = (from: Vec3, to: Vec3) => Math.atan2(to[0] - from[0], to[2] - from[2]);

/** Shortest-path angle interpolation. */
export function lerpAngle(a: number, b: number, t: number): number {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
}

/** Ease for step-to-step motion: a little acceleration reads as walking, not sliding. */
const ease = (t: number) => t * t * (3 - 2 * t);

/**
 * Per-id tracks over a run, precomputed once, so any fractional position can be
 * posed cheaply every frame.
 */
export class Tracks {
  private tracks = new Map<string, Track>();
  readonly steps: number;

  /** Moves longer than `maxJump` (respawns, teleports) snap instead of sliding. */
  constructor(frames: ViewModel["frames"], private maxJump = 3) {
    this.steps = frames.length;
    frames.forEach((frame, step) => {
      for (const state of frame) {
        let track = this.tracks.get(state.id);
        if (!track) {
          track = { kind: state.kind, states: new Array(this.steps), headings: new Float32Array(this.steps) };
          this.tracks.set(state.id, track);
        }
        track.states[step] = state;
      }
    });
    for (const track of this.tracks.values()) {
      let heading = 0;
      for (let s = 0; s < this.steps; s++) {
        const prev = track.states[s - 1];
        const cur = track.states[s];
        if (prev && cur && (prev.pos[0] !== cur.pos[0] || prev.pos[2] !== cur.pos[2])) heading = headingOf(prev.pos, cur.pos);
        track.headings[s] = heading;
      }
    }
  }

  ids(): string[] {
    return [...this.tracks.keys()];
  }

  /** Pose every tracked thing at playhead `position` (fractional step). */
  poseAll(position: number, out: Pose[] = []): Pose[] {
    out.length = 0;
    const p = Math.min(Math.max(position, 0), Math.max(0, this.steps - 1));
    const a = Math.floor(p);
    const b = Math.min(a + 1, this.steps - 1);
    const t = p - a;
    for (const [id, track] of this.tracks) {
      const pose = this.pose(id, track, a, b, t);
      if (pose) out.push(pose);
    }
    return out;
  }

  private pose(id: string, track: Track, a: number, b: number, t: number): Pose | null {
    const from = track.states[a];
    const to = track.states[b];
    if (!from && !to) return null;
    if (!from) return { id, kind: track.kind, pos: to!.pos, heading: track.headings[b], presence: ease(t), stride: 0, attrs: to!.attrs };
    if (!to) return { id, kind: track.kind, pos: from.pos, heading: track.headings[a], presence: 1 - ease(t), stride: 0, attrs: from.attrs };

    const dx = to.pos[0] - from.pos[0];
    const dy = to.pos[1] - from.pos[1];
    const dz = to.pos[2] - from.pos[2];
    const moving = dx !== 0 || dy !== 0 || dz !== 0;
    const jump = Math.hypot(dx, dy, dz) > this.maxJump;
    const k = jump ? (t < 0.5 ? 0 : 1) : ease(t);
    // Turn early in the step, then walk: reads like an ant reorienting before it moves.
    const turn = moving && !jump ? Math.min(1, t * 3) : t < 0.5 ? 0 : 1;
    return {
      id,
      kind: track.kind,
      pos: [from.pos[0] + dx * k, from.pos[1] + dy * k, from.pos[2] + dz * k],
      heading: lerpAngle(track.headings[a], track.headings[b], turn),
      presence: 1,
      stride: moving && !jump ? t : 0,
      attrs: t < 0.5 ? from.attrs : to.attrs,
    };
  }
}
