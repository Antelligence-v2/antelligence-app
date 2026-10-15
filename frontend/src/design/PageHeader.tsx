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

/**
 * Header in the landing page's style: the colony photograph under a dark fade,
 * a widely tracked eyebrow and a thin uppercase title. Always dark, in both themes.
 */
export function PhotoHeader({ eyebrow, title, description, actions, top, className }: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Breadcrumb or back link, pinned to the top-left. */
  top?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("dark relative overflow-hidden rounded-2xl bg-[#0b0f0a] text-white", className)}>
      <img src={`${import.meta.env.BASE_URL}ant-frontpage.jpg`} alt="" decoding="async" className="absolute inset-0 size-full object-cover object-[40%_62%]" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/50 to-black/30" />
      {top && <div className="absolute left-6 top-5 text-xs text-white/60 md:left-10 [&_a:hover]:text-white">{top}</div>}
      <div className="relative flex flex-wrap items-end justify-between gap-4 px-6 pb-8 pt-20 md:px-10 md:pt-28">
        <div className="min-w-0 space-y-3">
          {eyebrow && <p className="text-2xs uppercase tracking-[0.28em] text-white/60">{eyebrow}</p>}
          <h1 className="text-3xl font-extralight uppercase tracking-[0.18em] md:text-5xl">{title}</h1>
          {description && <p className="max-w-2xl text-sm leading-relaxed text-white/75">{description}</p>}
        </div>
        {actions && <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** Pill button for use on a PhotoHeader (the landing page's "Enter" button, quieter). */
export const photoButton = "inline-flex h-8 items-center gap-1.5 rounded-full border border-white/25 bg-white/10 px-3.5 text-xs font-medium text-white backdrop-blur transition-colors hover:bg-white/20 [&_svg]:size-3.5";
