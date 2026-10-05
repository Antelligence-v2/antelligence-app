import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight, ArrowUp, ArrowUpRight } from "lucide-react";
import { useWorlds } from "@/api/queries";
import type { World } from "@/api/engine";
import { Skeleton } from "@/components/ui/skeleton";
import { Page, PageHeader } from "@/design/PageHeader";
import { ErrorState } from "@/design/States";
import { armLabel, humanize, worldMeta } from "@/features/worlds/meta";
import { PRIMARY_NAV } from "@/shell/nav";

function WorldCard({ world }: { world: World }) {
  const meta = worldMeta(world.name);
  const Direction = world.lower_is_better ? ArrowDown : ArrowUp;
  return (
    <Link
      to={`/w/${world.name}`}
      className="surface-edge group relative flex flex-col gap-5 rounded-xl border bg-card p-5 transition-[border-color,background-color,transform] duration-base ease-out-expo hover:-translate-y-0.5 hover:border-foreground/15 hover:bg-surface-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-9 items-center justify-center rounded-lg border bg-surface-2 text-primary transition-colors group-hover:border-primary/30">
          <meta.icon className="size-[18px]" />
        </div>
        <ArrowRight className="size-4 -translate-x-1 text-muted-foreground opacity-0 transition-[opacity,transform] duration-base group-hover:translate-x-0 group-hover:opacity-100" />
      </div>
      <div className="space-y-1.5">
        <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{meta.title}</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">{world.description}</p>
      </div>
      <div className="mt-auto flex flex-wrap gap-1.5">
        {world.arms.map((arm) => (
          <span key={arm} className="rounded-md border bg-background/40 px-1.5 py-0.5 text-2xs text-muted-foreground">
            {armLabel(arm)}
          </span>
        ))}
      </div>
      <dl className="grid grid-cols-2 gap-3 border-t pt-4 text-xs">
        <div className="space-y-0.5">
          <dt className="flex items-center gap-1 text-muted-foreground">
            Primary metric
            <Direction className="size-3" aria-label={world.lower_is_better ? "lower is better" : "higher is better"} />
          </dt>
          <dd className="font-medium leading-snug">{world.metric_label ?? humanize(world.primary_metric)}</dd>
        </div>
        <div className="space-y-0.5">
          <dt className="text-muted-foreground">Seeded cases</dt>
          <dd className="numeric font-medium">{world.default_cases.length}</dd>
        </div>
      </dl>
    </Link>
  );
}

function CardSkeleton() {
  return (
    <div className="flex flex-col gap-5 rounded-xl border bg-card p-5">
      <Skeleton className="size-9 rounded-lg" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="flex gap-1.5">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-20" />
      </div>
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export default function Worlds() {
  const worlds = useWorlds();
  const research = PRIMARY_NAV.find((item) => item.to === "/research");

  return (
    <Page>
      <PageHeader
        eyebrow="Antelligence engine"
        title="Worlds"
        description="Every world runs on one kernel: agents see only local views, coordinate through typed expiring signals, and a model-free verifier owns outcomes. Every run is hash-chained and replayable."
      />

      {worlds.isError ? (
        <ErrorState error={worlds.error} onRetry={() => void worlds.refetch()} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {worlds.isPending
            ? Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />)
            : worlds.data.map((world) => <WorldCard key={world.name} world={world} />)}
        </div>
      )}

      {research && (
        <Link
          to={research.to}
          className="group flex items-center gap-3 rounded-xl border border-dashed px-5 py-4 text-sm transition-colors hover:border-foreground/20 hover:bg-card"
        >
          <research.icon className="size-4 text-muted-foreground group-hover:text-primary" />
          <span className="font-medium">{research.label}</span>
          <span className="text-muted-foreground">{research.description}</span>
          <ArrowUpRight className="ml-auto size-3.5 text-muted-foreground" />
        </Link>
      )}
    </Page>
  );
}
