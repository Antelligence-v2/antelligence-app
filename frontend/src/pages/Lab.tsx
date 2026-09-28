import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatDistanceToNowStrict } from "date-fns";
import { ArrowRight, FlaskConical, Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { useCreateExperiment, useExperiments, useWorlds } from "@/api/queries";
import type { World } from "@/api/engine";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Page, PageHeader } from "@/design/PageHeader";
import { EmptyState, ErrorState } from "@/design/States";
import { minimumP } from "@/features/lab/stats";
import { armLabel, worldMeta } from "@/features/worlds/meta";
import { ParamField } from "@/features/worlds/ParamField";
import { cn } from "@/lib/utils";

const MAX_CASES = 20;

function Section({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">{label}</h2>
        {hint && <p className="text-2xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) return setSeconds(0);
    const start = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 250);
    return () => window.clearInterval(id);
  }, [active]);
  return seconds;
}

function Builder({ worlds }: { worlds: World[] }) {
  const navigate = useNavigate();
  const create = useCreateExperiment();
  const elapsed = useElapsed(create.isPending);
  const [worldName, setWorldName] = useState(worlds[0].name);
  const world = worlds.find((w) => w.name === worldName) ?? worlds[0];
  const [arms, setArms] = useState<string[]>(world.arms);
  const [baseline, setBaseline] = useState(world.baseline);
  const [caseCount, setCaseCount] = useState(Math.min(MAX_CASES, world.default_cases.length));
  const [params, setParams] = useState<Record<string, number>>({});

  // Switching world resets everything to that world's defaults.
  useEffect(() => {
    setArms(world.arms);
    setBaseline(world.baseline);
    setCaseCount(Math.min(MAX_CASES, world.default_cases.length));
    setParams(Object.fromEntries(Object.entries(world.params).map(([k, b]) => [k, b.default])));
  }, [world]);

  const cases = useMemo(() => world.default_cases.slice(0, caseCount), [world, caseCount]);
  const runCount = arms.length * cases.length;
  const underpowered = minimumP(cases.length) >= 0.05;
  const valid = arms.length >= 2 && arms.includes(baseline) && cases.length > 0;

  const toggleArm = (arm: string) => {
    setArms((current) => {
      const next = current.includes(arm) ? current.filter((a) => a !== arm) : world.arms.filter((a) => a === arm || current.includes(a));
      if (!next.includes(baseline) && next.length) setBaseline(next[0]);
      return next;
    });
  };

  const run = () => {
    if (!valid || create.isPending) return;
    create.mutate(
      { world: world.name, arms, cases, baseline, params },
      {
        onSuccess: (report) => {
          toast.success("Experiment complete", { description: `${worldMeta(world.name).title} · ${runCount} runs` });
          navigate(`/lab/${report.experiment_id}`);
        },
      },
    );
  };

  return (
    <div className="surface-edge space-y-8 rounded-xl border bg-card p-5 md:p-6">
      <Section label="World">
        <div className="flex flex-wrap gap-2">
          {worlds.map((w) => {
            const meta = worldMeta(w.name);
            return (
              <button
                key={w.name}
                type="button"
                onClick={() => setWorldName(w.name)}
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-sm transition-colors",
                  w.name === world.name ? "border-primary/60 bg-primary/[0.08] text-foreground" : "text-muted-foreground hover:border-foreground/20 hover:text-foreground",
                )}
              >
                <meta.icon className={cn("size-4", w.name === world.name && "text-primary")} /> {meta.title}
              </button>
            );
          })}
        </div>
      </Section>

      <Section label="Arms" hint="Each selected arm runs on every seed; click “baseline” to compare against it">
        <div className="grid gap-2 sm:grid-cols-2">
          {world.arms.map((arm) => {
            const on = arms.includes(arm);
            const isBase = arm === baseline && on;
            return (
              <div
                key={arm}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 transition-colors",
                  on ? "bg-surface-2" : "opacity-60 hover:opacity-100",
                  isBase && "border-primary/50",
                )}
              >
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  aria-label={armLabel(arm)}
                  onClick={() => toggleArm(arm)}
                  className={cn("mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border transition-colors", on ? "border-primary bg-primary" : "border-muted-foreground/40")}
                >
                  {on && <svg viewBox="0 0 12 12" className="size-3 text-primary-foreground"><path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                </button>
                <div className="min-w-0 flex-1 space-y-0.5">
                  <p className="text-sm font-medium">{armLabel(arm)}</p>
                  {world.arm_descriptions?.[arm] && <p className="text-xs leading-relaxed text-muted-foreground">{world.arm_descriptions[arm]}</p>}
                </div>
                {on && (
                  <button
                    type="button"
                    onClick={() => setBaseline(arm)}
                    className={cn("shrink-0 rounded px-1.5 py-0.5 text-2xs transition-colors", isBase ? "bg-primary font-medium text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground")}
                  >
                    baseline
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <Section label="Seeds" hint="The same seeds run under every arm (paired design)">
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <Slider min={1} max={Math.min(MAX_CASES, world.default_cases.length)} step={1} value={[caseCount]} onValueChange={([v]) => setCaseCount(v)} aria-label="Seeds" className="flex-1" />
            <span className="numeric w-20 whitespace-nowrap text-right font-mono text-sm">{caseCount} seeds</span>
          </div>
          <p className="truncate font-mono text-2xs text-muted-foreground">{cases.join(" · ")}</p>
          {underpowered && (
            <p className="text-xs text-warning">
              With {cases.length} seeds no difference can reach p &lt; 0.05 (smallest possible p is {minimumP(cases.length).toFixed(2)}). Use at least 6.
            </p>
          )}
        </div>
      </Section>

      {Object.keys(world.params).length > 0 && (
        <Section label="Parameters">
          <div className="space-y-6">
            {Object.entries(world.params).map(([name, bounds]) => (
              <ParamField key={name} name={name} bounds={bounds} value={params[name] ?? bounds.default} onChange={(v) => setParams((p) => ({ ...p, [name]: v }))} />
            ))}
          </div>
        </Section>
      )}

      <div className="relative flex flex-wrap items-center justify-between gap-3 border-t pt-5">
        {create.isPending && <div className="absolute inset-x-0 top-0 h-px animate-shimmer bg-[linear-gradient(90deg,transparent,hsl(var(--primary)),transparent)] bg-[length:200%_100%]" />}
        <p className="numeric text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{arms.length}</span> arms × <span className="font-medium text-foreground">{cases.length}</span> seeds = <span className="font-medium text-foreground">{runCount}</span> runs
          {create.isPending && <span className="ml-2 font-mono text-xs">· {elapsed}s</span>}
        </p>
        <Button onClick={run} disabled={!valid || create.isPending}>
          {create.isPending ? <Loader2 className="animate-spin" /> : <Play />}
          {create.isPending ? "Running…" : "Run experiment"}
        </Button>
      </div>
      {!valid && arms.length < 2 && <p className="-mt-4 text-xs text-muted-foreground">Pick at least two arms to compare.</p>}
      {create.isError && <ErrorState error={create.error} />}
    </div>
  );
}

function Library() {
  const experiments = useExperiments();
  return (
    <div className="surface-edge overflow-hidden rounded-xl border bg-card">
      <div className="border-b px-4 py-3"><h2 className="text-sm font-medium">Library</h2></div>
      {experiments.isError && <ErrorState className="m-3" error={experiments.error} onRetry={() => void experiments.refetch()} />}
      {experiments.isPending && <div className="space-y-2 p-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div>}
      {experiments.data?.length === 0 && (
        <EmptyState icon={<FlaskConical />} title="No experiments yet" className="m-3 border-none">Results you run appear here and are kept by the engine.</EmptyState>
      )}
      <ul className="divide-y">
        {experiments.data?.map((item) => {
          const meta = worldMeta(item.request.world);
          return (
            <li key={item.experiment_id}>
              <Link to={`/lab/${item.experiment_id}`} className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/60">
                <meta.icon className="size-4 shrink-0 text-muted-foreground group-hover:text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{meta.title} <span className="font-normal text-muted-foreground">· {item.request.arms.length} arms × {item.request.cases.length} seeds</span></p>
                  <p className="text-2xs text-muted-foreground">{formatDistanceToNowStrict(item.created_at * 1000, { addSuffix: true })} · baseline {armLabel(item.request.baseline)}</p>
                </div>
                <ArrowRight className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Lab() {
  const worlds = useWorlds();
  return (
    <Page>
      <PageHeader
        eyebrow="Experiments"
        title="Lab"
        description="Run several arms on the same seeded cases and compare each to a baseline with a paired sign test. Results stay honest about sample size and safety."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        {worlds.isError && <ErrorState error={worlds.error} onRetry={() => void worlds.refetch()} />}
        {worlds.isPending && <Skeleton className="h-[560px] rounded-xl" />}
        {worlds.data && <Builder worlds={worlds.data} />}
        <Library />
      </div>
    </Page>
  );
}
