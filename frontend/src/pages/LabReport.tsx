import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowDown, ArrowUp, ChevronRight, Info, Play, Trophy } from "lucide-react";
import { useExperiment } from "@/api/queries";
import type { Experiment } from "@/api/engine";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Hash } from "@/design/Hash";
import { Page } from "@/design/PageHeader";
import { ErrorState } from "@/design/States";
import { cellIntensity, effectOf, forestBound, formatP, formatPct } from "@/features/lab/stats";
import { Compare, type WatchSelection } from "@/features/lab/Compare";
import { Button } from "@/components/ui/button";
import { formatMetric } from "@/features/runs/derive";
import { armLabel, humanize, worldMeta } from "@/features/worlds/meta";
import { cn } from "@/lib/utils";

function Card({ title, aside, children, className }: { title: string; aside?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("surface-edge overflow-hidden rounded-xl border bg-card", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-medium">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Recommendation({ report, onWatch }: { report: Experiment; onWatch: () => void }) {
  const rec = report.recommendation;
  if (!rec) return null;
  const tone = rec.best_arm ? "success" : rec.underpowered ? "warning" : "neutral";
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border p-4",
        tone === "success" && "border-success/30 bg-success/[0.06]",
        tone === "warning" && "border-warning/30 bg-warning/[0.06]",
      )}
    >
      {tone === "success" ? <Trophy className="mt-0.5 size-4 shrink-0 text-success" /> : tone === "warning" ? <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" /> : <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium">{rec.best_arm ? `${armLabel(rec.best_arm)} works best` : rec.underpowered ? "Too few seeds to decide" : "No arm beat the baseline"}</p>
        <p className="text-sm text-muted-foreground">{rec.summary}</p>
      </div>
      {rec.best_arm && (
        <Button size="sm" variant="outline" className="shrink-0" onClick={onWatch}><Play /> Watch it</Button>
      )}
    </div>
  );
}

/** Horizontal forest plot: % change vs baseline per arm, colored by whether it's an improvement. */
function ForestPlot({ report }: { report: Experiment }) {
  const entries = Object.entries(report.comparisons_vs_baseline);
  const bound = forestBound(report.comparisons_vs_baseline);
  const pos = (pct: number) => 50 + (pct / bound) * 50;
  if (entries.length === 0) return <p className="p-4 text-sm text-muted-foreground">Only the baseline was run.</p>;
  return (
    <div className="space-y-1 p-4">
      <div className="grid grid-cols-[140px_minmax(0,1fr)_150px] items-center gap-4 pb-2 text-2xs text-muted-foreground">
        <span />
        <div className="relative h-4 font-mono">
          <span className="absolute left-0">{formatPct(-bound)}</span>
          <span className="absolute left-1/2 -translate-x-1/2">0</span>
          <span className="absolute right-0">{formatPct(bound)}</span>
        </div>
        <span className="text-right">vs {armLabel(report.request.baseline)}</span>
      </div>
      {entries.map(([arm, c]) => {
        const effect = effectOf(c.pct_change, report.lower_is_better);
        const pct = c.pct_change ?? 0;
        const verdict = report.recommendation?.verdicts[arm];
        return (
          <div key={arm} className="grid grid-cols-[140px_minmax(0,1fr)_150px] items-center gap-4 py-1.5">
            <span className="truncate text-sm">{armLabel(arm)}</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="relative h-7 rounded-md bg-surface-2">
                  <div className="absolute inset-y-1 left-1/2 w-px bg-foreground/25" />
                  <div
                    className={cn("absolute inset-y-2 rounded-sm", effect === "better" ? "bg-success/80" : effect === "worse" ? "bg-danger/80" : "bg-muted-foreground/50")}
                    style={{ left: `${Math.min(pos(0), pos(pct))}%`, width: `${Math.max(0.6, Math.abs(pos(pct) - pos(0)))}%` }}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent className="space-y-0.5 font-mono">
                <p>{formatPct(c.pct_change)} · mean Δ {c.mean_delta === null ? "—" : c.mean_delta.toFixed(2)}</p>
                <p>{c.wins} better / {c.losses} worse / {c.ties} tied of {c.pairs}</p>
                {verdict && <p className="text-muted-foreground">{verdict.reason}</p>}
              </TooltipContent>
            </Tooltip>
            <div className="text-right">
              <p className={cn("numeric font-mono text-sm", effect === "better" ? "text-success" : effect === "worse" ? "text-danger" : "text-muted-foreground")}>{formatPct(c.pct_change)}</p>
              <p className="numeric font-mono text-2xs text-muted-foreground">{formatP(c.sign_test_p)} · {c.wins}/{c.losses}/{c.ties}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ArmsTable({ report }: { report: Experiment }) {
  const metric = report.primary_metric;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-2xs uppercase tracking-[0.06em] text-muted-foreground">
            <th className="px-4 py-2.5 font-medium">Arm</th>
            <th className="px-4 py-2.5 text-right font-medium">Mean {humanize(metric).toLowerCase()}</th>
            <th className="px-4 py-2.5 font-medium">Success (95% CI)</th>
            <th className="px-4 py-2.5 text-right font-medium">Unsafe</th>
            <th className="px-4 py-2.5 text-right font-medium">Blocked</th>
            <th className="px-4 py-2.5 font-medium">Verdicts</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {Object.entries(report.arms).map(([arm, a]) => {
            const m = (a as Record<string, unknown>)[metric] as { mean: number | null } | undefined;
            const lo = a.success_wilson_95.low * 100;
            const hi = a.success_wilson_95.high * 100;
            return (
              <tr key={arm} className="hover:bg-accent/40">
                <td className="px-4 py-2.5">
                  <span className="font-medium">{armLabel(arm)}</span>
                  {arm === report.request.baseline && <span className="ml-2 rounded bg-surface-3 px-1.5 py-0.5 text-2xs text-muted-foreground">baseline</span>}
                  {arm === report.recommendation?.best_arm && <Trophy className="ml-2 inline size-3.5 text-success" />}
                </td>
                <td className="numeric px-4 py-2.5 text-right font-mono">{m?.mean === null || m?.mean === undefined ? "—" : formatMetric(metric, m.mean)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-3">
                    <span className="numeric w-12 font-mono text-xs">{a.successes}/{a.cases}</span>
                    <div className="relative h-1.5 w-28 rounded-full bg-surface-3">
                      <div className="absolute inset-y-0 rounded-full bg-primary/40" style={{ left: `${lo}%`, width: `${Math.max(1, hi - lo)}%` }} />
                      <div className="absolute -top-0.5 size-2.5 -translate-x-1/2 rounded-full bg-primary" style={{ left: `${(a.successes / Math.max(1, a.cases)) * 100}%` }} />
                    </div>
                  </div>
                </td>
                <td className={cn("numeric px-4 py-2.5 text-right font-mono", a.unsafe_applied ? "text-danger" : "text-muted-foreground")}>{a.unsafe_applied}</td>
                <td className="numeric px-4 py-2.5 text-right font-mono text-muted-foreground">{a.blocked_attempts + a.concurrent_blocks}</td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {Object.entries(a.verdicts).map(([v, n]) => `${n} ${v.replace(/_/g, " ")}`).join(" · ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Arms × seeds grid of the primary metric; brighter = better; click a cell to open that run. */
function RunMatrix({ report, selection, onPick }: { report: Experiment; selection: WatchSelection; onPick: (arm: string, seed: number) => void }) {
  const metric = report.primary_metric;
  const all = Object.values(report.runs).flat().map((r) => (typeof r[metric] === "number" ? (r[metric] as number) : null));
  const present = all.filter((v): v is number => v !== null);
  const lo = Math.min(...present);
  const hi = Math.max(...present);
  return (
    <div className="overflow-x-auto p-4">
      <table className="border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th />
            {report.request.cases.map((c) => <th key={c} className="numeric px-1 font-mono text-2xs font-normal text-muted-foreground">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.runs).map(([arm, rows]) => (
            <tr key={arm}>
              <th className="whitespace-nowrap pr-3 text-left text-xs font-normal text-muted-foreground">{armLabel(arm)}</th>
              {rows.map((r) => {
                const v = typeof r[metric] === "number" ? (r[metric] as number) : null;
                const t = cellIntensity(v, lo, hi, report.lower_is_better);
                return (
                  <td key={r.run_id} className="p-0">
                    <button
                      type="button"
                      onClick={() => onPick(arm, r.spec.case)}
                      title={`Watch ${armLabel(arm)} · seed ${r.spec.case} · ${r.verdict}`}
                      className={cn(
                        "group relative numeric h-8 min-w-11 rounded-md px-1.5 font-mono text-2xs transition-[transform,box-shadow] hover:scale-105 hover:shadow-e2",
                        r.verdict !== "success" && r.verdict !== "safe_incomplete" && "ring-1 ring-danger",
                        r.spec.case === selection.seed && (arm === selection.left || arm === selection.right) && "ring-2 ring-foreground/70",
                      )}
                      style={{ background: `hsl(var(--primary) / ${0.06 + t * 0.39})` }}
                    >
                      <span className="group-hover:opacity-0">{v === null ? "—" : formatMetric(metric, v)}</span>
                      <Play className="absolute inset-0 m-auto size-3 fill-current opacity-0 transition-opacity group-hover:opacity-100" />
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Report({ report }: { report: Experiment }) {
  const meta = worldMeta(report.request.world);
  const baseline = report.request.baseline;
  const challenger = report.recommendation?.best_arm ?? Object.keys(report.comparisons_vs_baseline)[0] ?? baseline;
  const [selection, setSelection] = useState<WatchSelection>({ seed: report.request.cases[0], left: baseline, right: challenger });
  // Each explicit "watch" remounts the panel so it starts playing from the first tick.
  const [watchCount, setWatchCount] = useState(0);
  const watch = (next: WatchSelection) => {
    setSelection(next);
    setWatchCount((n) => n + 1);
    document.getElementById("watch")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const pick = (arm: string, seed: number) =>
    watch(arm === baseline ? { ...selection, seed } : { seed, left: baseline, right: arm });
  const Direction = report.lower_is_better ? ArrowDown : ArrowUp;
  const params = Object.entries(report.request.params);
  return (
    <Page className="space-y-6">
      <nav className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link to="/lab" className="hover:text-foreground">Lab</Link>
        <ChevronRight className="size-3" />
        <Hash value={report.experiment_id} head={16} tail={0} className="text-xs" />
      </nav>
      <header className="space-y-2">
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-[-0.02em]">
          <meta.icon className="size-5 text-primary" /> {meta.title} experiment
        </h1>
        <p className="numeric flex flex-wrap items-center gap-x-1 text-sm text-muted-foreground">
          {Object.keys(report.arms).length} arms × {report.request.cases.length} seeds · vs {armLabel(report.request.baseline)} ·
          <span className="inline-flex items-center gap-1">primary metric {humanize(report.primary_metric).toLowerCase()} <Direction className="size-3" /></span>
          {params.map(([k, v]) => <span key={k}>· {humanize(k).toLowerCase()} {String(v)}</span>)}
        </p>
      </header>

      <Recommendation report={report} onWatch={() => watch({ seed: selection.seed, left: baseline, right: challenger })} />

      <Compare key={`${selection.seed}-${watchCount}`} report={report} selection={selection} onSelection={setSelection} autoplay={watchCount > 0} />

      <Card title="Effect vs baseline" aside={<span className="text-2xs text-muted-foreground">paired sign test · wins/losses/ties</span>}>
        <ForestPlot report={report} />
      </Card>

      <Card title="Arms"><ArmsTable report={report} /></Card>

      <Card title="Runs" aside={<span className="text-2xs text-muted-foreground">{humanize(report.primary_metric)} per seed · click any cell to watch it</span>}>
        <RunMatrix report={report} selection={selection} onPick={pick} />
      </Card>

      <section className="space-y-2 rounded-xl border border-dashed p-4">
        <h2 className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground"><Info className="size-3.5" /> Caveats</h2>
        <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted-foreground">
          {report.caveats.map((c) => <li key={c}>{c}</li>)}
        </ul>
      </section>
    </Page>
  );
}

export default function LabReport() {
  const { id = "" } = useParams();
  const experiment = useExperiment(id);
  if (experiment.data) return <Report report={experiment.data} />;
  return (
    <Page className="space-y-6">
      {experiment.isError ? (
        <ErrorState error={experiment.error} onRetry={() => void experiment.refetch()} />
      ) : (
        <>
          <Skeleton className="h-8 w-80" />
          <Skeleton className="h-20 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </>
      )}
    </Page>
  );
}
