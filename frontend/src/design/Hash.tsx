import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function shortHash(value: string, head = 6, tail = 4): string {
  return value.length <= head + tail + 1 ? value : `${value.slice(0, head)}…${value.slice(-tail)}`;
}

/** A content hash or id: monospace, truncated, full value on hover, click to copy. */
export function Hash({ value, head, tail, className, copy = true }: {
  value: string;
  head?: number;
  tail?: number;
  className?: string;
  copy?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // Clipboard can be unavailable (insecure context); the full value is still in the tooltip.
    }
  };
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={copy ? onCopy : undefined}
          className={cn(
            "group inline-flex items-center gap-1 rounded px-1 -mx-1 font-mono text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
            className,
          )}
        >
          <span className="numeric">{shortHash(value, head, tail)}</span>
          {copy && (copied
            ? <Check className="size-3 text-success" />
            : <Copy className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />)}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[28rem] break-all font-mono">{value}</TooltipContent>
    </Tooltip>
  );
}
