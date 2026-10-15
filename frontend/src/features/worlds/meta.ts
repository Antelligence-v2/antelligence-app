import type { LucideIcon } from "lucide-react";
import { Brain, Bug, Network, Orbit, Route } from "lucide-react";

type WorldMeta = { title: string; icon: LucideIcon; tagline: string; /** Headline metrics on the run page, in order. */ kpis: string[] };

const META: Record<string, WorldMeta> = {
  ant_colony: { title: "Ant colony", icon: Bug, tagline: "LLM, rule or hybrid ants forage with pheromones, predators and a Queen", kpis: ["food_collected", "food_delivered", "ants_caught", "collection_rate"] },
  tumor: { title: "Tumor", icon: Brain, tagline: "LLM, rule or hybrid nanobots vs a synthetic glioblastoma", kpis: ["kill_rate", "living_cells", "deliveries", "drug_delivered"] },
  foraging: { title: "E13 benchmark", icon: Route, tagline: "Research benchmark: 3 rule agents, ordered foods (paper E13)", kpis: ["sweep_moves", "deliveries", "directed_moves", "steps_to_success"] },
  task_dag: { title: "Task DAG", icon: Network, tagline: "Partial-view planners merged under admission (E15)", kpis: ["accepted_nodes", "proposals", "unique_nodes", "unsafe_act_count"] },
};

export function worldMeta(name: string): WorldMeta {
  return META[name] ?? { title: humanize(name), icon: Orbit, tagline: "", kpis: [] };
}

/** Whether chosen option values call for LLM agents (the engine decides; this mirrors it for the UI). */
export function selectsLlm(values: Record<string, unknown>): boolean {
  return Object.values(values).some((v) => v === "LLM-Powered" || v === "Hybrid" || v === "llm");
}

/** snake_case / kebab identifiers → "Sentence case". */
export function humanize(id: string): string {
  const words = id.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const OPTION_LABELS: Record<string, string> = { llm: "LLM", rule: "Rule-based", "Rule-Based": "Rule-based", "LLM-Powered": "LLM-powered" };

/** Option values as shown on buttons: keeps "LLM" and hyphenated names intact. */
export function optionLabel(value: string): string {
  return OPTION_LABELS[value] ?? humanize(value);
}

/** Arm ids read better as title words: hive_memory_signals → "Hive memory + signals". */
export function armLabel(arm: string): string {
  return humanize(arm.replace(/_signals$/, " + signals").replace(/^hive_memory \+/, "hive memory +"));
}
