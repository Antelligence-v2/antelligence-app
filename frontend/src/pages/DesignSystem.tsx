import type { ReactNode } from "react";
import { Moon, Play, Sun } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Hash } from "@/design/Hash";
import { Kbd } from "@/design/Kbd";
import { StatusDot } from "@/design/StatusDot";
import { useThemeToggle } from "@/design/theme";

const SWATCHES = [
  "background", "card", "surface-2", "surface-3", "muted", "border",
  "foreground", "muted-foreground", "primary", "success", "warning", "danger", "info",
];

const TYPE_SCALE: Array<[string, string]> = [
  ["text-2xl font-semibold tracking-[-0.02em]", "Page title · 24"],
  ["text-lg font-semibold tracking-[-0.015em]", "Section · 18"],
  ["text-[15px] font-semibold tracking-[-0.01em]", "Card title · 15"],
  ["text-sm", "Body · 14 — agents coordinate only through typed, expiring signals."],
  ["text-xs text-muted-foreground", "Caption · 12 — trust tier local_replay, proof_ok false"],
  ["text-2xs uppercase tracking-[0.08em] text-muted-foreground", "Label · 11"],
  ["font-mono text-xs numeric", "Mono · 12 — 9f3a0c71e1 · 0.17094017"],
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

/** Dev-only living reference for tokens and primitives (route /design). */
export default function DesignSystem() {
  const { theme, toggle } = useThemeToggle();
  return (
    <div className="mx-auto max-w-5xl space-y-10 px-8 py-10">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-2xs uppercase tracking-[0.08em] text-muted-foreground">Antelligence</p>
          <h1 className="text-2xl font-semibold tracking-[-0.02em]">Design system</h1>
        </div>
        <Button variant="outline" size="sm" onClick={toggle}>
          {theme === "dark" ? <Sun /> : <Moon />} {theme === "dark" ? "Light" : "Dark"}
        </Button>
      </header>

      <Section title="Color">
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
          {SWATCHES.map((name) => (
            <div key={name} className="space-y-1.5">
              <div className="h-12 rounded-lg border" style={{ background: `hsl(var(--${name}))` }} />
              <p className="font-mono text-2xs text-muted-foreground">{name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Type">
        <div className="space-y-2.5">
          {TYPE_SCALE.map(([cls, text]) => <p key={cls} className={cls}>{text}</p>)}
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button><Play /> Launch run</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
          <Button size="sm">Small</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Section>

      <Section title="Status">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="success"><StatusDot tone="success" /> safe_complete</Badge>
          <Badge variant="warning"><StatusDot tone="warning" /> safe_incomplete</Badge>
          <Badge variant="danger"><StatusDot tone="danger" /> unsafe</Badge>
          <Badge variant="info">local_replay</Badge>
          <Badge>rule</Badge>
          <Badge variant="secondary">case 3</Badge>
          <Badge variant="outline">staged</Badge>
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground"><StatusDot tone="primary" pulse /> running</span>
        </div>
      </Section>

      <Section title="Inline">
        <div className="flex flex-wrap items-center gap-6 text-sm">
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">Search <Kbd>⌘</Kbd><Kbd>K</Kbd></span>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">Play <Kbd>space</Kbd></span>
          <span className="inline-flex items-center gap-2 text-muted-foreground">trace <Hash value="9f3a0c71e1b24d8aa0c55e2e7bb1f0d95c1e0a2b77c0e1aa4d3f9b2c8e6a01e1" /></span>
        </div>
      </Section>

      <Section title="Surfaces">
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Kill rate</CardTitle>
              <CardDescription>Share of initial living cells removed</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="numeric text-3xl font-semibold tracking-[-0.02em]">17.1<span className="text-lg text-muted-foreground">%</span></p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Input</CardTitle>
              <CardDescription>Controls sit on the surface</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Input placeholder="Search runs…" />
              <Input defaultValue="tumor-rule-1-19e18ba66f" className="font-mono text-xs" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Loading</CardTitle>
              <CardDescription>Skeletons match final layout</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-8 w-24" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-2/3" />
            </CardContent>
          </Card>
        </div>
      </Section>
    </div>
  );
}
