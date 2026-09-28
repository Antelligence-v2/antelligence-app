import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

/** A keyboard key hint, e.g. <Kbd>⌘K</Kbd>. */
export function Kbd({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 select-none items-center justify-center rounded border border-border bg-surface-2 px-1 font-mono text-[10px] font-medium text-muted-foreground shadow-e1",
        className,
      )}
      {...props}
    />
  );
}
