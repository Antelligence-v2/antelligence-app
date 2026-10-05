import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Standard page heading for engine-native pages. */
export function PageHeader({ eyebrow, title, description, actions, className }: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="min-w-0 space-y-1">
        {eyebrow && <p className="text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-[-0.02em]">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Centered page column used by engine-native pages. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-6xl space-y-8 px-6 py-8 md:px-10 md:py-10", className)}>{children}</div>;
}
