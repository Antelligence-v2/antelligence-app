import { useParams } from "react-router-dom";
import { useRun } from "@/api/queries";
import { Skeleton } from "@/components/ui/skeleton";
import { Hash } from "@/design/Hash";
import { Page, PageHeader } from "@/design/PageHeader";
import { ErrorState } from "@/design/States";

/** Minimal run summary; the full run experience lands in step 6. */
export default function RunPage() {
  const { runId = "" } = useParams();
  const run = useRun(runId);
  return (
    <Page>
      <PageHeader eyebrow="Run" title={<span className="font-mono text-xl">{runId}</span>} />
      {run.isError && <ErrorState error={run.error} onRetry={() => void run.refetch()} />}
      {run.isPending && <Skeleton className="h-40" />}
      {run.data && (
        <div className="surface-edge space-y-2 rounded-xl border bg-card p-5 text-sm">
          <p>Verdict: <span className="font-medium">{run.data.verdict.verdict}</span> · {run.data.ticks} ticks · {run.data.event_count} events</p>
          <p className="flex items-center gap-2 text-muted-foreground">trace <Hash value={run.data.trace_hash} /></p>
        </div>
      )}
    </Page>
  );
}
