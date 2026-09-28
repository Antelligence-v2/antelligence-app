import type { LucideIcon } from "lucide-react";
import { Brain, Network, Orbit, Route } from "lucide-react";

type WorldMeta = { title: string; icon: LucideIcon; tagline: string };

const META: Record<string, WorldMeta> = {
  tumor: { title: "Tumor", icon: Brain, tagline: "Nanobot swarm vs a synthetic glioblastoma" },
  foraging: { title: "Foraging", icon: Route, tagline: "Chain-prioritized foraging on a grid (E13)" },
  task_dag: { title: "Task DAG", icon: Network, tagline: "Partial-view planners merged under admission (E15)" },
};

export function worldMeta(name: string): WorldMeta {
  return META[name] ?? { title: humanize(name), icon: Orbit, tagline: "" };
}

/** snake_case / kebab identifiers → "Sentence case". */
export function humanize(id: string): string {
  const words = id.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Arm ids read better as title words: hive_memory_signals → "Hive memory + signals". */
export function armLabel(arm: string): string {
  return humanize(arm.replace(/_signals$/, " + signals").replace(/^hive_memory \+/, "hive memory +"));
}
