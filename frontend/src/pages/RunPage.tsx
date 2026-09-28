import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ChevronRight, RotateCcw, ShieldCheck } from "lucide-react";
import { useRun, useRunEvents, useVerifyRun } from "@/api/queries";
import type { EngineEvent, Run } from "@/api/engine";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Hash } from "@/design/Hash";
import { Page } from "@/design/PageHeader";
import { ErrorState } from "@/design/States";
import { TrustBadge, VerdictBadge } from "@/features/runs/badges";
import { Sparkline, TimeSeriesChart } from "@/features/runs/charts";
import {
  countByType, eventsByTick, formatMetric, numericSeriesKeys, pointAt, seriesValues, tickRange, tickSeries, type TickPoint,
} from "@/features/runs/derive";
import { PlaybackHints, Scrubber } from "@/features/runs/Scrubber";
import { usePlayback, type Playback } from "@/features/runs/usePlayback";
import { LANE_LEGEND, agentLanes } from "@/features/runs/describe";
import { Swimlanes } from "@/features/runs/Swimlanes";
import { EventStream, type StreamScope } from "@/features/runs/EventStream";
import { EventDetail } from "@/features/runs/EventDetail";
import { AgentPanel } from "@/features/runs/AgentPanel";
import { Provenance } from "@/features/runs/Provenance";
import { armLabel, humanize, worldMeta } from "@/features/worlds/meta";
import { cn } from "@/lib/utils";

function KpiTile({ label, value, ticks, values, cursor, emphasis }: {
  label: string;
  value: string;
  ticks: number[];
  values: Array<number | null> | null;
  cursor: number;
  emphasis?: boolean;
}) {
  return (
    <div className={cn("surface-edge flex flex-col gap-3 rounded-xl border bg-card p-4", emphasis && "border-primary/25")}>
      <p className="truncate text-xs text-muted-foreground">{label}</p>
      <p className="numeric text-[26px] font-semibold leading-none tracking-[-0.02em]">{value}</p>
      {values ? <Sparkline ticks={ticks} values={values} cursor={cursor} /> : <div className="h-8" />}
    </div>
  );
}

function SafetyStrip({ run }: { run: Run }) {
  const v = run.verdict;
  const c = run.bundle.counters;
  const items: Array<[string, number | undefined, boolean]> = [
    ["unsafe applied", v.unsafe_applied, v.unsafe_applied > 0],
    ["blocked attempts", v.blocked_attempts, false],
    ["concurrent blocks", v.concurrent_blocks, false],
    ["policy failures", v.policy_failures, v.policy_failures > 0],
    ["signals deposited", c.signals_deposited, false],
    ["signals rejected", c.signals_rejected, false],
  ];
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-xl border border-dashed px-4 py-3 text-xs">
      {items.filter(([, n]) => n !== undefined).map(([label, n, bad]) => (
        <span key={label} className="inline-flex items-baseline gap-1.5">
          <span className={cn("numeric font-mono font-medium", bad ? "text-danger" : n === 0 ? "text-muted-foreground" : "text-foreground")}>{n}</span>
          <span className="text-muted-foreground">{label}</span>
        </span>
      ))}
    </div>
  );
}

const TYPE_LABEL: Record<string, string> = {
  decided: "decisions", outcome: "outcomes", intent_blocked: "blocked", signal_deposited: "signals",
  signal_rejected: "rejected", signal_expired: "expired", memory_changed: "memory", policy_failed: "failures",
};

function TickActivity({ events }: { events: EngineEvent[] }) {
  const counts = countByType(events);
  const entries = Object.entries(TYPE_LABEL).filter(([type]) => counts[type]);
  if (entries.length === 0) return <p className="text-xs text-muted-foreground">No agent activity this tick.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([type, label]) => (
        <span
          key={type}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-2xs",
            type === "intent_blocked" || type === "policy_failed" ? "border-danger/30 text-danger" : "text-muted-foreground",
          )}
        >
          <span className="numeric font-mono font-medium text-foreground">{counts[type]}</span> {label}
        </span>
      ))}
    </div>
  );
}

function Timeline({ run, series, events, playback }: { run: Run; series: TickPoint[]; events: EngineEvent[]; playback: Playback }) {
  const keys = useMemo(() => numericSeriesKeys(series), [series]);
  const [metric, setMetric] = useState<string | undefined>(worldMeta(run.spec.world).kpis[0]);
  const active = metric && keys.includes(metric) ? metric : keys[0];
  const ticks = useMemo(() => series.map((p) => p.tick), [series]);
  const values = useMemo(() => (active ? seriesValues(series, active) : []), [series, active]);
  const byTick = useMemo(() => eventsByTick(events), [events]);
  const density = useMemo(() => {
    const d = new Map<number, number>();
    for (const [t, list] of byTick) d.set(t, list.filter((e) => e.type !== "observed" && e.type !== "tick_ended").length);
    return d;
  }, [byTick]);
  const flagged = useMemo(() => new Set(events.filter((e) => e.type === "intent_blocked" || e.type === "policy_failed").map((e) => e.tick)), [events]);

  return (
    <section className="surface-edge overflow-hidden rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <h2 className="text-sm font-medium">Timeline</h2>
        {keys.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {keys.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setMetric(k)}
                className={cn(
                  "h-7 rounded-md px-2.5 text-xs transition-colors",
                  k === active ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {humanize(k)}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-4 p-4">
        {active ? (
          <TimeSeriesChart ticks={ticks} values={values} cursor={playback.position} onSeek={playback.seek} format={(v) => formatMetric(active, v)} />
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">No metric changes over time in this run.</p>
        )}
        {playback.max > playback.min && <Scrubber playback={playback} density={density} flagged={flagged} />}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <div className="flex items-center gap-3">
            <span className="numeric font-mono text-xs text-muted-foreground">tick {playback.tick}</span>
            <TickActivity events={byTick.get(playback.tick) ?? []} />
          </div>
          {playback.max > playback.min && <PlaybackHints />}
        </div>
      </div>
    </section>
  );
}

const LEGEND_COLOR: Record<string, string> = {
  acted: "bg-primary/35", signaled: "bg-primary", rejected: "bg-warning", blocked: "bg-danger",
};

/** Agents lanes + event stream + agent-at-tick panel, all synced to the playhead. */
function Inspector({ events, playback }: { events: EngineEvent[]; playback: Playback }) {
  const lanes = useMemo(() => agentLanes(events), [events]);
  const [agent, setAgent] = useState<string | null>(null);
  const [scope, setScope] = useState<StreamScope>("tick");
  const [types, setTypes] = useState<Set<string>>(() => new Set());
  const [open, setOpen] = useState<EngineEvent | null>(null);

  const openEvent = (e: EngineEvent) => {
    setOpen(e);
    if (e.tick !== playback.tick) playback.seek(e.tick);
  };

  return (
    <>
      {lanes.agents.length > 0 && playback.max > playback.min && (
        <section className="surface-edge rounded-xl border bg-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <h2 className="text-sm font-medium">Agents <span className="font-normal text-muted-foreground">· {lanes.agents.length}</span></h2>
            <div className="flex flex-wrap items-center gap-3 text-2xs text-muted-foreground">
              {LANE_LEGEND.map(([state, label]) => (
                <span key={state} className="inline-flex items-center gap-1.5"><span className={`size-2 rounded-sm ${LEGEND_COLOR[state]}`} />{label}</span>
              ))}
            </div>
          </div>
          <div className="p-4 pb-0">
            <Swimlanes
              lanes={lanes}
              min={playback.min}
              max={playback.max}
              cursor={playback.position}
              selected={agent}
              onPick={(a, t) => { setAgent(a); playback.seek(t); }}
            />
          </div>
        </section>
      )}

      <section className="surface-edge grid overflow-hidden rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 border-b lg:border-b-0 lg:border-r">
          <div className="border-b px-4 py-3"><h2 className="text-sm font-medium">Event log</h2></div>
          <EventStream
            events={events}
            tick={playback.tick}
            scope={scope}
            onScope={setScope}
            types={types}
            onTypes={setTypes}
            agent={agent}
            onClearAgent={() => setAgent(null)}
            onOpen={openEvent}
            openSeq={open?.seq ?? null}
          />
        </div>
        <div className="min-w-0">
          <div className="border-b px-4 py-3"><h2 className="text-sm font-medium">Agent at tick</h2></div>
          <AgentPanel agent={agent} tick={playback.tick} events={events} onOpen={openEvent} />
        </div>
      </section>

      <EventDetail event={open} events={events} onOpen={openEvent} onClose={() => setOpen(null)} />
    </>
  );
}

/** Mounted once events are loaded, so playback starts on the real tick range. */
function RunBody({ run, events }: { run: Run; events: EngineEvent[] }) {
  const [params, setParams] = useSearchParams();
  const series = useMemo(() => tickSeries(events), [events]);
  const range = tickRange(series);
  const initial = params.get("t") !== null ? Number(params.get("t")) : undefined;
  const playback = usePlayback(range.min, range.max, Number.isFinite(initial) ? initial : undefined);
  const meta = worldMeta(run.spec.world);

  // Mirror the playhead into ?t= when paused, so a link reopens at the same tick.
  useEffect(() => {
    if (playback.playing || series.length === 0) return;
    const current = params.get("t");
    if (current !== String(playback.tick)) setParams((p) => { p.set("t", String(playback.tick)); return p; }, { replace: true });
  }, [playback.playing, playback.tick, series.length, params, setParams]);

  const now = pointAt(series, playback.tick)?.metrics ?? run.metrics;
  const ticks = series.map((p) => p.tick);
  const kpis = (meta.kpis.length ? meta.kpis : Object.keys(run.metrics)).filter((k) => k in run.metrics).slice(0, 4);
  const trending = new Set(numericSeriesKeys(series));

  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map((k, i) => {
          const numeric = trending.has(k);
          return (
            <KpiTile
              key={k}
              emphasis={i === 0}
              label={humanize(k)}
              value={formatMetric(k, series.length ? now[k] : run.metrics[k])}
              ticks={ticks}
              values={numeric ? seriesValues(series, k) : null}
              cursor={playback.tick}
            />
          );
        })}
      </div>
      <SafetyStrip run={run} />
      <Timeline run={run} series={series} events={events} playback={playback} />
      <Inspector events={events} playback={playback} />
    </>
  );
}

function RunView({ run }: { run: Run }) {
  const events = useRunEvents(run.run_id);
  const meta = worldMeta(run.spec.world);
  const verifyRun = useVerifyRun();
  const verify = {
    run: () => verifyRun.mutate(run.run_id),
    pending: verifyRun.isPending,
    result: verifyRun.data,
    error: verifyRun.error,
  };

  return (
    <Page className="space-y-6">
      <nav className="flex items-center gap-1 text-xs text-muted-foreground">
        <Link to="/worlds" className="hover:text-foreground">Worlds</Link>
        <ChevronRight className="size-3" />
        <Link to={`/w/${run.spec.world}`} className="hover:text-foreground">{meta.title}</Link>
        <ChevronRight className="size-3" />
        <Hash value={run.run_id} head={24} tail={0} className="text-xs" />
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-[-0.02em]">
            <meta.icon className="size-5 text-primary" />
            {meta.title}
            <span className="text-muted-foreground/50">·</span>
            <span>{armLabel(run.spec.arm)}</span>
          </h1>
          <p className="numeric text-sm text-muted-foreground">
            case {run.spec.case}
            {Object.entries(run.spec.params).map(([k, v]) => <span key={k}> · {humanize(k).toLowerCase()} {String(v)}</span>)}
            <span> · {run.ticks} ticks · {run.event_count.toLocaleString("en-US")} events · stopped: {run.stopped_reason ?? "—"}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <VerdictBadge verdict={run.verdict.verdict} />
          <TrustBadge trust={run.bundle.trust} />
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              document.getElementById("provenance")?.scrollIntoView({ behavior: "smooth" });
              if (!verify.result) verify.run();
            }}
          >
            <ShieldCheck /> Verify
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to={`/w/${run.spec.world}`}><RotateCcw /> New run</Link>
          </Button>
        </div>
      </header>

      {events.isError && <ErrorState error={events.error} onRetry={() => void events.refetch()} />}
      {events.isPending && <BodySkeleton />}
      {events.data && <RunBody run={run} events={events.data.events} />}
      <Provenance run={run} verify={verify} />
    </Page>
  );
}

function BodySkeleton() {
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-[118px] rounded-xl" />)}
      </div>
      <Skeleton className="h-11 rounded-xl" />
      <Skeleton className="h-[360px] rounded-xl" />
    </>
  );
}

export default function RunPage() {
  const { runId = "" } = useParams();
  const run = useRun(runId);
  if (run.data) return <RunView run={run.data} />;
  return (
    <Page className="space-y-6">
      {run.isError ? (
        <ErrorState error={run.error} onRetry={() => void run.refetch()} />
      ) : (
        <>
          <Skeleton className="h-3 w-64" />
          <Skeleton className="h-8 w-96" />
          <BodySkeleton />
        </>
      )}
    </Page>
  );
}
