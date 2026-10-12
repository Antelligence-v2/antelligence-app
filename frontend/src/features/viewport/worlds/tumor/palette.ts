/**
 * Tumor palette. The 3D scene is always a dark "under the microscope" diorama:
 * neutral tissue, crimson living cells, violet hypoxic ones, amber dying ones,
 * and nanobots that glow by what they are doing.
 */
export const TUMOR_COLORS = {
  sky: "#05040a",
  tissue: "#101116",
  tissueLight: "#1f2129",
  base: "#08080b",
  boundary: "#ff7aa8",
  vessel: "#ff2d4a",
  vesselCore: "#ffb3c0",
  trail: "#3fe0ff",
  mote: "#ff9ec4",
  cell: {
    viable: "#e8325c",
    hypoxic: "#8a4dff",
    necrotic: "#2a2530",
    apoptotic: "#ffb23e",
  },
  bot: {
    searching: "#3fe0ff",
    targeting: "#ffd84a",
    delivering: "#38ff9c",
    returning: "#5b8cff",
    reloading: "#d06bff",
  },
  signal: { found: "#3fe0ff", claimed: "#ffd84a", other: "#7fa8ff" },
  field: {
    drug: "#38ff9c",
    oxygen: "#4aa8ff",
    trail_pheromone: "#3fe0ff",
    alarm_pheromone: "#ff3d5a",
    recruitment_pheromone: "#ffc04a",
  } as Record<string, string>,
};
