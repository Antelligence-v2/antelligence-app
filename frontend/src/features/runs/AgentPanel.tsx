import type { EngineEvent } from "@/api/engine";
import { StatusDot } from "@/design/StatusDot";
import { EmptyState } from "@/design/States";
import { MousePointerClick } from "lucide-react";
import { describeEvent } from "./describe";

const ORDER = ["observed", "decided", "intent_blocked", "policy_failed", "outcome", "signal_deposited", "signal_rejected", "memory_changed"];

/** What one agent saw, decided and got at the playhead's tick. */
export function AgentPanel({ agent, tick, events, onOpen }: {
  agent: string | null;
  tick: number;
  events: EngineEvent[];
  onOpen: (e: EngineEvent) => void;
}) {
  if (!agent) {
    return (
      <EmptyState icon={<MousePointerClick />} title="Pick an agent" className="m-4 border-none">
        Click a lane above to see exactly what an agent observed, decided and got back from the verifier at any tick.
      </EmptyState>
    );
  }
  const mine = events
    .filter((e) => e.agent_id === agent && e.tick === tick)
    .sort((a, b) => ORDER.indexOf(a.type) - ORDER.indexOf(b.type) || a.seq - b.seq);

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-baseline justify-between">
        <p className="font-mono text-sm font-medium text-primary">{agent}</p>
        <p className="numeric font-mono text-2xs text-muted-foreground">tick {tick}</p>
      </div>
      {mine.length === 0 ? (
        <p className="text-sm text-muted-foreground">Idle this tick.</p>
      ) : (
        <ol className="relative space-y-3 border-l pl-4">
          {mine.map((e) => {
            const view = describeEvent(e);
            return (
              <li key={e.seq} className="relative">
                <StatusDot tone={view.tone} className="absolute -left-[21px] top-1.5 ring-4 ring-card" />
                <button type="button" onClick={() => onOpen(e)} className="group w-full text-left">
                  <p className="text-xs font-medium group-hover:text-primary">{view.title}</p>
                  {view.detail && <p className="break-words text-xs text-muted-foreground">{view.detail}</p>}
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
