/**
 * The contract between a world (ant colony, tumor, ...) and the shared viewport.
 *
 * A world adapter converts its backend's run format into a ViewModel once;
 * everything in core/ reads only this shape. Scene units: 1 unit = 1 grid cell
 * (or whatever the world chooses), y is up, the ground is the y = 0 plane.
 */

export type Vec3 = [number, number, number];

/** One agent (or any tracked thing: food, cells...) at one integer step. */
export interface AgentState {
  id: string;
  kind: string;
  pos: Vec3;
  /** World-specific attributes (carrying, is_llm, payload...). Read by styles. */
  attrs?: Record<string, unknown>;
}

/** Something that happened at a step and place: a delivery, a transaction, a kill. */
export interface WorldEvent {
  step: number;
  pos: Vec3;
  kind: string;
  data?: Record<string, unknown>;
}

/** A scalar field sampled on a grid at some steps (not necessarily every step). */
export interface FieldSeries {
  /** Cells along x and z; values are row-major with index = z * width + x. */
  width: number;
  height: number;
  /** Scene position of cell (0, 0)'s center, and the size of one cell. */
  origin: Vec3;
  cellSize: number;
  snapshots: Array<{ step: number; values: Float32Array; max: number }>;
}

export interface ViewModel {
  bounds: { min: Vec3; max: Vec3 };
  /** Number of recorded steps; valid steps are 0 .. steps - 1. */
  steps: number;
  /** All tracked things at each step. */
  frames: AgentState[][];
  fields: Record<string, FieldSeries>;
  events: WorldEvent[];
}
