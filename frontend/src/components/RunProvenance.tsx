import { useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";

type RunProvenanceProps = {
  runId?: string;
  provenance?: Record<string, any>;
  apiBaseUrl: string;
  isPreviewMode: boolean;
};

export function RunProvenance({
  runId,
  provenance,
  apiBaseUrl,
  isPreviewMode,
}: RunProvenanceProps) {
  const [retrieved, setRetrieved] = useState<Record<string, any> | null>(null);
  const [retrieving, setRetrieving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!runId || !provenance) return null;

  const record = retrieved ?? provenance;
  const publicValues = record.public_values ?? {};

  const retrieveRun = async () => {
    if (isPreviewMode) return;
    setRetrieving(true);
    setError(null);
    try {
      const response = await axios.get(`${apiBaseUrl}/simulation/tumor/runs/${runId}`);
      setRetrieved(response.data.provenance ?? response.data);
    } catch (cause: any) {
      setError(cause.response?.data?.detail?.message ?? cause.message ?? "Retrieval failed");
    } finally {
      setRetrieving(false);
    }
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${runId}-provenance.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-6 mt-4 rounded-lg border bg-white/80 p-4 shadow-sm dark:bg-slate-800/80">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Run provenance</p>
          <p className="font-mono text-xs break-all">{runId}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={retrieveRun} disabled={retrieving || isPreviewMode}>
            {retrieving ? "Retrieving…" : "Retrieve"}
          </Button>
          <Button size="sm" variant="outline" onClick={exportJson}>Export JSON</Button>
        </div>
      </div>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-5">
        <div><span className="text-muted-foreground">Trust tier</span><div className="font-semibold">{record.trust_tier ?? "unknown"}</div></div>
        <div><span className="text-muted-foreground">Proof staged</span><div className="font-semibold">{String(record.proof_staged ?? false)}</div></div>
        <div><span className="text-muted-foreground">Proof OK</span><div className="font-semibold">{String(record.proof_ok ?? false)}</div></div>
        <div className="lg:col-span-2"><span className="text-muted-foreground">Config hash</span><div className="font-mono break-all">{record.config_hash ?? "unknown"}</div></div>
      </div>
      <div className="mt-3 rounded bg-slate-100 p-2 font-mono text-[11px] dark:bg-slate-900">
        public_values: {JSON.stringify(publicValues)}
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
