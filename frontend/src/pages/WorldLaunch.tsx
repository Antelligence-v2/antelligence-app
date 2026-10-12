import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Dices, Loader2, Play, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useRunJob, useWorlds } from "@/api/queries";
import type { ParamValue, World, WorldOption } from "@/api/engine";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Kbd } from "@/design/Kbd";
import { Page, PhotoHeader } from "@/design/PageHeader";
import { EmptyState, ErrorState } from "@/design/States";
import { armLabel, humanize, selectsLlm, worldMeta } from "@/features/worlds/meta";
import { ParamField } from "@/features/worlds/ParamField";
import { SceneCanvas } from "@/features/viewport/Viewport";
import { cn } from "@/lib/utils";

const MAX_CASE = 2 ** 31 - 1;

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-2xs uppercase tracking-[0.2em] text-muted-foreground">{label}</h2>
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

function OptionPicker({ name, option, value, onChange }: { name: string; option: WorldOption; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-sm">{option.label}</p>
      <div role="radiogroup" aria-label={option.label} className="flex flex-wrap gap-1 rounded-lg border p-1">
        {option.allowed.map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={v === value}
            data-option={name}
            onClick={() => onChange(v)}
            className={cn(
              "h-8 flex-1 whitespace-nowrap rounded-md px-3 text-xs font-medium transition-colors",
              v === value ? "bg-primary/10 text-foreground ring-1 ring-primary/40" : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
            )}
          >
            {humanize(v)}
          </button>
        ))}
      </div>
    </div>
  );
}

function Launcher({ world }: { world: World }) {
  const navigate = useNavigate();
  const runJob = useRunJob();
  const meta = worldMeta(world.name);
  const defaults = useMemo(() => Object.fromEntries(Object.entries(world.params).map(([k, b]) => [k, b.default])), [world]);
  // Like the original simulators' pages: LLM-driven agents by default whenever the backend has a key.
  const optionDefaults = useMemo(() => Object.fromEntries(Object.entries(world.options ?? {}).map(([k, o]) => [
    k, k === "agent_type" && world.llm?.available && o.allowed.includes("LLM-Powered") ? "LLM-Powered" : o.default,
  ])), [world]);
  const [arm, setArm] = useState(world.baseline);
  const [caseId, setCaseId] = useState(world.default_cases[0] ?? 1);
  const [params, setParams] = useState<Record<string, number>>(defaults);
  const [options, setOptions] = useState<Record<string, string>>(optionDefaults);
  const [model, setModel] = useState(world.llm?.default_model ?? "");
  // Predator brains only matter when there are predators (the engine ignores them otherwise).
  const effective = params.n_predators === 0 ? Object.fromEntries(Object.entries(options).filter(([k]) => k !== "predator_type")) : options;
  const usesLlm = !!world.llm && selectsLlm(effective);
  const pending = runJob.running;

  const launch = async () => {
    if (pending) return;
    const body: Record<string, ParamValue> = { ...params, ...effective, ...(usesLlm ? { model: model.trim() } : {}) };
    const runId = await runJob.start({ world: world.name, arm, case: caseId, params: body });
    if (runId) {
      toast.success("Run complete", { description: `${meta.title} · ${armLabel(arm)} · case ${caseId}` });
      navigate(`/runs/${encodeURIComponent(runId)}`);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        void launch();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const summary: Array<[string, string]> = [
    ["World", meta.title],
    ["Arm", armLabel(arm)],
    ["Case (seed)", String(caseId)],
    ...Object.entries(params).map(([k, v]) => [world.param_labels?.[k] ?? humanize(k), String(v)] as [string, string]),
    ...Object.entries(effective).map(([k, v]) => [world.options?.[k]?.label ?? humanize(k), humanize(v)] as [string, string]),
    ["Policy", usesLlm ? `LLM · ${model || "no model"}` : "Rule (no LLM calls)"],
  ];
  const job = runJob.job;
  const progress = job?.max_ticks ? Math.min(1, job.tick / job.max_ticks) : 0;
  const preview = runJob.live;

  return (
    <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
      {/* Left bar: run button on top, then every setting (like the original simulator pages). */}
      <aside className="space-y-6 lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:self-start lg:overflow-y-auto lg:pr-1">
        <div className="surface-edge overflow-hidden rounded-xl border bg-card">
          <div className="relative p-4">
            {pending && <div className="absolute inset-x-0 top-0 h-px animate-shimmer bg-[linear-gradient(90deg,transparent,hsl(var(--primary)),transparent)] bg-[length:200%_100%]" />}
            <Button className="w-full rounded-full" onClick={() => void launch()} disabled={pending || (usesLlm && !model.trim())}>
              {pending ? <Loader2 className="animate-spin" /> : <Play />}
              {pending ? (job?.status === "queued" ? "Queued…" : `Running… t${job?.tick ?? 0}`) : "Launch run"}
              {!pending && <Kbd className="ml-auto border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground/80">⌘↵</Kbd>}
            </Button>
            {pending && job?.max_ticks ? (
              <div className="mt-3 space-y-1">
                <div className="h-1 overflow-hidden rounded-full bg-surface-3">
                  <div className="h-full bg-primary transition-[width] duration-300" style={{ width: `${progress * 100}%` }} />
                </div>
                <p className="numeric text-center font-mono text-2xs text-muted-foreground">tick {job.tick} / {job.max_ticks}{job.llm ? " · LLM" : ""}</p>
              </div>
            ) : (
              <p className="mt-2.5 text-center text-2xs text-muted-foreground">
                {usesLlm ? "LLM runs call your LiteLLM proxy; replays answer from the run's response cache." : "Runs locally and deterministically; results are research-grade, not clinical."}
              </p>
            )}
          </div>
        </div>
        {runJob.error && <ErrorState error={runJob.error} />}
        <Field label="Arm" hint="Which coordination mechanisms are switched on">
          <ArmPicker world={world} value={arm} onChange={setArm} />
          {world.name === "ant_colony" && arm === "queen" && usesLlm && (
            <p className="text-2xs text-muted-foreground">As in the original sim, ants follow the Queen first, so with a Queen they rarely ask the model. Use “No queen” to see the model drive the ants.</p>
          )}
        </Field>

        {Object.keys(world.options ?? {}).length > 0 && (
          <Field label="Agents" hint="Same choices as the original simulator">
            <div className="surface-edge space-y-5 rounded-xl border bg-card p-5">
              {Object.entries(world.options ?? {}).map(([name, option]) => (
                <OptionPicker key={name} name={name} option={option} value={options[name]} onChange={(v) => setOptions((o) => ({ ...o, [name]: v }))} />
              ))}
              {usesLlm && (
                <div className="space-y-2 border-t pt-4">
                  <label htmlFor="llm-model" className="flex items-center gap-1.5 text-sm"><Sparkles className="size-3.5 text-primary" />Model (via LiteLLM)</label>
                  <input
                    id="llm-model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    spellCheck={false}
                    className="h-8 w-full rounded-md border bg-transparent px-2.5 font-mono text-xs outline-none transition-colors focus:border-ring"
                  />
                  {world.llm && !world.llm.available ? (
                    <p className="text-2xs text-danger">The backend has no IO_SECRET_KEY (or LITELLM_API_KEY), so LLM runs will be refused. Set it and restart the backend.</p>
                  ) : (
                    <p className="text-2xs text-muted-foreground">Each agent asks the model on its turn, so LLM runs take minutes, not seconds. You can watch it live.</p>
                  )}
                </div>
              )}
            </div>
          </Field>
        )}

        {Object.keys(world.params).length > 0 && (
          <Field label="Parameters">
            <div className="surface-edge space-y-6 rounded-xl border bg-card p-5">
              {Object.entries(world.params).map(([name, bounds]) => (
                <ParamField key={name} name={name} label={world.param_labels?.[name]} bounds={bounds} value={params[name]} onChange={(v) => setParams((p) => ({ ...p, [name]: v }))} />
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
      </aside>

      <section className="min-w-0 space-y-4">
        {pending && preview && preview.frames.length > 0 ? (
          <div className="surface-edge overflow-hidden rounded-xl border bg-card p-3">
            <p className="px-1 pb-2 text-2xs uppercase tracking-[0.2em] text-muted-foreground">Live · tick {job?.tick ?? 0}</p>
            <div className="mx-auto max-w-[640px]">
              <SceneCanvas data={preview} position={preview.frames[preview.frames.length - 1].tick} layer={(preview.scene.kind as string) === "tumor" ? "drug" : "trail"} selected={null} onSelect={() => {}} />
            </div>
          </div>
        ) : (
          <div className="surface-edge flex aspect-[4/3] max-h-[560px] w-full items-center justify-center rounded-xl border border-dashed bg-card px-6 text-center text-2xs uppercase tracking-[0.2em] text-muted-foreground">
            {pending ? "Starting…" : "Configure the colony on the left and press Launch run"}
          </div>
        )}
        <div className="surface-edge overflow-hidden rounded-xl border bg-card">
          <div className="space-y-3 p-5">
            <h2 className="text-2xs uppercase tracking-[0.2em] text-muted-foreground">Run spec</h2>
            <dl className="space-y-2 text-sm">
              {summary.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="numeric truncate text-right font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>
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
      <PhotoHeader
        top={<Link to="/worlds" className="inline-flex items-center gap-1.5 transition-colors"><ArrowLeft className="size-3.5" /> Worlds</Link>}
        eyebrow="New run"
        title={meta.title}
        description={world?.description ?? (worlds.isPending ? <Skeleton className="h-4 w-80 bg-white/15" /> : undefined)}
      />
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
