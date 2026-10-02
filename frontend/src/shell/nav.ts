import type { LucideIcon } from "lucide-react";
import { Bug, Crosshair, FlaskConical, FlaskRound, GitCompareArrows, MessagesSquare, Orbit, ScanLine } from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Two-key chord shown in the palette, e.g. "g w". */
  chord?: string;
  description: string;
  /** Extra path prefixes that also mark this item active (e.g. /runs under Worlds). */
  matches?: string[];
};

/** Engine-native product surfaces. */
export const PRIMARY_NAV: NavItem[] = [
  { to: "/worlds", label: "Worlds", icon: Orbit, chord: "g w", description: "Launch runs on engine worlds", matches: ["/w", "/runs"] },
  { to: "/lab", label: "Experiments", icon: FlaskConical, chord: "g e", description: "Compare arms across seeded cases" },
  { to: "/research", label: "Research", icon: MessagesSquare, chord: "g r", description: "Compare LLM swarms on reference tasks" },
];

/** Pre-engine pages, kept reachable until they are retired (step 14). */
export const LEGACY_NAV: NavItem[] = [
  { to: "/tumor", label: "Tumor playback", icon: ScanLine, description: "Legacy single tumor run" },
  { to: "/tumor-hunt", label: "Tumor hunt", icon: Crosshair, description: "Legacy wave-spawn hunt" },
  { to: "/experiments", label: "Experiment Lab v1", icon: FlaskRound, description: "Legacy three-arm tumor experiments" },
  { to: "/ants", label: "Ant colony", icon: Bug, description: "Original ant foraging simulator" },
  { to: "/comparison", label: "Ant comparison", icon: GitCompareArrows, description: "Queen vs no-queen ant runs" },
];

function matchesPath(pathname: string, to: string): boolean {
  return to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);
}

export function isActive(pathname: string, item: Pick<NavItem, "to" | "matches">): boolean {
  return [item.to, ...(item.matches ?? [])].some((to) => matchesPath(pathname, to));
}

export function isLegacyPath(pathname: string): boolean {
  return LEGACY_NAV.some((item) => isActive(pathname, item));
}
