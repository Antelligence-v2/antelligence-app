import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Page, PageHeader } from "@/design/PageHeader";
import { LEGACY_NAV, PRIMARY_NAV } from "@/shell/nav";

/** Temporary home until the engine world catalog lands (step 5). */
export default function Home() {
  const links = [...PRIMARY_NAV.filter((item) => item.to !== "/"), ...LEGACY_NAV];
  return (
    <Page>
      <PageHeader
        eyebrow="Antelligence"
        title="Worlds"
        description="One engine, many worlds: agents coordinate only through typed, expiring signals; a model-free verifier owns outcomes; every run is replayable."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {links.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="surface-edge group flex items-start gap-3 rounded-xl border bg-card p-4 transition-colors duration-fast hover:border-foreground/15 hover:bg-surface-2"
          >
            <item.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{item.label}</p>
              <p className="text-xs text-muted-foreground">{item.description}</p>
            </div>
            <ArrowUpRight className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </Link>
        ))}
      </div>
    </Page>
  );
}
