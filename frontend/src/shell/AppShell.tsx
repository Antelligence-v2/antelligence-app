import { Suspense, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { PreviewModeBanner } from "@/components/PreviewModeBanner";
import { CommandPalette } from "./CommandPalette";
import { ErrorBoundary } from "./ErrorBoundary";
import { useGlobalHotkeys } from "./hotkeys";
import { LEGACY_NAV, PRIMARY_NAV } from "./nav";
import { LogoMark, Sidebar } from "./Sidebar";

export function PageFallback() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-8 md:px-10">
      <div className="space-y-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-7 w-64" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    </div>
  );
}

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const chords = useMemo(() => {
    const map: Record<string, () => void> = {};
    for (const item of [...PRIMARY_NAV, ...LEGACY_NAV]) {
      const key = item.chord?.split(" ")[1];
      if (key) map[key] = () => navigate(item.to);
    }
    return map;
  }, [navigate]);
  useGlobalHotkeys({ onPalette: () => setPaletteOpen((open) => !open), chords });

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <aside className="hidden w-60 shrink-0 border-r bg-card/40 md:block">
        <Sidebar onOpenPalette={() => setPaletteOpen(true)} />
      </aside>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <Sidebar onOpenPalette={() => { setMobileNavOpen(false); setPaletteOpen(true); }} onNavigate={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b px-4 md:hidden">
          <button type="button" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)} className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            <Menu className="size-4" />
          </button>
          <LogoMark className="size-4 text-primary" />
          <span className="text-sm font-semibold">Antelligence</span>
        </header>
        <PreviewModeBanner />
        <main className="min-h-0 flex-1 overflow-y-auto">
          <ErrorBoundary resetKey={location.pathname}>
            <Suspense fallback={<PageFallback />}>
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                className="min-h-full"
              >
                <Outlet />
              </motion.div>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
