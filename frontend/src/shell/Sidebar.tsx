import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronRight, Moon, Search, Sun } from "lucide-react";
import * as Collapsible from "@radix-ui/react-collapsible";
import { cn } from "@/lib/utils";
import { Kbd } from "@/design/Kbd";
import { useThemeToggle } from "@/design/theme";
import { BUILD_INFO } from "@/lib/runtime";
import { LEGACY_NAV, PRIMARY_NAV, isActive, isLegacyPath, type NavItem } from "./nav";

export function LogoMark({ className }: { className?: string }) {
  // Three agents joined by signal edges: the swarm, reduced to a glyph.
  return (
    <svg viewBox="0 0 24 24" className={cn("size-5", className)} aria-hidden>
      <path d="M6 17 12 6l6 11Z" fill="none" stroke="currentColor" strokeOpacity=".35" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="12" cy="6" r="2.6" fill="currentColor" />
      <circle cx="6" cy="17" r="2.6" fill="currentColor" />
      <circle cx="18" cy="17" r="2.6" fill="currentColor" />
    </svg>
  );
}

function NavRow({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const active = isActive(pathname, item.to);
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={cn(
        "group relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] transition-colors duration-fast",
        active ? "text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
      )}
    >
      {active && (
        <motion.span
          layoutId="nav-active"
          className="absolute inset-0 rounded-md bg-accent"
          transition={{ type: "spring", stiffness: 520, damping: 40 }}
        />
      )}
      <item.icon className={cn("relative size-4 shrink-0", active ? "text-primary" : "opacity-80")} />
      <span className="relative truncate">{item.label}</span>
    </NavLink>
  );
}

export function Sidebar({ onOpenPalette, onNavigate }: { onOpenPalette: () => void; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const { theme, toggle } = useThemeToggle();
  const onLegacyPage = isLegacyPath(pathname);
  const [legacyOpen, setLegacyOpen] = useState(onLegacyPage);
  // Reveal the group whenever navigation lands on a legacy page, so the active row is visible.
  useEffect(() => {
    if (onLegacyPage) setLegacyOpen(true);
  }, [onLegacyPage]);

  return (
    <div className="flex h-full flex-col gap-4 px-3 py-4">
      <div className="flex items-center gap-2.5 px-2">
        <LogoMark className="text-primary" />
        <span className="text-[15px] font-semibold tracking-[-0.01em]">Antelligence</span>
      </div>

      <button
        type="button"
        onClick={onOpenPalette}
        className="flex h-8 items-center gap-2 rounded-md border bg-background/60 px-2.5 text-[13px] text-muted-foreground shadow-e1 transition-colors hover:border-foreground/20 hover:text-foreground"
      >
        <Search className="size-3.5" />
        <span className="flex-1 text-left">Search</span>
        <Kbd>⌘K</Kbd>
      </button>

      <nav className="flex flex-col gap-0.5">
        {PRIMARY_NAV.map((item) => <NavRow key={item.to} item={item} onNavigate={onNavigate} />)}
      </nav>

      <Collapsible.Root open={legacyOpen} onOpenChange={setLegacyOpen} className="flex flex-col gap-0.5">
        <Collapsible.Trigger className="flex h-7 items-center gap-1.5 rounded-md px-2.5 text-2xs font-medium uppercase tracking-[0.08em] text-muted-foreground/70 transition-colors hover:text-foreground">
          <ChevronRight className={cn("size-3 transition-transform duration-base", legacyOpen && "rotate-90")} />
          Legacy
        </Collapsible.Trigger>
        <Collapsible.Content className="flex flex-col gap-0.5 overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down" style={{ ["--radix-accordion-content-height" as string]: "var(--radix-collapsible-content-height)" }}>
          {LEGACY_NAV.map((item) => <NavRow key={item.to} item={item} onNavigate={onNavigate} />)}
        </Collapsible.Content>
      </Collapsible.Root>

      <div className="mt-auto flex items-center justify-between gap-2 px-2">
        <span className="truncate font-mono text-2xs text-muted-foreground/60" title={`${BUILD_INFO.buildLabel} · ${BUILD_INFO.gitSha}`}>
          {BUILD_INFO.gitSha && BUILD_INFO.gitSha !== "unknown" ? BUILD_INFO.gitSha.slice(0, 7) : BUILD_INFO.mode}
        </span>
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {theme === "dark" ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
        </button>
      </div>
    </div>
  );
}
