import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { StatusDot, type Tone } from "@/design/StatusDot";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Trust } from "@/api/engine";

const VERDICT: Record<string, { tone: Tone; label: string; help: string }> = {
  success: { tone: "success", label: "Success", help: "Goal reached with no unsafe actions applied." },
  safe_incomplete: { tone: "warning", label: "Safe · incomplete", help: "No unsafe actions, but the goal was not reached." },
  attempted_unsafe: { tone: "danger", label: "Attempted unsafe", help: "An agent attempted an unsafe action; it was blocked." },
  state_violation: { tone: "danger", label: "State violation", help: "An unsafe action was applied to the world." },
  verified_impossible: { tone: "info", label: "Verified impossible", help: "The verifier established the goal can't be reached." },
  unknown: { tone: "neutral", label: "Unknown", help: "The verifier could not classify this episode." },
};

/** Evaluator-owned verdict: never what the agents claimed. */
export function VerdictBadge({ verdict }: { verdict: string }) {
  const v = VERDICT[verdict] ?? { tone: "neutral" as Tone, label: verdict, help: "" };
  const variant = v.tone === "neutral" || v.tone === "primary" ? "secondary" : v.tone;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant={variant} className="h-6 gap-1.5 px-2 text-xs">
          <StatusDot tone={v.tone} /> {v.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-64">Verifier verdict. {v.help}</TooltipContent>
    </Tooltip>
  );
}

/** Trust tier, always explicit: local replay is not a cryptographic proof. */
export function TrustBadge({ trust }: { trust: Trust }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className="h-6 gap-1.5 px-2 font-mono text-xs">
          <ShieldCheck /> {trust.trust_tier}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-72 space-y-1">
        <p>{trust.note ?? "Provenance trust tier."}</p>
        <p className="font-mono text-muted-foreground">proof_ok {String(trust.proof_ok)} · onchain_ok {String(trust.onchain_ok)}</p>
      </TooltipContent>
    </Tooltip>
  );
}
