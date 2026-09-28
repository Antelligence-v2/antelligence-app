import { useEffect, useRef } from "react";

/** True when a key event comes from a field where typing must not trigger shortcuts. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

const CHORD_WINDOW_MS = 900;

/**
 * Global shortcuts: ⌘K / Ctrl+K toggles the palette, "g <key>" chords navigate.
 * `chords` maps the second key (e.g. "w") to a handler.
 */
export function useGlobalHotkeys({ onPalette, chords }: { onPalette: () => void; chords: Record<string, () => void> }) {
  const pending = useRef<number | null>(null);
  const latest = useRef({ onPalette, chords });
  latest.current = { onPalette, chords };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        latest.current.onPalette();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      const key = event.key.toLowerCase();
      if (pending.current !== null && Date.now() - pending.current < CHORD_WINDOW_MS) {
        pending.current = null;
        const handler = latest.current.chords[key];
        if (handler) {
          event.preventDefault();
          handler();
        }
        return;
      }
      pending.current = key === "g" ? Date.now() : null;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
