import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Activity,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Download,
  ExternalLink,
  FlaskConical,
  Info,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { API_BASE_URL, BUILD_INFO, IS_PREVIEW_MODE } from "@/lib/runtime";
import {
  DEFAULT_EXPERIMENT_CONFIG,
  buildExperimentRequest,
  experimentToCsv,
  experimentToJson,
  formatExperimentNumber,
  formatPercent,
  parseSeedInput,
  statusLabel,
  validateExperimentRequest,
} from "@/lib/experiment";
import type {
  Experiment,
  ExperimentArm,
  ExperimentCase,
  ExperimentLibraryEntry,
  ExperimentRequest,
  ExperimentSummary,
  ReplayCheck,
  TumorSimulationConfig,
} from "@/lib/experimentTypes";

const DEFAULT_SEEDS = [17, 23, 42];
const ARM_LABELS: Record<string, string> = {
  no_bots: "No bots",
  fixed: "Fixed swarm",
  pheromone: "Pheromone swarm",
};
const ARM_COLORS: Record<string, string> = {
  no_bots: "#94a3b8",
  fixed: "#f59e0b",
  pheromone: "#a855f7",
};

function armLabel(arm: ExperimentArm): string {
  return ARM_LABELS[arm] ?? statusLabel(arm);
}

function armBadgeClass(arm: ExperimentArm): string {
  if (arm === "pheromone") return "border-purple-300 bg-purple-100 text-purple-800 dark:border-purple-700 dark:bg-purple-950/50 dark:text-purple-200";
  if (arm === "fixed") return "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200";
  return "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200";
}

function apiErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (error?.response?.data?.message) return error.response.data.message;
  return error?.message ?? "The backend request failed.";
}

function isExperiment(value: any): value is Experiment {
  return Boolean(
    value &&
      typeof value === "object" &&
      typeof value.experiment_id === "string" &&
      typeof value.name === "string" &&
      Array.isArray(value.cases) &&
      Array.isArray(value.summary) &&
      Array.isArray(value.replay_checks),
  );
}

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

function StatusBadge({ status }: { status: string }) {
  const tone = status === "completed" ? "default" : status === "failed" ? "destructive" : "outline";
  return (
    <Badge variant={tone} className="capitalize">
      {statusLabel(status)}
    </Badge>
  );
}

function BuilderNumberField({
  id,
  label,
  value,
  min,
  max,
  step,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        value={Number.isNaN(value) ? "" : value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ArmDefinitions() {
  return (
    <div className="grid gap-3 md:grid-cols-3" aria-label="Experiment controls">
      <div className="rounded-lg border border-slate-300 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/60">
        <div className="mb-1 flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-200">
          <span className="h-2.5 w-2.5 rounded-full bg-slate-400" /> No bots
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">Control arm: zero nanobots and pheromone signaling disabled.</p>
      </div>
      <div className="rounded-lg border border-amber-300 bg-amber-50/70 p-3 dark:border-amber-800 dark:bg-amber-950/30">
        <div className="mb-1 flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-200">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Fixed swarm
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">Requested nanobot count with pheromone signaling disabled.</p>
      </div>
      <div className="rounded-lg border border-purple-300 bg-purple-50/70 p-3 dark:border-purple-800 dark:bg-purple-950/30">
        <div className="mb-1 flex items-center gap-2 font-semibold text-purple-800 dark:text-purple-200">
          <span className="h-2.5 w-2.5 rounded-full bg-purple-500" /> Pheromone swarm
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">Same requested swarm with pheromone signaling enabled.</p>
      </div>
    </div>
  );
}

function ReplayResult({ check }: { check: ReplayCheck }) {
  const matched = check.status === "matched";
  const mismatch = check.status === "mismatch";
  return (
    <div className={`mt-3 rounded-md border p-3 text-xs ${matched ? "border-emerald-300 bg-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/30" : mismatch ? "border-amber-300 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/30" : "border-red-300 bg-red-50/70 dark:border-red-800 dark:bg-red-950/30"}`}>
      <div className="flex items-center gap-2 font-semibold">
        {matched ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <TriangleAlert className="h-4 w-4 text-amber-600" />}
        Replay: {statusLabel(check.status)}
      </div>
      <p className="mt-1 text-muted-foreground">{check.message || "Backend replay check completed."}</p>
      <div className="mt-2 grid gap-1 break-all font-mono text-[10px] text-muted-foreground md:grid-cols-2">
        <span>expected: {check.expected_trace_hash || "—"}</span>
        <span>actual: {check.actual_trace_hash || "—"}</span>
        <span>checked: {check.checked_at || "—"}</span>
        {check.replay_run_id && <span>replay run: {check.replay_run_id}</span>}
      </div>
      {check.replay_run_id && (
        <a className="mt-2 inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline" href={`/tumor?run=${encodeURIComponent(check.replay_run_id)}`}>
          Open replay playback <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

function CaseRow({
  item,
  replayCheck,
  onReplay,
  replaying,
  disabled,
}: {
  item: ExperimentCase;
  replayCheck?: ReplayCheck;
  onReplay: (caseId: string) => void;
  replaying: boolean;
  disabled: boolean;
}) {
  return (
    <div data-testid={`case-${item.case_id}`} className="rounded-lg border bg-background/60 p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={armBadgeClass(item.arm)}>{armLabel(item.arm)}</Badge>
            <span className="font-mono text-xs text-muted-foreground">{item.case_id}</span>
            <span className="text-sm text-muted-foreground">Seed {item.seed}</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">Actual saved run for this arm and seed.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-input bg-background px-3 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
            href={`/tumor?run=${encodeURIComponent(item.run_id)}`}
          >
            Open run <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Replay check"
            data-testid={`replay-check-${item.case_id}`}
            disabled={disabled || replaying}
            onClick={() => onReplay(item.case_id)}
          >
            {replaying ? <LoaderCircle className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
            Replay check
          </Button>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <Table className="min-w-[720px]">
          <TableHeader>
            <TableRow>
              <TableHead>Initial cells</TableHead>
              <TableHead>Final cells</TableHead>
              <TableHead>Living-cell reduction</TableHead>
              <TableHead>Deliveries</TableHead>
              <TableHead>Drug delivered</TableHead>
              <TableHead>Simulated time</TableHead>
              <TableHead>Runtime</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>{formatExperimentNumber(item.initial_living_cells, 0)}</TableCell>
              <TableCell>{formatExperimentNumber(item.final_living_cells, 0)}</TableCell>
              <TableCell className="font-medium">{formatPercent(item.net_cell_reduction_pct)}</TableCell>
              <TableCell>{formatExperimentNumber(item.deliveries)}</TableCell>
              <TableCell>{formatExperimentNumber(item.drug_delivered)}</TableCell>
              <TableCell>{formatExperimentNumber(item.simulation_minutes)} min</TableCell>
              <TableCell>{formatExperimentNumber(item.runtime_seconds)} s</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">Saved bindings</summary>
        <div className="mt-2 grid gap-1 break-all rounded bg-muted/50 p-3 font-mono text-[10px] text-muted-foreground md:grid-cols-3">
          <span>config: {item.config_hash || "—"}</span>
          <span>geometry: {item.initial_geometry_hash || "—"}</span>
          <span>trace: {item.trace_hash || "—"}</span>
        </div>
      </details>
      {replayCheck && <ReplayResult check={replayCheck} />}
    </div>
  );
}

function SummaryTable({ summary }: { summary: ExperimentSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[900px]">
        <TableHeader>
          <TableRow>
            <TableHead>Arm</TableHead>
            <TableHead>Seeds</TableHead>
            <TableHead>Living-cell reduction mean</TableHead>
            <TableHead>Sample SD</TableHead>
            <TableHead>Deliveries mean</TableHead>
            <TableHead>Drug mean</TableHead>
            <TableHead>vs no bots (pp)</TableHead>
            <TableHead>vs fixed (pp)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.map((item) => (
            <TableRow key={item.arm}>
              <TableCell><Badge variant="outline" className={armBadgeClass(item.arm)}>{armLabel(item.arm)}</Badge></TableCell>
              <TableCell>{item.seed_count}</TableCell>
              <TableCell className="font-medium">{formatPercent(item.net_cell_reduction_pct_mean)}</TableCell>
              <TableCell>{formatPercent(item.net_cell_reduction_pct_std)}</TableCell>
              <TableCell>{formatExperimentNumber(item.deliveries_mean)}</TableCell>
              <TableCell>{formatExperimentNumber(item.drug_delivered_mean)}</TableCell>
              <TableCell>{formatExperimentNumber(item.vs_no_bots_pp)} pp</TableCell>
              <TableCell>{formatExperimentNumber(item.vs_fixed_pp)} pp</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ExperimentReport({
  experiment,
  replayingCaseId,
  onReplay,
  replayDisabled,
}: {
  experiment: Experiment;
  replayingCaseId: string | null;
  onReplay: (caseId: string) => void;
  replayDisabled: boolean;
}) {
  const replayChecks = useMemo(() => new Map((experiment.replay_checks ?? []).map((check) => [check.case_id, check])), [experiment.replay_checks]);
  const summaryChartData = (experiment.summary ?? []).map((item) => ({
    arm: item.arm,
    name: armLabel(item.arm),
    mean: item.net_cell_reduction_pct_mean,
    std: item.net_cell_reduction_pct_std,
  }));
  const perSeedChartData = Array.from(new Set((experiment.cases ?? []).map((item) => item.seed))).sort((a, b) => a - b).map((seed) => {
    const row: Record<string, string | number | null> = { name: `Seed ${seed}`, seed };
    for (const arm of ["no_bots", "fixed", "pheromone"]) {
      row[arm] = experiment.cases.find((item) => item.seed === seed && item.arm === arm)?.net_cell_reduction_pct ?? null;
    }
    return row;
  });

  return (
    <section aria-labelledby="report-heading" className="space-y-6">
      <Card className="overflow-hidden border-slate-700 bg-slate-950 text-slate-100 shadow-xl dark:bg-slate-950">
        <CardHeader className="border-b border-slate-800 bg-gradient-to-r from-slate-900 via-indigo-950/70 to-purple-950/70">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-indigo-300/50 bg-indigo-500/20 text-indigo-100">Saved report</Badge>
                <StatusBadge status={experiment.status} />
              </div>
              <CardTitle id="report-heading" className="mt-3 text-2xl text-white">{experiment.name}</CardTitle>
              <CardDescription className="mt-2 max-w-3xl text-slate-300">
                {experiment.case_count} saved case{experiment.case_count === 1 ? "" : "s"} across {experiment.seed_count} seed{experiment.seed_count === 1 ? "" : "s"}. Descriptive synthetic results only; no winner or treatment claim is inferred.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => downloadText(`${experiment.experiment_id}.json`, experimentToJson(experiment), "application/json")}>
                <Download className="mr-2 h-4 w-4" /> Export JSON
              </Button>
              <Button type="button" variant="secondary" onClick={() => downloadText(`${experiment.experiment_id}.csv`, experimentToCsv(experiment), "text/csv;charset=utf-8")}>
                <Download className="mr-2 h-4 w-4" /> Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-6">
          {(experiment.status === "partial" || experiment.status === "failed") && (
            <Alert variant={experiment.status === "failed" ? "destructive" : "default"} className="border-amber-500/50 bg-amber-950/30 text-slate-100">
              <ShieldAlert className="h-4 w-4" />
              <AlertTitle>{statusLabel(experiment.status)} backend batch</AlertTitle>
              <AlertDescription className="text-slate-300">
                {experiment.error || "The backend did not complete every requested arm. Completed cases below remain explicitly marked as partial."}
              </AlertDescription>
            </Alert>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4"><p className="text-xs uppercase tracking-wide text-slate-400">Seeds</p><p className="mt-1 text-xl font-semibold">{(experiment.request?.seeds ?? []).join(", ") || "—"}</p></div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4"><p className="text-xs uppercase tracking-wide text-slate-400">Steps per run</p><p className="mt-1 text-xl font-semibold">{formatExperimentNumber(experiment.request?.config?.max_steps, 0)}</p></div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4"><p className="text-xs uppercase tracking-wide text-slate-400">Requested bots</p><p className="mt-1 text-xl font-semibold">{formatExperimentNumber(experiment.request?.config?.n_nanobots, 0)}</p></div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4"><p className="text-xs uppercase tracking-wide text-slate-400">Geometry</p><p className="mt-1 text-sm font-semibold">{experiment.matched_initial_geometry === true ? "Matched across arms" : experiment.matched_initial_geometry === false ? "Mismatch reported" : "Not established"}</p></div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-300">
            <div className="flex items-start gap-2"><Info className="mt-0.5 h-4 w-4 shrink-0 text-indigo-300" /><p>Actual simulated duration, deliveries, and drug-delivered values are shown per saved case below. Sample SD is only calculated where the backend has at least two cases in an arm. This local synthetic 2D model has short exposure, no toxicity model, a descriptive small sample, and replay checks are not cryptographic proof.</p></div>
          </div>
        </CardContent>
      </Card>

      {summaryChartData.length > 0 && (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Comparative report</CardTitle>
              <CardDescription>Mean net living-cell reduction by arm. Positive means fewer surviving cells; negative means growth.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summaryChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} unit="%" />
                    <Tooltip formatter={(value: number | null) => [formatPercent(value), "Mean living-cell reduction"]} />
                    <Legend />
                    <Bar dataKey="mean" name="Mean living-cell reduction" fill="#818cf8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Per-seed outcomes</CardTitle>
              <CardDescription>Paired by seed; missing or unmeasured values remain blank.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={perSeedChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} unit="%" />
                    <Tooltip formatter={(value: number | null, name: string) => [formatPercent(value), armLabel(name)]} />
                    <Legend formatter={(value) => armLabel(value)} />
                    <Line type="monotone" dataKey="no_bots" name="no_bots" stroke={ARM_COLORS.no_bots} strokeWidth={2} connectNulls={false} />
                    <Line type="monotone" dataKey="fixed" name="fixed" stroke={ARM_COLORS.fixed} strokeWidth={2} connectNulls={false} />
                    <Line type="monotone" dataKey="pheromone" name="pheromone" stroke={ARM_COLORS.pheromone} strokeWidth={2} connectNulls={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Arm summary and variability</CardTitle>
          <CardDescription>Percentage-point differences are paired descriptive comparisons, not efficacy or superiority claims.</CardDescription>
        </CardHeader>
        <CardContent>
          {experiment.summary.length > 0 ? <SummaryTable summary={experiment.summary} /> : <p className="text-sm text-muted-foreground">No summary rows were returned by the backend.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Per-seed cases</CardTitle>
          <CardDescription>Each row links to the existing playback route and can be recomputed through the backend.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {experiment.cases.length > 0 ? experiment.cases.map((item) => (
            <CaseRow
              key={item.case_id}
              item={item}
              replayCheck={replayChecks.get(item.case_id)}
              onReplay={onReplay}
              replaying={replayingCaseId === item.case_id}
              disabled={replayDisabled}
            />
          )) : <p className="text-sm text-muted-foreground">No completed cases were returned by the backend.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scope and limitations</CardTitle>
          <CardDescription>Kept with the saved report so exports and reloads retain the interpretation boundary.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
            {(experiment.limitations ?? []).map((limitation) => <li key={limitation} className="flex gap-2"><span className="text-indigo-500">•</span>{limitation}</li>)}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}

export default function ExperimentLab() {
  const navigate = useNavigate();
  const params = useParams();
  const initialId = useMemo(() => params.id || new URLSearchParams(window.location.search).get("id") || new URLSearchParams(window.location.search).get("experiment_id"), [params.id]);
  const [name, setName] = useState("Three-arm baseline");
  const [seedInput, setSeedInput] = useState(DEFAULT_SEEDS.join(", "));
  const [config, setConfig] = useState<TumorSimulationConfig>({ ...DEFAULT_EXPERIMENT_CONFIG });
  const [library, setLibrary] = useState<ExperimentLibraryEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialId);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [replayingCaseId, setReplayingCaseId] = useState<string | null>(null);
  const [requestErrors, setRequestErrors] = useState<string[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const updateSelectedUrl = useCallback((id: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("id", id);
    window.history.replaceState(window.history.state, "", url);
  }, []);

  const loadExperiment = useCallback(async (id: string, signal?: AbortSignal) => {
    if (IS_PREVIEW_MODE) return;
    setIsLoadingReport(true);
    setReportError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/experiments/${encodeURIComponent(id)}`, { signal });
      if (!isExperiment(response.data)) throw new Error("The backend returned an invalid saved experiment report.");
      setExperiment(response.data);
      setSelectedId(response.data.experiment_id);
      updateSelectedUrl(response.data.experiment_id);
    } catch (error: any) {
      if (!signal?.aborted) setReportError(apiErrorMessage(error));
    } finally {
      if (!signal?.aborted) setIsLoadingReport(false);
    }
  }, [updateSelectedUrl]);

  const loadLibrary = useCallback(async (signal?: AbortSignal) => {
    if (IS_PREVIEW_MODE) return;
    setIsLoadingLibrary(true);
    setLibraryError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/experiments`, { signal });
      if (!response.data || !Array.isArray(response.data.experiments)) throw new Error("The backend returned an invalid experiment library.");
      setLibrary(response.data.experiments);
    } catch (error: any) {
      if (!signal?.aborted) setLibraryError(apiErrorMessage(error));
    } finally {
      if (!signal?.aborted) setIsLoadingLibrary(false);
    }
  }, []);

  useEffect(() => {
    if (IS_PREVIEW_MODE) return;
    const controller = new AbortController();
    void loadLibrary(controller.signal);
    if (initialId) void loadExperiment(initialId, controller.signal);
    return () => controller.abort();
  }, [initialId, loadExperiment, loadLibrary]);

  const runExperiment = async () => {
    const seeds = parseSeedInput(seedInput);
    const request: ExperimentRequest = buildExperimentRequest(name, seeds, config);
    const errors = validateExperimentRequest(request.name, request.seeds, request.config);
    setRequestErrors(errors);
    setReportError(null);
    if (errors.length > 0 || IS_PREVIEW_MODE) return;

    setIsSubmitting(true);
    setExperiment(null);
    setSelectedId(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/experiments`, request, { timeout: 300000 });
      if (!isExperiment(response.data)) throw new Error("The backend returned an invalid experiment report.");
      setExperiment(response.data);
      setSelectedId(response.data.experiment_id);
      updateSelectedUrl(response.data.experiment_id);
      await loadLibrary();
      toast.success(response.data.status === "completed" ? "Experiment saved." : `Experiment saved as ${statusLabel(response.data.status)}.`);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const retainedId = detail?.experiment_id || error?.response?.data?.experiment_id;
      if (retainedId) {
        setRequestErrors([`${apiErrorMessage(error)} The backend retained experiment ${retainedId}; loading its saved report.`]);
        await loadExperiment(retainedId);
        await loadLibrary();
      } else {
        setRequestErrors([apiErrorMessage(error)]);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const replayCase = async (caseId: string) => {
    if (IS_PREVIEW_MODE || !experiment) return;
    setReplayingCaseId(caseId);
    try {
      const response = await axios.post(`${API_BASE_URL}/experiments/${encodeURIComponent(experiment.experiment_id)}/replay/${encodeURIComponent(caseId)}`);
      const check = response.data as ReplayCheck;
      if (!check || typeof check.status !== "string") throw new Error("The backend returned an invalid replay check.");
      setExperiment((current) => current ? { ...current, replay_checks: [...(current.replay_checks ?? []), check] } : current);
      if (check.status === "matched") toast.success(`Replay matched for ${caseId}.`);
      else toast.error(`Replay ${statusLabel(check.status)} for ${caseId}.`);
    } catch (error: any) {
      toast.error(`Replay check failed: ${apiErrorMessage(error)}`);
    } finally {
      setReplayingCaseId(null);
    }
  };

  const estimatedCells = Math.PI * config.tumor_radius ** 2 * config.cell_density;
  const parsedSeeds = parseSeedInput(seedInput);
  const estimatedWork = estimatedCells * config.max_steps * parsedSeeds.length * 3;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-purple-100/40 text-foreground dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/40">
      <header className="border-b bg-white/85 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-950/85">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/")} className="gap-2">
              <ArrowLeft className="h-4 w-4" /> Home
            </Button>
            <div className="hidden h-7 w-px bg-border sm:block" />
            <div>
              <div className="flex items-center gap-2"><FlaskConical className="h-5 w-5 text-purple-600" /><h1 className="text-2xl font-bold tracking-tight">Experiment Lab</h1></div>
              <p className="mt-1 text-sm text-muted-foreground">Reproducible three-arm comparisons for the synthetic tumor model</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => navigate("/tumor")} className="gap-2 self-start sm:self-auto">
            <Activity className="h-4 w-4" /> Open single-run playback
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 lg:px-8 lg:py-8">
        {IS_PREVIEW_MODE && (
          <Alert className="border-amber-300 bg-amber-50/90 dark:border-amber-800 dark:bg-amber-950/30">
            <ShieldAlert className="h-4 w-4" />
            <AlertTitle>Read-only preview</AlertTitle>
            <AlertDescription>Experiment Lab is visible in preview build {BUILD_INFO.buildLabel}; backend reads and writes are disabled here. No run is started automatically.</AlertDescription>
          </Alert>
        )}

        <section className="rounded-xl border border-indigo-200 bg-white/70 p-5 shadow-sm dark:border-indigo-900 dark:bg-slate-900/70">
          <div className="flex items-start gap-3"><BookOpen className="mt-1 h-5 w-5 shrink-0 text-indigo-600" /><div><h2 className="font-semibold">What this experiment tests</h2><p className="mt-1 max-w-4xl text-sm leading-relaxed text-muted-foreground">Hold synthetic geometry, Rule-Based behavior, seed, and requested swarm size constant while comparing a no-bot control, a fixed swarm, and a pheromone-enabled swarm. Results are descriptive, small-sample observations from local 2D simulations—not evidence of clinical efficacy, toxicity, or superiority.</p></div></div>
          <div className="mt-4"><ArmDefinitions /></div>
        </section>

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(290px,360px)_minmax(0,1fr)]">
          <aside className="min-w-0 space-y-6">
            <Card className="border-indigo-200 shadow-md dark:border-indigo-900">
              <CardHeader>
                <CardTitle>Build an experiment</CardTitle>
                <CardDescription>One bounded POST runs all three arms for each declared seed.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5"><Label htmlFor="experiment-name">Experiment name</Label><Input id="experiment-name" value={name} maxLength={80} onChange={(event) => setName(event.target.value)} placeholder="e.g. Three-arm baseline" /></div>
                <div className="space-y-1.5"><Label htmlFor="experiment-seeds">Seeds</Label><Input id="experiment-seeds" aria-label="Seeds" value={seedInput} onChange={(event) => setSeedInput(event.target.value)} placeholder="17, 23, 42" /><p className="text-xs text-muted-foreground">Enter 1–5 unique integer seeds, separated by commas or spaces.</p></div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
                  <BuilderNumberField id="experiment-steps" label="Steps per run" value={config.max_steps} min={1} max={200} step={1} onChange={(value) => setConfig((current) => ({ ...current, max_steps: value }))} hint="Maximum 200" />
                  <BuilderNumberField id="experiment-bots" label="Nanobots" value={config.n_nanobots} min={1} max={25} step={1} onChange={(value) => setConfig((current) => ({ ...current, n_nanobots: value }))} hint="Fixed and pheromone arms" />
                  <BuilderNumberField id="experiment-domain" label="Domain size" value={config.domain_size} min={1} max={1000} step={1} onChange={(value) => setConfig((current) => ({ ...current, domain_size: value }))} hint="Synthetic µm; maximum 1000" />
                  <BuilderNumberField id="experiment-voxel" label="Voxel size" value={config.voxel_size} min={1} step={1} onChange={(value) => setConfig((current) => ({ ...current, voxel_size: value }))} hint="Domain/voxel grid ≤ 30" />
                  <BuilderNumberField id="experiment-radius" label="Tumor radius" value={config.tumor_radius} min={1} step={1} onChange={(value) => setConfig((current) => ({ ...current, tumor_radius: value }))} hint="Must fit inside domain" />
                  <BuilderNumberField id="experiment-cell-density" label="Cell density" value={config.cell_density} min={0.000001} step={0.0001} onChange={(value) => setConfig((current) => ({ ...current, cell_density: value }))} />
                  <BuilderNumberField id="experiment-vessel-density" label="Vessel density" value={config.vessel_density} min={0.000001} step={0.001} onChange={(value) => setConfig((current) => ({ ...current, vessel_density: value }))} />
                </div>
                <div className="rounded-md bg-muted/60 p-3 text-xs text-muted-foreground">
                  <div className="flex justify-between gap-2"><span>Arms × seeds</span><span className="font-medium text-foreground">3 × {parsedSeeds.length || 0} = {parsedSeeds.length * 3}</span></div>
                  <div className="mt-1 flex justify-between gap-2"><span>Expected cells</span><span className="font-medium text-foreground">{formatExperimentNumber(estimatedCells, 1)}</span></div>
                  <div className="mt-1 flex justify-between gap-2"><span>Bounded work estimate</span><span className="font-medium text-foreground">{formatExperimentNumber(estimatedWork, 0)} units</span></div>
                </div>
                <Button type="button" className="w-full gap-2" onClick={runExperiment} disabled={isSubmitting || IS_PREVIEW_MODE}>
                  {isSubmitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Run experiment
                </Button>
                {isSubmitting && <p className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite"><LoaderCircle className="h-3.5 w-3.5 animate-spin" /> Backend is running bounded local work. Completion time is indeterminate; no fake progress is shown.</p>}
                {requestErrors.length > 0 && <Alert variant="destructive"><TriangleAlert className="h-4 w-4" /><AlertTitle>Check the request</AlertTitle><AlertDescription><ul className="list-disc space-y-1 pl-4">{requestErrors.map((error) => <li key={error}>{error}</li>)}</ul></AlertDescription></Alert>}
                <p className="text-xs leading-relaxed text-muted-foreground">The request is always sent as Rule-Based, offline, and without a Queen. The backend is the source of all cases and metrics.</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3"><div className="flex items-center justify-between gap-2"><div><CardTitle className="text-lg">Saved library</CardTitle><CardDescription>Reloads from the backend on page load.</CardDescription></div><Button type="button" variant="ghost" size="icon" aria-label="Refresh saved experiment library" onClick={() => void loadLibrary()} disabled={IS_PREVIEW_MODE || isLoadingLibrary}><RefreshCw className={`h-4 w-4 ${isLoadingLibrary ? "animate-spin" : ""}`} /></Button></div></CardHeader>
              <CardContent>
                {libraryError && <p className="mb-3 text-sm text-destructive">Could not load library: {libraryError}</p>}
                {isLoadingLibrary && library.length === 0 && <p className="text-sm text-muted-foreground">Loading saved experiments…</p>}
                {!isLoadingLibrary && library.length === 0 && !libraryError && <p className="text-sm text-muted-foreground">No saved experiments yet. Run a bounded comparison to create one.</p>}
                <div className="space-y-2">
                  {library.map((item) => <button key={item.experiment_id} type="button" onClick={() => { setSelectedId(item.experiment_id); void loadExperiment(item.experiment_id); }} className={`w-full rounded-md border p-3 text-left transition-colors hover:border-indigo-400 hover:bg-indigo-50/60 dark:hover:bg-indigo-950/30 ${selectedId === item.experiment_id ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40" : "bg-background"}`}><div className="flex items-start justify-between gap-2"><span className="truncate font-medium">{item.name}</span><StatusBadge status={item.status} /></div><div className="mt-1 text-xs text-muted-foreground">{item.seed_count} seeds · {item.case_count} cases · {new Date(item.created_at).toLocaleString()}</div></button>)}
                </div>
              </CardContent>
            </Card>
          </aside>

          <div className="min-w-0 space-y-6">
            {reportError && <Alert variant="destructive"><TriangleAlert className="h-4 w-4" /><AlertTitle>Could not load saved report</AlertTitle><AlertDescription>{reportError}</AlertDescription></Alert>}
            {isLoadingReport && <Card><CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 text-center"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-500" /><p className="font-medium">Loading saved report…</p><p className="text-sm text-muted-foreground">Reading the selected experiment from the backend.</p></CardContent></Card>}
            {!isLoadingReport && experiment && <ExperimentReport experiment={experiment} replayingCaseId={replayingCaseId} onReplay={replayCase} replayDisabled={IS_PREVIEW_MODE} />}
            {!isLoadingReport && !experiment && !reportError && !isSubmitting && <Card className="border-dashed"><CardContent className="flex min-h-96 flex-col items-center justify-center px-6 text-center"><FlaskConical className="h-12 w-12 text-indigo-400" /><h2 className="mt-4 text-xl font-semibold">Your saved report will appear here</h2><p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">Configure a hypothesis, declare the seeds, then run the experiment. The report will include actual backend cases, paired charts, variability, playback links, and replay checks.</p></CardContent></Card>}
          </div>
        </div>
      </main>
    </div>
  );
}
