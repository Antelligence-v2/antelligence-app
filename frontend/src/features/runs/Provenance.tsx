import { AnimatePresence, motion } from "framer-motion";
import { Check, Download, Loader2, ShieldCheck, ShieldQuestion, X } from "lucide-react";
import type { Replay, Run } from "@/api/engine";
import { Button } from "@/components/ui/button";
import { Hash } from "@/design/Hash";
import { StatusDot } from "@/design/StatusDot";
import { cn } from "@/lib/utils";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate text-right">{children}</span>
    </div>
  );
}

function Flag({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono text-2xs", ok ? "text-success" : "text-muted-foreground")}>
      {ok ? <Check className="size-3" /> : <X className="size-3" />} {label}
    </span>
  );
}

function downloadBundle(run: Run) {
  const blob = new Blob([JSON.stringify(run.bundle, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${run.run_id}.bundle.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function ReplayResult({ result }: { result: Replay }) {
  const ok = result.replay_ok;
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={cn("space-y-2 rounded-lg border p-3", ok ? "border-success/30 bg-success/[0.06]" : "border-danger/30 bg-danger/[0.06]")}
    >
      <p className={cn("flex items-center gap-2 text-sm font-medium", ok ? "text-success" : "text-danger")}>
        {ok ? <Check className="size-4" /> : <X className="size-4" />}
        {ok ? "Replay matched" : "Replay did not match"}
      </p>
      <p className="text-xs text-muted-foreground">
        {ok
          ? `The engine rebuilt this run from its spec alone and reproduced all ${result.event_count ?? "its"} events: identical trace hash.`
          : result.reason ?? "The replayed trace differs from the recorded one."}
      </p>
      {result.expected_trace_hash && (
        <div className="space-y-0.5 border-t pt-2">
          <Field label="recorded"><Hash value={result.expected_trace_hash} head={10} tail={8} /></Field>
          <Field label="replayed"><Hash value={result.replayed_trace_hash ?? "—"} head={10} tail={8} /></Field>
        </div>
      )}
    </motion.div>
  );
}

/**
 * Run-level provenance: the three hashes, the honest trust tier, the
 * publication outbox, and an independent replay check.
 */
export function Provenance({ run, verify }: {
  run: Run;
  verify: { run: () => void; pending: boolean; result: Replay | undefined; error: Error | null };
}) {
  const trust = run.bundle.trust;
  const outbox = run.outbox;
  return (
    <section id="provenance" className="surface-edge scroll-mt-6 overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-medium">Provenance</h2>
        <span className="font-mono text-2xs text-muted-foreground">{run.bundle.schema}</span>
      </div>
      <div className="grid divide-y md:grid-cols-3 md:divide-x md:divide-y-0">
        <div className="space-y-1 p-4">
          <h3 className="mb-2 text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Hashes</h3>
          <Field label="config"><Hash value={run.config_hash} /></Field>
          <Field label="trace"><Hash value={run.trace_hash} /></Field>
          <Field label="bundle"><Hash value={run.bundle_hash} /></Field>
          <Field label="events"><span className="numeric font-mono">{run.event_count.toLocaleString("en-US")}</span></Field>
          <Field label="scope"><Hash value={run.bundle.scope} head={14} tail={6} copy={false} /></Field>
        </div>

        <div className="space-y-3 p-4">
          <h3 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Trust</h3>
          <div className="flex items-center gap-2">
            {trust.proof_ok ? <ShieldCheck className="size-4 text-success" /> : <ShieldQuestion className="size-4 text-warning" />}
            <span className="font-mono text-sm">{trust.trust_tier}</span>
          </div>
          <div className="flex gap-3">
            <Flag ok={trust.proof_ok} label="proof" />
            <Flag ok={trust.onchain_ok} label="on-chain" />
          </div>
          {trust.note && <p className="text-xs leading-relaxed text-muted-foreground">{trust.note}</p>}
          {outbox && (
            <div className="flex items-center justify-between border-t pt-3 text-xs">
              <span className="text-muted-foreground">Publication outbox</span>
              <span className="inline-flex items-center gap-1.5 font-mono">
                <StatusDot tone={outbox.status === "published" ? "success" : outbox.status === "failed" ? "danger" : "warning"} />
                {outbox.status}{outbox.attempts ? ` · ${outbox.attempts} tries` : ""}
              </span>
            </div>
          )}
        </div>

        <div className="space-y-3 p-4">
          <h3 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Independent check</h3>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Rebuild the run from its spec in a fresh scheduler and compare the resulting trace hash with the recorded one.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={verify.run} disabled={verify.pending}>
              {verify.pending ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
              {verify.pending ? "Replaying…" : "Verify replay"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => downloadBundle(run)}>
              <Download /> Bundle
            </Button>
          </div>
          <AnimatePresence mode="wait">
            {verify.result && <ReplayResult key={String(verify.result.replay_ok)} result={verify.result} />}
          </AnimatePresence>
          {verify.error && <p className="text-xs text-danger">{verify.error.message}</p>}
        </div>
      </div>
    </section>
  );
}
