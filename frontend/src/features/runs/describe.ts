/** Human-readable descriptions of engine events and per-agent lanes. Pure. */
import type { EngineEvent } from "../../api/engine.ts";

export type EventTone = "neutral" | "primary" | "success" | "warning" | "danger" | "info";
export type EventView = { title: string; detail?: string; tone: EventTone };

const str = (v: unknown) => (typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v));
const short = (id: unknown) => (typeof id === "string" && id.length > 12 ? `${id.slice(0, 8)}…` : str(id));

/** `{a: 1, b: [2, 3]}` → "a 1 · b [2,3]"; numbers trimmed so positions stay readable. */
export function inlineParams(obj: unknown): string {
  if (!obj || typeof obj !== "object") return "";
  const fmt = (v: unknown): string => {
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(1);
    if (Array.isArray(v)) return `[${v.map(fmt).join(", ")}]`;
    return str(v);
  };
  return Object.entries(obj as Record<string, unknown>).map(([k, v]) => `${k} ${fmt(v)}`).join(" · ");
}

export function describeEvent(e: EngineEvent): EventView {
  const d = e.data;
  switch (e.type) {
    case "run_started": return { title: "Run started", detail: `arm ${str(d.arm)} · seed ${str(d.seed)}`, tone: "neutral" };
    case "observed": {
      const signals = Array.isArray(d.signal_ids) ? d.signal_ids.length : 0;
      const memory = Array.isArray(d.memory_ids) ? d.memory_ids.length : 0;
      return { title: "Observed", detail: `${signals} signal${signals === 1 ? "" : "s"}${memory ? ` · ${memory} memory record${memory === 1 ? "" : "s"}` : ""}`, tone: "neutral" };
    }
    case "decided": {
      const parts = [inlineParams(d.params), d.rationale ? `“${str(d.rationale)}”` : "", Array.isArray(d.cites) && d.cites.length ? `cites ${d.cites.length}` : ""];
      return { title: `Decided ${str(d.action)}`, detail: parts.filter(Boolean).join(" · ") || undefined, tone: "primary" };
    }
    case "policy_failed": return { title: "Policy failed", detail: str(d.error ?? d.reason), tone: "danger" };
    case "outcome":
      return d.accepted
        ? { title: `Accepted ${str(d.action)}`, detail: inlineParams(d.effects) || undefined, tone: "success" }
        : { title: `Rejected ${str(d.action)}`, detail: str(d.reason) || undefined, tone: "warning" };
    case "signal_deposited":
      return { title: `Signal · ${str(d.kind)}`, detail: [inlineParams(d.payload), `ttl ${str(d.ttl)}`].filter(Boolean).join(" · "), tone: "primary" };
    case "signal_rejected": return { title: "Signal rejected", detail: str(d.reason), tone: "warning" };
    case "signal_expired": return { title: "Signal expired", detail: short(d.signal_id), tone: "neutral" };
    case "intent_blocked": return { title: `Blocked ${str(d.action)}`, detail: str(d.reason).replace(/_/g, " "), tone: "danger" };
    case "memory_changed":
      return { title: `Memory ${str(d.subject)}`, detail: `${str(d.from) || "∅"} → ${str(d.to)}${d.reason ? ` · ${str(d.reason)}` : ""}`, tone: "info" };
    case "tick_ended": return { title: "Tick ended", detail: `revision ${str(d.revision)}`, tone: "neutral" };
    case "run_finished": return { title: "Run finished", detail: str(d.stopped_reason), tone: "neutral" };
    default: return { title: e.type.replace(/_/g, " "), tone: "neutral" };
  }
}

/** What an agent did in one tick, strongest signal first. */
export type LaneState = "blocked" | "failed" | "rejected" | "signaled" | "acted" | "observed";
const RANK: Record<LaneState, number> = { failed: 6, blocked: 5, rejected: 4, signaled: 3, acted: 2, observed: 1 };

export type Lanes = { agents: string[]; cells: Map<string, Map<number, LaneState>> };

/** Natural sort so bot-2 < bot-10 and "queen" sorts after bots. */
export function naturalCompare(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

export function agentLanes(events: readonly EngineEvent[]): Lanes {
  const cells = new Map<string, Map<number, LaneState>>();
  const bump = (agent: string, tick: number, state: LaneState) => {
    let row = cells.get(agent);
    if (!row) cells.set(agent, (row = new Map()));
    const prev = row.get(tick);
    if (!prev || RANK[state] > RANK[prev]) row.set(tick, state);
  };
  for (const e of events) {
    if (!e.agent_id) continue;
    if (e.type === "intent_blocked") bump(e.agent_id, e.tick, "blocked");
    else if (e.type === "policy_failed") bump(e.agent_id, e.tick, "failed");
    else if (e.type === "outcome") bump(e.agent_id, e.tick, e.data.accepted ? "acted" : "rejected");
    else if (e.type === "signal_deposited") bump(e.agent_id, e.tick, "signaled");
    else if (e.type === "observed" || e.type === "decided") bump(e.agent_id, e.tick, "observed");
  }
  return { agents: [...cells.keys()].sort(naturalCompare), cells };
}

export type EventFilter = { types: ReadonlySet<string>; agent: string | null; tick: number | null };

export function filterEvents(events: readonly EngineEvent[], f: EventFilter): EngineEvent[] {
  return events.filter((e) =>
    (f.types.size === 0 || f.types.has(e.type)) &&
    (f.agent === null || e.agent_id === f.agent) &&
    (f.tick === null || e.tick === f.tick));
}

/** The event that produced a signal or memory record id, if it is in this log. */
export function findOrigin(events: readonly EngineEvent[], id: string): EngineEvent | undefined {
  return events.find((e) =>
    (e.type === "signal_deposited" && e.data.id === id) || (e.type === "memory_changed" && e.data.record_id === id));
}

export const LANE_LEGEND: Array<[LaneState, string]> = [
  ["acted", "acted"], ["signaled", "emitted signal"], ["rejected", "rejected"], ["blocked", "blocked"],
];
