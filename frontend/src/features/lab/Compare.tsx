import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Eye } from "lucide-react";
import { useRunEvents, useRunFrames } from "@/api/queries";
import type { Experiment } from "@/api/engine";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMetric, pointAt, tickSeries } from "@/features/runs/derive";
import { PlaybackHints, Scrubber } from "@/features/runs/Scrubber";
import { usePlayback } from "@/features/runs/usePlayback";
import { SceneCanvas } from "@/features/viewport/Viewport";
import { FIELD_STYLE } from "@/features/viewport/styles";
import { armLabel, humanize } from "@/features/worlds/meta";
import { cn } from "@/lib/utils";
import { effectOf } from "./stats";

export type WatchSelection = { seed: number; left: string; right: string };

function runIdFor(report: Experiment, arm: string, seed: number): string | undefined {
  return report.runs[arm]?.find((r) => r.spec.case === seed)?.run_id;
}

/** One side of the comparison: live scene + the primary metric counting up as it plays. */
function Side({ report, arm, seed, position, tick, layer, winner }: {
  report: Experiment;
  arm: string;
  seed: number;
  position: number;
  tick: number;
  layer: string | null;
  winner: boolean;
}) {
  const runId = runIdFor(report, arm, seed);
  const frames = useRunFrames(runId);
  const events = useRunEvents(runId);
  const series = useMemo(() => tickSeries(events.data?.events ?? []), [events.data]);
  const metric = report.primary_metric;
  const last = series[series.length - 1];
  const now = pointAt(series, tick)?.metrics[metric];
  const finished = last && tick >= last.tick;
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className={cn("min-w-0 space-y-3 rounded-xl border p-3", winner ? "border-success/40" : "border-border")}>
      <div className="flex items-center justify-between gap-2 px-1">
        <p className="truncate text-sm font-medium">
          {armLabel(arm)}
          {arm === report.request.baseline && <span className="ml-2 rounded bg-surface-3 px-1.5 py-0.5 text-2xs font-normal text-muted-foreground">baseline</span>}
        </p>
        {runId && (
          <Link to={`/runs/${encodeURIComponent(runId)}?t=${tick}`} className="inline-flex shrink-0 items-center gap-1 text-2xs text-muted-foreground hover:text-foreground">
            Open run <ArrowUpRight className="size-3" />
          </Link>
        )}
      </div>
      <div className="mx-auto max-w-[440px]">
        {frames.data ? (
          <SceneCanvas data={frames.data} position={position} layer={layer} selected={selected} onSelect={setSelected} />
        ) : frames.isPending ? (
          <Skeleton className="aspect-square w-full rounded-lg" />
        ) : (
          <div className="flex aspect-square w-full items-center justify-center rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
            No frames for this run (recorded before replay existed). Re-run the experiment with a different seed set to record them.
          </div>
        )}
      </div>
      <div className="flex items-baseline justify-between px-1">
        <span className="text-xs text-muted-foreground">{humanize(metric)}</span>
        <span className="numeric font-mono text-xl font-semibold">{now === undefined ? "—" : formatMetric(metric, now)}</span>
      </div>
      <p className="h-4 px-1 text-2xs text-muted-foreground">
        {finished ? `Finished at tick ${last.tick}${last.metrics[report.request.world === "tumor" ? "cleared" : "success"] ? " · goal reached" : ""}` : ""}
      </p>
    </div>
  );
}

/**
 * Watch two arms on the same seed, side by side, under one playhead: the
 * visual counterpart of the paired comparison above.
 */
export function Compare({ report, selection, onSelection }: {
  report: Experiment;
  selection: WatchSelection;
  onSelection: (s: WatchSelection) => void;
}) {
  const arms = Object.keys(report.runs);
  const maxTicks = Math.max(1, ...arms.flatMap((a) => report.runs[a].filter((r) => r.spec.case === selection.seed).map((r) => r.ticks)));
  const playback = usePlayback(0, maxTicks, 0);
  const fields = report.request.world === "tumor" ? Object.keys(FIELD_STYLE).filter((f) => f !== "oxygen") : [];
  const [layer, setLayer] = useState<string | null>(fields.includes("drug") ? "drug" : null);
  const left = report.runs[selection.left]?.find((r) => r.spec.case === selection.seed);
  const right = report.runs[selection.right]?.find((r) => r.spec.case === selection.seed);
  const metric = report.primary_metric;
  const lv = typeof left?.[metric] === "number" ? (left[metric] as number) : null;
  const rv = typeof right?.[metric] === "number" ? (right[metric] as number) : null;
  const pct = lv && rv !== null ? ((rv - lv) / Math.abs(lv)) * 100 : null;
  const verdict = effectOf(pct, report.lower_is_better);

  const Picker = ({ value, onChange }: { value: string; onChange: (arm: string) => void }) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 rounded-md border bg-transparent px-2 text-xs outline-none focus:border-ring"
    >
      {arms.map((a) => <option key={a} value={a} className="bg-popover">{armLabel(a)}</option>)}
    </select>
  );

  return (
    <section id="watch" className="surface-edge scroll-mt-6 overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-medium"><Eye className="size-4 text-primary" /> Watch</h2>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Picker value={selection.left} onChange={(left) => onSelection({ ...selection, left })} />
          <span>vs</span>
          <Picker value={selection.right} onChange={(right) => onSelection({ ...selection, right })} />
          <span className="ml-1">seed</span>
          <select
            value={selection.seed}
            onChange={(e) => onSelection({ ...selection, seed: Number(e.target.value) })}
            className="numeric h-8 rounded-md border bg-transparent px-2 font-mono text-xs outline-none focus:border-ring"
          >
            {report.request.cases.map((c) => <option key={c} value={c} className="bg-popover">{c}</option>)}
          </select>
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div className="grid gap-3 md:grid-cols-2">
          <Side report={report} arm={selection.left} seed={selection.seed} position={playback.position} tick={playback.tick} layer={layer} winner={verdict === "worse"} />
          <Side report={report} arm={selection.right} seed={selection.seed} position={playback.position} tick={playback.tick} layer={layer} winner={verdict === "better"} />
        </div>

        <Scrubber playback={playback} density={new Map()} flagged={new Set()} />

        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <p className="text-xs text-muted-foreground">
            On seed {selection.seed}: {armLabel(selection.left)} {lv === null ? "—" : formatMetric(metric, lv)} → {armLabel(selection.right)} {rv === null ? "—" : formatMetric(metric, rv)}
            {pct !== null && (
              <span className={cn("ml-2 font-medium", verdict === "better" ? "text-success" : verdict === "worse" ? "text-danger" : "")}>
                ({pct > 0 ? "+" : ""}{pct.toFixed(0)}% {humanize(metric).toLowerCase()})
              </span>
            )}
          </p>
          <div className="flex items-center gap-3">
            {fields.length > 0 && (
              <div className="flex items-center gap-1">
                {[null, ...fields].map((f) => (
                  <button
                    key={f ?? "none"}
                    type="button"
                    onClick={() => setLayer(f)}
                    className={cn("h-6 rounded px-1.5 text-2xs transition-colors", layer === f ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
                  >
                    {f ? FIELD_STYLE[f].label : "No field"}
                  </button>
                ))}
              </div>
            )}
            <PlaybackHints />
          </div>
        </div>
      </div>
    </section>
  );
}
