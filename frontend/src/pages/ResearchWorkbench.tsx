import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Download,
  FlaskConical,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  Square,
  XCircle,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BUILD_INFO, IS_PREVIEW_MODE } from "@/lib/runtime";
import {
  DEFAULT_RESEARCH_FORM,
  DEFAULT_RESEARCH_PROTOCOLS,
  buildResearchRequest,
  collectiveBehaviourViews,
  estimateResearchCalls,
  formatResearchNumber,
  formatResearchPercent,
  gateClass,
  gateLabel,
  isResearchCatalog,
  isResearchReport,
  isTerminalResearchStatus,
  researchToCsv,
  researchToJson,
  researchUsage,
  sourceCalculationLines,
  validateResearchRequest,
  type ResearchForm,
} from "@/lib/research";
import {
  apiErrorMessage,
  cancelResearchRun,
  getResearchCatalog,
  getResearchRun,
  listResearchRuns,
  startResearchRun,
} from "@/lib/researchApi";
import type {
  ResearchCatalog,
  ResearchLibraryEntry,
  ResearchModel,
  ResearchReport,
  ResearchRunsResponse,
} from "@/lib/researchTypes";

function downloadText(filename: string, text: string, type: string): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function statusTone(status: string): "default" | "destructive" | "outline" | "secondary" {
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  if (status === "running") return "secondary";
  return "outline";
}

function statusLabel(status: string): string {
  return status.split("_").join(" ");
}

function ModelIdentity({ model, selected, onToggle, disabled }: { model: ResearchModel; selected: boolean; onToggle: () => void; disabled: boolean }) {
  return (
    <label className={`block rounded-lg border p-3 transition-colors ${selected ? "border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/30" : "bg-background"} ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-indigo-400"}`}>
      <div className="flex items-start gap-3">
        <input type="checkbox" checked={selected} disabled={disabled} onChange={onToggle} className="mt-1 h-4 w-4 accent-indigo-600" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{model.label}</span>
            <Badge variant={model.availability === "ready" ? "default" : "outline"} className={model.availability === "unknown" ? "border-amber-400 text-amber-800 dark:text-amber-200" : ""}>{model.availability}</Badge>
            {model.local && <Badge variant="outline">local</Badge>}
          </div>
          <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{model.model_id}</p>
          <p className="mt-1 text-xs text-muted-foreground">{model.reason || model.provenance || "Identity is pinned by the local adapter."}</p>
        </div>
      </div>
    </label>
  );
}

function GateBadge({ gate }: { gate: string }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${gateClass(gate)}`}>{gateLabel(gate)}</span>;
}

function Builder({ catalog, form, setForm, onStart, isSubmitting, errors, active }: { catalog: ResearchCatalog | null; form: ResearchForm; setForm: (next: ResearchForm | ((current: ResearchForm) => ResearchForm)) => void; onStart: () => void; isSubmitting: boolean; errors: string[]; active: boolean }) {
  const selectedProtocols = catalog?.protocols.filter((protocol) => form.protocols.includes(protocol.id)) || [];
  const calculatedCalls = estimateResearchCalls(form.tasks_per_dataset, form.datasets.length, form.model_keys.length, selectedProtocols);
  const update = <K extends keyof ResearchForm>(key: K, value: ResearchForm[K]) => setForm((current) => ({ ...current, [key]: value }));
  const toggle = (key: "model_keys" | "protocols" | "datasets", value: string) => setForm((current) => ({ ...current, [key]: current[key].includes(value) ? current[key].filter((item) => item !== value) : [...current[key], value] }));

  return (
    <Card className="border-indigo-200 shadow-md dark:border-indigo-900">
      <CardHeader>
        <CardTitle>Build a bounded run</CardTitle>
        <CardDescription>Nothing runs until you explicitly start it. All selected IDs and limits are sent as one immutable request.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-1.5"><Label htmlFor="research-name">Run name</Label><Input id="research-name" value={form.name} maxLength={120} onChange={(event) => update("name", event.target.value)} /></div>

        <fieldset className="space-y-2"><legend className="text-sm font-medium">Local model identities</legend><p className="text-xs text-muted-foreground">Ready and unknown states stay visible. Unknown models cannot be silently substituted.</p><div className="space-y-2">{catalog?.models.map((model) => <ModelIdentity key={model.key} model={model} selected={form.model_keys.includes(model.key)} disabled={model.availability !== "ready" || active} onToggle={() => toggle("model_keys", model.key)} />) || <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">Catalog not loaded yet; private backend discovery is disabled in preview.</p>}</div></fieldset>

        <fieldset className="space-y-2"><legend className="text-sm font-medium">Public datasets</legend><div className="grid gap-2">{catalog?.datasets.map((dataset) => <label key={dataset.key} className={`rounded-lg border p-3 ${active ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-indigo-400"}`}><div className="flex items-start gap-3"><input type="checkbox" checked={form.datasets.includes(dataset.key)} disabled={active} onChange={() => toggle("datasets", dataset.key)} className="mt-1 h-4 w-4 accent-indigo-600" /><span className="min-w-0"><span className="flex flex-wrap items-center gap-2 font-semibold">{dataset.label}<Badge variant="outline" className="capitalize">{dataset.domain}</Badge></span><span className="mt-1 block text-xs text-muted-foreground">{dataset.revision} · {dataset.license} · {form.split === "development" ? dataset.development_count : dataset.evaluation_count} {form.split} examples</span><span className="mt-1 block break-all text-[11px] text-muted-foreground">{dataset.source_url}</span></span></div></label>) || <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">No dataset catalog available.</p>}</div></fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5"><Label htmlFor="research-split">Split</Label><select id="research-split" value={form.split} onChange={(event) => update("split", event.target.value as ResearchForm["split"])} disabled={active} className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"><option value="development">development</option><option value="evaluation">evaluation</option></select></div>
          <div className="space-y-1.5"><Label htmlFor="research-tasks">Tasks per dataset</Label><Input id="research-tasks" type="number" min={1} max={catalog?.limits.max_tasks_per_dataset || 50} value={form.tasks_per_dataset} disabled={active} onChange={(event) => update("tasks_per_dataset", Number(event.target.value))} /></div>
        </div>

        <div className="space-y-1.5"><Label htmlFor="research-output-policy">Output policy</Label><select id="research-output-policy" value={form.output_policy} onChange={(event) => update("output_policy", event.target.value as ResearchForm["output_policy"])} disabled={active} className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"><option value="constrained_short_v1">Constrained short JSON (repair)</option><option value="prompt_only">Prompt-only baseline</option><option value="source_calculation_v1">Source-backed arithmetic (experimental)</option></select><p className="text-xs text-muted-foreground">Source-backed arithmetic lets agents select one operation and exact source figures; code calculates the answer. Wrong figures, units, or interpretation can still produce a wrong answer. Unsupported multi-step calculations should abstain. Choice tasks retain constrained JSON. Opt-in; same token limit, no retries or fallback.</p></div>

        <fieldset className="space-y-2"><legend className="text-sm font-medium">Communication protocols</legend><div className="grid gap-2">{catalog?.protocols.map((protocol) => <label key={protocol.id} className={`rounded-lg border p-3 ${active ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:border-indigo-400"}`}><div className="flex items-start gap-3"><input type="checkbox" checked={form.protocols.includes(protocol.id)} disabled={active} onChange={() => toggle("protocols", protocol.id)} className="mt-1 h-4 w-4 accent-indigo-600" /><span><span className="flex flex-wrap items-center gap-2 font-semibold">{protocol.label}<Badge variant="secondary">{protocol.calls_per_model} calls/model</Badge></span><span className="mt-1 block text-xs text-muted-foreground">{protocol.description}</span></span></div></label>) || <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">No protocol catalog available.</p>}</div></fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5"><Label htmlFor="research-temperature">Temperature</Label><Input id="research-temperature" type="number" min={0} max={1} step={0.05} value={form.temperature} disabled={active} onChange={(event) => update("temperature", Number(event.target.value))} /></div>
          <div className="space-y-1.5"><Label htmlFor="research-seed">Seed</Label><Input id="research-seed" type="number" min={0} max={2147483647} value={form.seed} disabled={active} onChange={(event) => update("seed", Number(event.target.value))} /></div>
          <div className="space-y-1.5"><Label htmlFor="research-max-tokens">Max tokens</Label><Input id="research-max-tokens" type="number" min={64} max={512} value={form.max_tokens} disabled={active} onChange={(event) => update("max_tokens", Number(event.target.value))} /></div>
          <div className="space-y-1.5"><Label htmlFor="research-target">Target accuracy</Label><Input id="research-target" type="number" min={0} max={1} step={0.01} value={form.target_accuracy} disabled={active} onChange={(event) => update("target_accuracy", Number(event.target.value))} /></div>
          <div className="space-y-1.5"><Label htmlFor="research-max-calls">Max calls</Label><Input id="research-max-calls" type="number" min={1} max={catalog?.limits.max_calls || 600} value={form.max_calls} disabled={active} onChange={(event) => update("max_calls", Number(event.target.value))} /></div>
          <div className="space-y-1.5"><Label htmlFor="research-wall">Max wall seconds</Label><Input id="research-wall" type="number" min={1} max={catalog?.limits.max_wall_seconds || 3600} value={form.max_wall_seconds} disabled={active} onChange={(event) => update("max_wall_seconds", Number(event.target.value))} /></div>
        </div>

        <div className={`rounded-lg border p-4 ${calculatedCalls > form.max_calls ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30" : "border-indigo-200 bg-indigo-50/70 dark:border-indigo-900 dark:bg-indigo-950/30"}`}>
          <div className="flex items-center justify-between gap-3"><span className="text-sm font-medium">Calculated call budget</span><strong className="text-lg">{calculatedCalls} / {form.max_calls}</strong></div>
          <p className="mt-1 text-xs text-muted-foreground">tasks × datasets × models × protocol calls/model · default is 2 tasks × 2 domains × 2 models × 10 = 80 calls</p>
        </div>
        {errors.length > 0 && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Request needs attention</AlertTitle><AlertDescription><ul className="list-disc space-y-1 pl-4">{errors.map((error) => <li key={error}>{error}</li>)}</ul></AlertDescription></Alert>}
        <Button type="button" className="w-full gap-2" onClick={onStart} disabled={isSubmitting || active || IS_PREVIEW_MODE || !catalog}><Play className="h-4 w-4" />{isSubmitting ? "Starting…" : "Start research run"}</Button>
        {IS_PREVIEW_MODE && <p className="text-xs text-amber-700 dark:text-amber-300">Preview is read-only. Catalog, saved runs, and inference traffic stay private.</p>}
      </CardContent>
    </Card>
  );
}

function ProgressCard({ report, cancelRequested, onCancel, cancelling }: { report: ResearchReport; cancelRequested: boolean; onCancel: () => void; cancelling: boolean }) {
  const progress = report.total_cells > 0 ? Math.min(100, Math.round((report.completed_cells / report.total_cells) * 100)) : 0;
  return <Card className="border-indigo-200 dark:border-indigo-900"><CardHeader><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle className="flex flex-wrap items-center gap-2">{report.name}<Badge variant={statusTone(report.status)} className="capitalize">{statusLabel(report.status)}</Badge></CardTitle><CardDescription className="mt-1 break-all font-mono text-xs">run {report.run_id}</CardDescription>{report.execution_note && <p data-testid="execution-note" className="mt-3 rounded-md border border-amber-400 p-3 text-sm">{report.execution_note}</p>}<p className="mt-2 text-xs" data-testid="saved-output-policy">Saved output policy: <strong>{report.request.output_policy ?? "prompt_only"}</strong>{report.request.output_policy === undefined ? " (legacy)" : ""}</p></div>{!isTerminalResearchStatus(report.status) && <Button variant="destructive" size="sm" onClick={onCancel} disabled={cancelRequested || cancelling} className="gap-2">{cancelRequested || cancelling ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Square className="h-3.5 w-3.5" />}{cancelRequested ? "Cancel requested" : "Cancel run"}</Button>}</div></CardHeader><CardContent className="space-y-3"><div className="h-3 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} /></div><div className="grid gap-2 text-sm sm:grid-cols-4"><span><strong>{report.completed_cells}</strong> / {report.total_cells} cells</span><span><strong>{report.actual_calls}</strong> / {report.estimated_calls} calls</span><span>{progress}% stored progress</span><span>API cost ${formatResearchNumber(report.metered_api_cost_usd, 4)}</span></div>{cancelRequested && <p className="text-xs text-amber-700 dark:text-amber-300">Cancellation is bounded after the current call. The request remains visible until the worker reports its terminal state.</p>}</CardContent></Card>;
}

function SummaryReport({ report }: { report: ResearchReport }) {
  const usage = researchUsage(report);
  const byDomain = Array.from(new Set((report.summary || []).map((row) => row.domain)));
  return <div className="space-y-6"><Card><CardHeader><CardTitle>Domain score, coverage, and confidence gates</CardTitle><CardDescription>Rows are task-level summaries. Ballots are not independent benchmark examples; unknown and insufficient evidence stay visible.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto"><Table className="min-w-[1180px]"><TableHeader><TableRow><TableHead>Domain</TableHead><TableHead>Variant</TableHead><TableHead>Models</TableHead><TableHead>Tasks</TableHead><TableHead>Accuracy</TableHead><TableHead>Answered accuracy</TableHead><TableHead>Coverage</TableHead><TableHead>Wilson lower 95%</TableHead><TableHead>Calls</TableHead><TableHead>Tokens / seconds</TableHead><TableHead>Gate</TableHead></TableRow></TableHeader><TableBody>{report.summary.length === 0 ? <TableRow><TableCell colSpan={11} className="text-center text-muted-foreground">No summary rows yet.</TableCell></TableRow> : report.summary.map((row) => <TableRow key={`${row.domain}:${row.variant}`} className={row.gate === "unknown" || row.gate === "insufficient_evidence" ? "bg-amber-50/60 dark:bg-amber-950/20" : ""}><TableCell className="font-semibold capitalize">{row.domain}</TableCell><TableCell><div className="font-medium">{row.variant}</div><div className="text-xs text-muted-foreground">{row.protocol}</div></TableCell><TableCell className="font-mono text-xs">{row.model_keys.join(", ")}</TableCell><TableCell>{row.completed_count} / {row.task_count}</TableCell><TableCell>{formatResearchPercent(row.task_success_rate)}</TableCell><TableCell>{formatResearchPercent(row.answered_accuracy)}</TableCell><TableCell>{formatResearchPercent(row.coverage)}</TableCell><TableCell>{formatResearchPercent(row.wilson_lower_95)}</TableCell><TableCell>{row.call_count}</TableCell><TableCell className="whitespace-nowrap">{row.usage_complete ? `${row.prompt_tokens} + ${row.completion_tokens} / ${formatResearchNumber(row.elapsed_s, 2)}s` : "incomplete usage"}</TableCell><TableCell><GateBadge gate={row.gate} /></TableCell></TableRow>)}</TableBody></Table></div><div className="mt-4 grid gap-3 md:grid-cols-2">{byDomain.map((domain) => <div key={domain} className="rounded-lg border bg-muted/30 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{domain} interpretation</p><p className="mt-1 text-sm">{report.summary.filter((row) => row.domain === domain).some((row) => row.gate === "insufficient_evidence" || row.gate === "unknown") ? "Unknown / insufficient evidence is the honest result for at least one variant; the tiny sample is not accuracy validation." : "See the gate and confidence columns before interpreting the score."}</p></div>)}</div></CardContent></Card>

<Card><CardHeader><CardTitle>Actual usage comparison</CardTitle><CardDescription>{usage.note}</CardDescription></CardHeader><CardContent><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Prompt tokens" value={formatResearchNumber(usage.prompt_tokens, 0)} /><Metric label="Completion tokens" value={formatResearchNumber(usage.completion_tokens, 0)} /><Metric label="Elapsed seconds" value={formatResearchNumber(usage.elapsed_s, 2)} /><Metric label="Usage status" value={usage.complete ? "complete" : "incomplete"} /><Metric label="Metered API cost" value={report.metered_api_cost_usd === null ? "Not independently measured" : `$${formatResearchNumber(report.metered_api_cost_usd, 4)}`} /></div></CardContent></Card></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-muted/30 p-4"><p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 break-all text-xl font-semibold">{value}</p></div>;
}

function SourceCalculation({ payload }: { payload: unknown }) {
  const lines = sourceCalculationLines(payload);
  if (lines.length === 0) return null;
  return <div data-testid="source-calculation" className="rounded-md border border-indigo-300 p-3 dark:border-indigo-800"><p className="font-semibold">Source-backed calculation</p><p className="mb-2 text-muted-foreground">Arithmetic only — source relevance, units, and interpretation remain unverified.</p><ul className="space-y-1 break-words font-mono">{lines.map((line, index) => <li key={index}>{line}</li>)}</ul></div>;
}

function collectiveProtocolLabel(protocol: string): string {
  switch (protocol) {
    case "evidence_exchange": return "Evidence exchange";
    case "evidence_sources": return "Evidence sources (source-only)";
    case "evidence_isolated": return "Evidence isolated";
    case "solo_refine": return "Solo refine";
    default: return protocol;
  }
}

function CollectiveSourceList({ title, sources, senderLabel }: { title: string; sources: { id: string; text: string; sender?: string }[]; senderLabel?: (sender: string) => string }) {
  return <div className="space-y-2"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>{sources.length === 0 ? <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">Source text unavailable</p> : <ul className="space-y-2">{sources.map((source, index) => <li key={`${source.id}:${source.sender || ""}:${index}`} className="rounded-md border bg-background/70 p-3"><p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{source.text}</p>{source.sender && senderLabel && <p className="mt-2 text-xs text-muted-foreground">Shared by {senderLabel(source.sender)}</p>}</li>)}</ul>}</div>;
}

function CollectiveBehaviourPanel({ report }: { report: ResearchReport }) {
  const [selectedTask, setSelectedTask] = useState("");
  const views = collectiveBehaviourViews(report.cells || []);
  const questions = [...new Map(views.map((view) => [view.task_id, view.question])).entries()];
  const activeTask = questions.some(([id]) => id === selectedTask) ? selectedTask : questions[0]?.[0];
  if (views.length === 0) return null;
  return <Card data-testid="collective-behaviour-panel">
    <CardHeader><CardTitle>Collective behaviour</CardTitle><CardDescription>What each researcher received and how their answer changed. A changed answer is not necessarily better.</CardDescription></CardHeader>
    <CardContent className="space-y-5">
      <label className="block space-y-2 font-medium">Question to explore
        <select aria-label="Question to explore" className="block w-full min-w-0 rounded-md border bg-background p-2 text-sm" value={activeTask} onChange={(event) => setSelectedTask(event.target.value)}>
          {questions.map(([id, question], index) => <option key={id} value={id}>{index + 1}. {question}</option>)}
        </select>
      </label>
      <p className="text-lg font-semibold">{questions.find(([id]) => id === activeTask)?.[1]}</p>
      {views.filter((view) => view.task_id === activeTask).map((view) => {
        const labels = new Map(view.agents.map((agent) => [agent.agent_id, agent.label]));
        const senderLabel = (sender: string) => labels.get(sender) || "another researcher";
        return <section key={view.cell_id} data-protocol={view.protocol} className="rounded-lg border bg-muted/20 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{collectiveProtocolLabel(view.protocol)}</h3><p className="mt-1 text-sm text-muted-foreground">{view.mode_label}</p></div><Badge variant="outline">{view.agents.length} researcher{view.agents.length === 1 ? "" : "s"}</Badge></div>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">{view.agents.map((agent) => <article key={agent.agent_id} className="min-w-0 space-y-4 rounded-md border bg-background p-4">
            <h4 className="text-base font-semibold">{agent.label}</h4>
            <div className="space-y-2 text-sm"><p><span className="font-semibold">Initial answer:</span> {agent.initial_answer ?? "Answer unavailable"}</p><p><span className="font-semibold">Final answer:</span> {agent.final_answer ?? "Answer unavailable"}</p></div>
            <details><summary className="cursor-pointer text-sm font-medium">Read starting evidence ({agent.starting_sources.length} passages)</summary><div className="mt-2"><CollectiveSourceList title="Starting source passages" sources={agent.starting_sources} /></div></details>
            {agent.shared_sources.length > 0 ? <details><summary className="cursor-pointer text-sm font-medium">Read received evidence ({agent.shared_sources.length} passages)</summary><div className="mt-2"><CollectiveSourceList title="Shared source passages" sources={agent.shared_sources} senderLabel={senderLabel} /></div></details> : <p className="text-sm text-muted-foreground">No shared source passages received.</p>}
            {view.source_only && <p className="text-sm text-muted-foreground">Peers’ answers and summaries were not sent.</p>}
            {agent.received_findings.map((finding, index) => <div key={index} className="rounded-md border p-3 text-sm"><p className="font-medium">{senderLabel(finding.sender)} shared: {finding.answer ?? "abstained"}</p><p>{finding.brief}</p><p className="mt-1 text-xs text-muted-foreground">Peer claim, not a verified fact.</p></div>)}
            <details className="border-t pt-3 text-xs"><summary className="cursor-pointer text-muted-foreground">Machine identifiers and provenance</summary><div className="mt-2 space-y-1 break-all font-mono text-muted-foreground"><p>agent: {agent.agent_id}</p><p>starting IDs: {agent.initial_evidence_ids.join(", ") || "none recorded"}</p>{agent.shared_sources.map((source, index) => <p key={`${source.id}:${index}`}>shared: {source.id} · sender {source.sender || "unknown"} · message {source.message_id || "unknown"}</p>)}</div></details>
          </article>)}</div>
        </section>;
      })}
    </CardContent>
  </Card>;
}

function TraceExplorer({ report }: { report: ResearchReport }) {
  const events = useMemo(() => {
    const fromReport = report.events || [];
    if (fromReport.length > 0) return fromReport;
    return (report.cells || []).flatMap((cell) => cell.messages || []);
  }, [report.cells, report.events]);
  return <Card><CardHeader><CardTitle>Prompt / output trace explorer</CardTitle><CardDescription>Every displayed event is attributed to a task, protocol, model identity, role, and response. Short public rationale only; no private chain of thought is requested.</CardDescription></CardHeader><CardContent className="space-y-2">{events.length === 0 ? <p className="text-sm text-muted-foreground">No model events have been stored yet.</p> : events.map((event) => <details key={event.message_id} className="rounded-lg border bg-background"><summary className="cursor-pointer list-none p-3"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{event.kind}</Badge><span className="font-medium">{event.role}</span><span className="font-mono text-xs text-muted-foreground">{event.model_key} · task {event.task_id} · round {event.round}</span><span className="ml-auto text-xs text-muted-foreground">{event.usage_complete ? `${event.prompt_tokens ?? "?"}+${event.completion_tokens ?? "?"} tokens` : "usage incomplete"}</span></div></summary><div className="space-y-3 border-t p-3 text-xs"><div className="grid gap-1 break-all font-mono text-muted-foreground sm:grid-cols-2"><span>message: {event.message_id}</span><span>requested: {event.requested_model || "—"}</span><span>served: {event.served_model || "—"}</span><span>recipient: {event.recipient || "none"}</span><span>response: {event.response_id || "—"}</span><span>request hash: {event.request_hash || "—"}</span></div><div><p className="mb-1 font-semibold">Exact prompt messages</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-[11px] text-slate-100">{JSON.stringify(event.prompt_messages || [], null, 2)}</pre></div><div><p className="mb-1 font-semibold">Requested response schema · {String(event.output_policy ?? report.request.output_policy ?? "prompt_only")}</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-[11px] text-slate-100">{event.response_format ? JSON.stringify(event.response_format, null, 2) : "No constrained schema requested (prompt-only baseline)."}</pre></div><div><p className="mb-1 font-semibold">Raw model output</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-[11px] text-slate-100">{event.content || event.error || "(empty response)"}</pre></div>{(event.parse_error || event.error) && <p className="break-words text-destructive">{event.parse_error || event.error}</p>}<SourceCalculation payload={event.parse_error || event.error ? null : event.payload} />{event.payload !== undefined && <div><p className="mb-1 font-semibold">Parsed / computed payload</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-[11px]">{JSON.stringify(event.payload, null, 2)}</pre></div>}</div></details>)}</CardContent></Card>;
}

function Library({ entries, selectedId, loading, error, onRefresh, onSelect }: { entries: ResearchLibraryEntry[]; selectedId: string | null; loading: boolean; error: string | null; onRefresh: () => void; onSelect: (id: string) => void }) {
  return <Card><CardHeader className="pb-3"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-lg">Saved run library</CardTitle><CardDescription>Read-back of persisted reports. Selecting one never starts a new run.</CardDescription></div><Button variant="ghost" size="icon" aria-label="Refresh research library" disabled={loading || IS_PREVIEW_MODE} onClick={onRefresh}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button></div></CardHeader><CardContent>{error && <p className="mb-3 text-sm text-destructive">{error}</p>}{loading && entries.length === 0 && <p className="text-sm text-muted-foreground">Loading saved runs…</p>}{!loading && entries.length === 0 && !error && <p className="text-sm text-muted-foreground">No saved research runs yet.</p>}<div className="space-y-2">{entries.map((entry) => <button key={entry.run_id} type="button" onClick={() => onSelect(entry.run_id)} className={`w-full rounded-md border p-3 text-left transition-colors hover:border-indigo-400 hover:bg-indigo-50/60 dark:hover:bg-indigo-950/30 ${selectedId === entry.run_id ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40" : "bg-background"}`}><div className="flex items-start justify-between gap-2"><span className="truncate font-medium">{entry.name}</span><Badge variant={statusTone(entry.status)} className="capitalize">{statusLabel(entry.status)}</Badge></div><div className="mt-1 text-xs text-muted-foreground">{entry.completed_cells} / {entry.total_cells} cells · {new Date(entry.created_at).toLocaleString()}</div><div className="mt-1 break-all font-mono text-[10px] text-muted-foreground">{entry.run_id}</div></button>)}</div></CardContent></Card>;
}

function ReportActions({ report }: { report: ResearchReport }) {
  return <div className="flex flex-wrap gap-2"><Button variant="secondary" size="sm" onClick={() => downloadText(`${report.run_id}.json`, researchToJson(report), "application/json")} className="gap-2"><Download className="h-4 w-4" /> Export JSON</Button><Button variant="secondary" size="sm" onClick={() => downloadText(`${report.run_id}.csv`, researchToCsv(report), "text/csv;charset=utf-8")} className="gap-2"><Download className="h-4 w-4" /> Export CSV</Button></div>;
}

export default function ResearchWorkbench() {
  const navigate = useNavigate();
  const params = useParams();
  const initialRunId = useMemo(() => params.id || new URLSearchParams(window.location.search).get("run") || new URLSearchParams(window.location.search).get("run_id"), [params.id]);
  const [catalog, setCatalog] = useState<ResearchCatalog | null>(null);
  const [form, setForm] = useState<ResearchForm>({ ...DEFAULT_RESEARCH_FORM });
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [library, setLibrary] = useState<ResearchLibraryEntry[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [reportLoading, setReportLoading] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [requestErrors, setRequestErrors] = useState<string[]>([]);
  const reportGeneration = useRef(0);
  const catalogGeneration = useRef(0);
  const libraryGeneration = useRef(0);
  const pollAbort = useRef<AbortController | null>(null);
  const submitGeneration = useRef(0);

  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    if (IS_PREVIEW_MODE) return;
    const generation = ++catalogGeneration.current;
    setCatalogError(null);
    try {
      const next = await getResearchCatalog(signal);
      if (signal?.aborted || generation !== catalogGeneration.current) return;
      if (!isResearchCatalog(next)) throw new Error("The backend returned an invalid research catalog.");
      setCatalog(next);
      setForm((current) => ({
        ...current,
        model_keys: current.model_keys.length ? current.model_keys : next.models.filter((model) => model.availability === "ready").slice(0, 2).map((model) => model.key),
        protocols: current.protocols.length ? current.protocols : next.protocols.filter((protocol) => DEFAULT_RESEARCH_PROTOCOLS.includes(protocol.id as typeof DEFAULT_RESEARCH_PROTOCOLS[number])).map((protocol) => protocol.id),
        datasets: current.datasets.length ? current.datasets : next.datasets.slice(0, 2).map((dataset) => dataset.key),
      }));
    } catch (error) {
      if (!signal?.aborted && generation === catalogGeneration.current) setCatalogError(apiErrorMessage(error));
    }
  }, []);

  const loadLibrary = useCallback(async (signal?: AbortSignal) => {
    if (IS_PREVIEW_MODE) return;
    const generation = ++libraryGeneration.current;
    setLibraryLoading(true);
    setLibraryError(null);
    try {
      const next: ResearchRunsResponse = await listResearchRuns(signal);
      if (signal?.aborted || generation !== libraryGeneration.current) return;
      if (!next || !Array.isArray(next.items)) throw new Error("The backend returned an invalid research library.");
      setLibrary(next.items);
    } catch (error) {
      if (!signal?.aborted && generation === libraryGeneration.current) setLibraryError(apiErrorMessage(error));
    } finally {
      if (!signal?.aborted && generation === libraryGeneration.current) setLibraryLoading(false);
    }
  }, []);

  const pollRun = useCallback(async (runId: string, generation: number, controller: AbortController) => {
    while (!controller.signal.aborted && generation === reportGeneration.current) {
      try {
        const next = await getResearchRun(runId, controller.signal);
        if (controller.signal.aborted || generation !== reportGeneration.current || next.run_id !== runId) return;
        setReport((current) => current?.run_id === next.run_id && current.updated_at > next.updated_at ? current : next);
        setReportLoading(false);
        if (isTerminalResearchStatus(next.status)) {
          setCancelRequested(false);
          void loadLibrary();
          return;
        }
      } catch (error) {
        if (!controller.signal.aborted && generation === reportGeneration.current) {
          setRequestErrors([apiErrorMessage(error)]);
          setReportLoading(false);
        }
        return;
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, 1200));
    }
  }, [loadLibrary]);

  const loadRun = useCallback(async (runId: string) => {
    const generation = ++reportGeneration.current;
    pollAbort.current?.abort();
    const controller = new AbortController();
    pollAbort.current = controller;
    setSelectedRunId(runId);
    setReport(null);
    setCancelLoading(false);
    setReportLoading(true);
    setRequestErrors([]);
    setCancelRequested(false);
    try {
      const next = await getResearchRun(runId, controller.signal);
      if (controller.signal.aborted || generation !== reportGeneration.current || next.run_id !== runId || !isResearchReport(next)) return;
      setReport((current) => current?.run_id === next.run_id && current.updated_at > next.updated_at ? current : next);
      setReportLoading(false);
      const url = new URL(window.location.href);
      url.pathname = "/research";
      url.searchParams.set("run", runId);
      window.history.replaceState(window.history.state, "", url);
      if (!isTerminalResearchStatus(next.status)) void pollRun(runId, generation, controller);
      else void loadLibrary();
    } catch (error) {
      if (!controller.signal.aborted && generation === reportGeneration.current) {
        setRequestErrors([apiErrorMessage(error)]);
        setReportLoading(false);
      }
    }
  }, [loadLibrary, pollRun]);

  useEffect(() => {
    if (IS_PREVIEW_MODE) return;
    const controller = new AbortController();
    void loadCatalog(controller.signal);
    void loadLibrary(controller.signal);
    if (initialRunId) void loadRun(initialRunId);
    return () => {
      controller.abort();
      pollAbort.current?.abort();
    };
  }, [initialRunId, loadCatalog, loadLibrary, loadRun]);

  const startRun = async () => {
    if (IS_PREVIEW_MODE || !catalog) return;
    const request = buildResearchRequest(form);
    const errors = validateResearchRequest(request, catalog);
    setRequestErrors(errors);
    if (errors.length > 0) return;
    const generation = ++reportGeneration.current;
    const submitToken = ++submitGeneration.current;
    pollAbort.current?.abort();
    setSubmitLoading(true);
    setReport(null);
    setSelectedRunId(null);
    try {
      const started = await startResearchRun(request);
      if (generation !== reportGeneration.current || !started?.run_id || started.status !== "running") throw new Error("The backend returned an invalid running research job.");
      toast.success("Research run started.");
      await Promise.all([loadLibrary(), loadRun(started.run_id)]);
    } catch (error) {
      if (generation === reportGeneration.current) setRequestErrors([apiErrorMessage(error)]);
    } finally {
      if (submitToken === submitGeneration.current) setSubmitLoading(false);
    }
  };

  const cancelRun = async () => {
    const runId = selectedRunId;
    const generation = reportGeneration.current;
    if (!runId || !report || generation <= 0 || isTerminalResearchStatus(report.status)) return;
    setCancelRequested(true);
    setCancelLoading(true);
    try {
      const next = await cancelResearchRun(runId);
      if (generation !== reportGeneration.current || next.run_id !== runId || !isResearchReport(next)) return;
      setReport((current) => current?.run_id === next.run_id && current.updated_at > next.updated_at ? current : next);
      if (isTerminalResearchStatus(next.status)) {
        setCancelRequested(false);
        void loadLibrary();
      }
    } catch (error) {
      if (generation === reportGeneration.current) {
        setCancelRequested(false);
        setRequestErrors([apiErrorMessage(error)]);
      }
    } finally {
      if (generation === reportGeneration.current) setCancelLoading(false);
    }
  };

  const active = Boolean(report && !isTerminalResearchStatus(report.status));
  return <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-purple-100/40 text-foreground dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/40">
    <header className="border-b bg-white/85 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-950/85"><div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-8"><div className="flex items-center gap-3"><Button variant="ghost" size="sm" onClick={() => navigate("/")} className="gap-2"><ArrowLeft className="h-4 w-4" /> Home</Button><div className="hidden h-7 w-px bg-border sm:block" /><div><div className="flex items-center gap-2"><Search className="h-5 w-5 text-indigo-600" /><h1 className="text-2xl font-bold tracking-tight">Swarm Research Workbench</h1></div><p className="mt-1 text-sm text-muted-foreground">Bounded, attributable comparisons of local models and communication protocols</p></div></div><Button variant="outline" size="sm" onClick={() => navigate("/experiments")} className="gap-2 self-start sm:self-auto"><FlaskConical className="h-4 w-4" /> Experiment Lab</Button></div></header>
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 lg:px-8 lg:py-8">
      <Alert className="border-amber-300 bg-amber-50/90 dark:border-amber-800 dark:bg-amber-950/30"><ShieldAlert className="h-4 w-4" /><AlertTitle>Research boundary</AlertTitle><AlertDescription>Public-data research only. The builder uses local models; authorized cloud studies are labelled separately. This is not clinical evidence, financial advice, production readiness, proof of emergent intelligence, or proof that public benchmarks are model-unseen. Unknown and insufficient-evidence gates are intentionally prominent; tiny pilots are not accuracy validation.</AlertDescription></Alert>
      {IS_PREVIEW_MODE && <Alert className="border-indigo-300 bg-indigo-50/90 dark:border-indigo-800 dark:bg-indigo-950/30"><BookOpen className="h-4 w-4" /><AlertTitle>Read-only preview</AlertTitle><AlertDescription>Build {BUILD_INFO.buildLabel} on {BUILD_INFO.previewHostname}. No private catalog/library GETs and no research POST/poll/cancel traffic are sent from preview.</AlertDescription></Alert>}
      {!IS_PREVIEW_MODE && catalogError && <Alert variant="destructive"><XCircle className="h-4 w-4" /><AlertTitle>Catalog unavailable</AlertTitle><AlertDescription>{catalogError}</AlertDescription></Alert>}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-6"><Builder catalog={catalog} form={form} setForm={setForm} onStart={() => void startRun()} isSubmitting={submitLoading} errors={requestErrors} active={active} /><Library entries={library} selectedId={selectedRunId} loading={libraryLoading} error={libraryError} onRefresh={() => void loadLibrary()} onSelect={(id) => void loadRun(id)} /></aside>
        <section className="min-w-0 space-y-6">
          {reportLoading && <Card><CardContent className="flex min-h-48 flex-col items-center justify-center gap-3 text-center"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-500" /><p className="font-medium">Reading saved research report…</p><p className="text-sm text-muted-foreground">The selected run is identity-bound; stale responses are ignored.</p></CardContent></Card>}
          {!reportLoading && !report && <Card className="border-dashed"><CardContent className="flex min-h-72 flex-col items-center justify-center px-6 text-center"><CheckCircle2 className="h-12 w-12 text-indigo-400" /><h2 className="mt-4 text-xl font-semibold">Choose the question before the swarm speaks</h2><p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">Load the read-only catalog, keep the request bounded, then start a run. Reports preserve actual prompts, outputs, model identities, partial states, and honest scoring gates.</p></CardContent></Card>}
          {!reportLoading && report && <><ProgressCard report={report} cancelRequested={cancelRequested} onCancel={() => void cancelRun()} cancelling={cancelLoading} /><Card className="overflow-hidden border-slate-700 bg-slate-950 text-slate-100 dark:bg-slate-950"><CardHeader className="border-b border-slate-800 bg-gradient-to-r from-slate-900 via-indigo-950/70 to-purple-950/70"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-indigo-300/50 bg-indigo-500/20 text-indigo-100">Saved report</Badge><Badge variant={statusTone(report.status)} className="capitalize">{statusLabel(report.status)}</Badge></div><CardTitle className="mt-2 text-2xl text-white">{report.name}</CardTitle><CardDescription className="mt-2 text-slate-300">{report.request.datasets.length} dataset{report.request.datasets.length === 1 ? "" : "s"} · {report.request.model_keys.length} selected model identities · proof_ok={String(report.proof_ok)} · metered API cost ${formatResearchNumber(report.metered_api_cost_usd, 4)}</CardDescription></div><ReportActions report={report} /></div></CardHeader><CardContent className="space-y-4 p-6"><div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4"><Metric label="Request hash" value={report.request_hash || "—"} /><Metric label="Selected tasks" value={String(report.selected_task_ids.length)} /><Metric label="Actual calls" value={String(report.actual_calls)} /><Metric label="Updated" value={new Date(report.updated_at).toLocaleString()} /></div><div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Distinct model roster</p><div className="flex flex-wrap gap-2">{(Array.isArray(report.models) ? report.models : []).map((model: any) => <Badge key={model.key || model.model_id} variant="outline" className="border-slate-600 text-slate-200">{model.model_id || model.label || model.key}</Badge>)}</div></div></CardContent></Card><SummaryReport report={report} /><CollectiveBehaviourPanel report={report} /><TraceExplorer report={report} /><Card><CardHeader><CardTitle>Errors, limitations, and evidence boundary</CardTitle><CardDescription>Failures and partial output are preserved instead of being converted to zero accuracy.</CardDescription></CardHeader><CardContent className="space-y-4">{report.errors.length > 0 ? <ul className="space-y-2 text-sm text-destructive">{report.errors.map((error, index) => <li key={`${error}-${index}`} className="flex gap-2"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</li>)}</ul> : <p className="text-sm text-muted-foreground">No run-level errors recorded.</p>}<ul className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">{report.limitations.map((limitation) => <li key={limitation} className="flex gap-2"><span className="text-indigo-500">•</span>{limitation}</li>)}</ul></CardContent></Card></>}
        </section>
      </div>
    </main>
  </div>;
}
