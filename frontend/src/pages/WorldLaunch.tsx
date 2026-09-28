import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Dices, Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { useCreateRun, useWorlds } from "@/api/queries";
import type { World } from "@/api/engine";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Kbd } from "@/design/Kbd";
import { Page, PageHeader } from "@/design/PageHeader";
import { EmptyState, ErrorState } from "@/design/States";
import { armLabel, humanize, worldMeta } from "@/features/worlds/meta";
import { ParamField } from "@/features/worlds/ParamField";
import { cn } from "@/lib/utils";

const MAX_CASE = 2 ** 31 - 1;

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
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

function ArmPicker({ world, value, onChange }: { world: World; value: string; onChange: (arm: string) => void }) {
  return (
    <div role="radiogroup" aria-label="Arm" className="grid gap-2 sm:grid-cols-2">
      {world.arms.map((arm) => {
        const selected = arm === value;
        return (
          <button
            key={arm}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(arm)}
            className={cn(
              "surface-edge flex flex-col gap-1 rounded-lg border p-3.5 text-left transition-[border-color,background-color,box-shadow] duration-fast",
              selected ? "border-primary/60 bg-primary/[0.06] ring-1 ring-primary/30" : "bg-card hover:border-foreground/15 hover:bg-surface-2",
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              <span className={cn("size-3.5 rounded-full border transition-colors", selected ? "border-[4px] border-primary" : "border-muted-foreground/40")} />
              {armLabel(arm)}
              {arm === world.baseline && <span className="ml-auto rounded bg-surface-3 px-1.5 py-0.5 text-2xs font-normal text-muted-foreground">baseline</span>}
            </span>
            {world.arm_descriptions?.[arm] && <span className="pl-[22px] text-xs leading-relaxed text-muted-foreground">{world.arm_descriptions[arm]}</span>}
          </button>
        );
      })}
    </div>
  );
}

function Launcher({ world }: { world: World }) {
  const navigate = useNavigate();
  const createRun = useCreateRun();
  const meta = worldMeta(world.name);
  const defaults = useMemo(() => Object.fromEntries(Object.entries(world.params).map(([k, b]) => [k, b.default])), [world]);
  const [arm, setArm] = useState(world.baseline);
  const [caseId, setCaseId] = useState(world.default_cases[0] ?? 1);
  const [params, setParams] = useState<Record<string, number>>(defaults);

  const launch = () => {
    if (createRun.isPending) return;
    createRun.mutate(
      { world: world.name, arm, case: caseId, params },
      {
        onSuccess: (run) => {
          toast.success("Run complete", { description: `${meta.title} · ${armLabel(arm)} · case ${caseId}` });
          navigate(`/runs/${encodeURIComponent(run.run_id)}`);
        },
      },
    );
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        launch();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const summary: Array<[string, string]> = [
    ["World", meta.title],
    ["Arm", armLabel(arm)],
    ["Case (seed)", String(caseId)],
    ...Object.entries(params).map(([k, v]) => [humanize(k), String(v)] as [string, string]),
    ["Policy", "Rule (no LLM calls)"],
  ];

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="space-y-8">
        <Field label="Arm" hint="Which coordination mechanisms are switched on">
          <ArmPicker world={world} value={arm} onChange={setArm} />
        </Field>

        {Object.keys(world.params).length > 0 && (
          <Field label="Parameters">
            <div className="surface-edge space-y-6 rounded-xl border bg-card p-5">
              {Object.entries(world.params).map(([name, bounds]) => (
                <ParamField key={name} name={name} bounds={bounds} value={params[name]} onChange={(v) => setParams((p) => ({ ...p, [name]: v }))} />
              ))}
            </div>
          </Field>
        )}

        <Field label="Case" hint="Same case + arm + params always produces the same run">
          <div className="flex flex-wrap items-center gap-1.5">
            {world.default_cases.slice(0, 12).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCaseId(c)}
                className={cn(
                  "numeric h-7 min-w-9 rounded-md border px-2 font-mono text-xs transition-colors",
                  c === caseId ? "border-primary/60 bg-primary/10 text-foreground" : "text-muted-foreground hover:border-foreground/20 hover:text-foreground",
                )}
              >
                {c}
              </button>
            ))}
            <div className="mx-1 h-5 w-px bg-border" />
            <input
              aria-label="Custom case"
              inputMode="numeric"
              value={caseId}
              onChange={(e) => {
                const n = Number(e.target.value.replace(/\D/g, ""));
                if (Number.isFinite(n)) setCaseId(Math.min(MAX_CASE, n));
              }}
              className="numeric h-7 w-24 rounded-md border bg-transparent px-2 font-mono text-xs outline-none focus:border-ring"
            />
            <Button variant="ghost" size="icon-sm" aria-label="Random case" onClick={() => setCaseId(Math.floor(Math.random() * 100_000))}>
              <Dices />
            </Button>
          </div>
        </Field>
      </div>

      <aside className="lg:sticky lg:top-8 lg:self-start">
        <div className="surface-edge overflow-hidden rounded-xl border bg-card">
          <div className="space-y-3 p-5">
            <h2 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">Run spec</h2>
            <dl className="space-y-2 text-sm">
              {summary.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="numeric truncate text-right font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="relative border-t p-4">
            {createRun.isPending && <div className="absolute inset-x-0 top-0 h-px animate-shimmer bg-[linear-gradient(90deg,transparent,hsl(var(--primary)),transparent)] bg-[length:200%_100%]" />}
            <Button className="w-full" onClick={launch} disabled={createRun.isPending}>
              {createRun.isPending ? <Loader2 className="animate-spin" /> : <Play />}
              {createRun.isPending ? "Running…" : "Launch run"}
              {!createRun.isPending && <Kbd className="ml-auto border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground/80">⌘↵</Kbd>}
            </Button>
            <p className="mt-2.5 text-center text-2xs text-muted-foreground">Runs locally and deterministically; results are research-grade, not clinical.</p>
          </div>
        </div>
        {createRun.isError && <ErrorState className="mt-3" error={createRun.error} />}
      </aside>
    </div>
  );
}

export default function WorldLaunch() {
  const { world: name = "" } = useParams();
  const worlds = useWorlds();
  const world = worlds.data?.find((w) => w.name === name);
  const meta = worldMeta(name);

  return (
    <Page>
      <div className="space-y-4">
        <Link to="/worlds" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
          <ArrowLeft className="size-3.5" /> Worlds
        </Link>
        <PageHeader
          eyebrow="New run"
          title={<span className="flex items-center gap-2.5"><meta.icon className="size-5 text-primary" />{meta.title}</span>}
          description={world?.description ?? (worlds.isPending ? <Skeleton className="h-4 w-80" /> : undefined)}
        />
      </div>
      {worlds.isError && <ErrorState error={worlds.error} onRetry={() => void worlds.refetch()} />}
      {worlds.isPending && <Skeleton className="h-96 w-full" />}
      {worlds.isSuccess && !world && (
        <EmptyState title={`No world named “${name}”`}>
          Available: {worlds.data.map((w) => w.name).join(", ")}.
        </EmptyState>
      )}
      {world && <Launcher key={world.name} world={world} />}
    </Page>
  );
}
