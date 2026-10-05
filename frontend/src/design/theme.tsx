import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import type { ReactNode } from "react";

export type Theme = "dark" | "light";

/** Dark-first theme on the <html> element, persisted per browser. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange storageKey="antelligence-theme">
      {children}
    </NextThemes>
  );
}

export function useThemeToggle(): { theme: Theme; toggle: () => void } {
  const { resolvedTheme, setTheme } = useTheme();
  const theme: Theme = resolvedTheme === "light" ? "light" : "dark";
  return { theme, toggle: () => setTheme(theme === "dark" ? "light" : "dark") };
}
